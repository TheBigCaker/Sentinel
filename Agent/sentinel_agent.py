import sys
import os
import json
import re
import time
from PIL import ImageGrab
from llama_cpp import Llama
import pyautogui
import pyperclip
import sentinel_memory
import pygetwindow as gw # v2.1: Import perception library
import psutil # v2.1: Import process utility

# --- 1. CONFIGURATION (Loaded from JSON) ---
try:
    with open('sentinel_config.json', 'r') as f:
        config = json.load(f)
    
    MODEL_PATH = config['model_path']
    DB_PATH = config['db_path']
    SCREENSHOT_FILE = config['screenshot_file']
    
    # Initialize the "Memory"
    memory = sentinel_memory.Memory(DB_PATH)
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# --- 2. PROMPTS ---
VISION_PROMPT_FIND = "USER: [Image]Scan this screenshot. Find the <{target_description}>. What are its center coordinates? Respond ONLY with JSON: {\"x\": <center_x>, \"y\": <center_y>}"
VISION_PROMPT_VERIFY = "USER: [Image]Look at this small image. Does this image contain a <{target_description}>? Respond ONLY with JSON: {\"answer\": \"yes\" or \"no\"}"

# -------------------------------------------

def get_full_screenshot_path():
    return os.path.join(DB_PATH, SCREENSHOT_FILE)

def take_screenshot(bbox=None):
    """Takes a screenshot. If bbox is provided, crops to that region."""
    full_path = get_full_screenshot_path()
    print(f"Taking screenshot... saving to {full_path}")
    try:
        img = ImageGrab.grab(bbox=bbox, all_screens=True) # v2.1: Grab all screens
        img.save(full_path)
        return full_path
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return None

# --- v2.1: "PERCEIVE" FUNCTION ---
def perceive_environment():
    """
    The "Brain's" perception function.
    Determines the currently active application and window.
    """
    print("[PERCEIVE] Analyzing active window...")
    try:
        active_window = gw.getActiveWindow()
        if not active_window:
            print("[PERCEIVE] No active window found.")
            return None, None

        title = active_window.title
        
        # Get the process executable name (e.g., "chrome.exe")
        pid = active_window._hWnd
        process = psutil.Process(pid)
        app_name = process.name()
        
        print(f"[PERCEIVE] App: {app_name}, Title: {title}")
        return app_name, title
        
    except Exception as e:
        print(f"[PERCEIVE] Error: Could not get active window: {e}")
        return None, None

def main():
    print("--- Sentinel Agent v2.1 (Brain + Memory + Perception) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)

    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    
    print("[BRAIN] Sentinel Agent v2.1 initialized.")
    
    # --- v2.1: Run the first "Perceive" test ---
    print("\n--- TEST: Running Perception Module ---")
    print("You have 3 seconds to switch to a target window (e.g., Chrome, Notepad)...")
    time.sleep(3)
    
    app_name, window_title = perceive_environment()
    
    if app_name:
        print("\n--- TEST: Retrieving Memory Based on Perception ---")
        # Now we try to retrieve a memory using what we just perceived
        fact = memory.retrieve_fact_memory("test_button", app_name)
        if fact:
            print(f"SUCCESS: Found a memory for {app_name}!")
            print(f"  > Label: {fact.label}, Coords: ({fact.last_known_x}, {fact.last_known_y})")
        else:
            print(f"No memories found for {app_name}.")
            # This is where the agent would decide to do a "full scan"
            # and then call memory.store_visual_memory(...) to learn.
    else:
        print("Perception test failed.")


if __name__ == "__main__":
    main()