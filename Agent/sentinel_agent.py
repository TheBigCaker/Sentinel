import sys
import os
import json
import time
import pyautogui
import pyperclip
import sentinel_memory
import pygetwindow as gw
import psutil

try:
    import win32process
    import win32gui
    PYWIN32_INSTALLED = True
except ImportError:
    PYWIN32_INSTALLED = False

# --- 1. CONFIGURATION (Loaded from JSON) ---
try:
    with open('sentinel_config.json', 'r') as f:
        config = json.load(f)
    
    DB_PATH = config['db_path']
    # MODEL_PATH is no longer needed here
    
    memory = sentinel_memory.Memory(DB_PATH)
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# -------------------------------------------

def perceive_environment():
    """Determines the currently active application and window."""
    print("[PERCEIVE] Analyzing active window...")
    try:
        active_window = gw.getActiveWindow()
        if not active_window:
            print("[PERCEIVE] No active window found.")
            return None, None
        title = active_window.title
        pid = None
        if os.name == 'nt' and PYWIN32_INSTALLED:
            try:
                hwnd = active_window._hWnd
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception: pass
        
        if not pid:
             print(f"[PERCEIVE] Could not determine Process ID for window.")
             return None, None
        process = psutil.Process(pid)
        app_name = process.name()
        print(f"[PERCEIVE] App: {app_name}, Title: {title}")
        return app_name, title
    except Exception as e:
        print(f"[PERCEIVE] Error: Could not get active window: {e}")
        return None, None

def click_at_position(x, y, description=""):
    """
    The "Hands" function. Clicks at a specific coordinate.
    """
    print(f"[HANDS] Activating for: '{description}'")
    try:
        print(f"Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.25)
        print("Clicking...")
        pyautogui.click()
        print(f"--- Clicked '{description}' ---")
        return True
    except Exception as e:
        print(f"[HANDS] Error: Could not run clicker: {e}")
        return False

def main():
    print("--- Sentinel Agent v2.6 (Worker) ---")
    
    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    print("[BRAIN] Sentinel Agent v2.6 initialized.")
    print("This agent will now attempt to find a target *from memory*.")
    
    # --- THE NEW "WORKER" LOOP ---
    
    # 1. Define our goal
    # In a real app, this would come from a user prompt or task list
    TARGET_LABEL = "gemini_copy_button" 
    
    print(f"\n--- GOAL: Find and click '{TARGET_LABEL}' ---")
    
    # 2. Perceive environment
    print("You have 3 seconds to switch to the target window (Google Gemini)...")
    time.sleep(3)
    app_name, window_title = perceive_environment()
    
    if not app_name:
        print("[BRAIN] Perception failed. Cannot continue.")
        return
        
    # 3. Retrieve Memory
    print(f"\n--- RETRIEVING MEMORY for '{TARGET_LABEL}' in '{app_name}' ---")
    fact = memory.retrieve_fact_memory(TARGET_LABEL, app_name)
    
    if fact:
        print(f"SUCCESS: Found memory for '{TARGET_LABEL}'!")
        print(f"  > Last Known Coords: ({fact.last_known_x}, {fact.last_known_y})")
        
        # 4. Act
        print(f"[BRAIN] Attempting to click...")
        click_at_position(fact.last_known_x, fact.last_known_y, TARGET_LABEL)
        
        # TODO: Add verification logic here.
        # "Did the clipboard content change?"
        
    else:
        # 4. Fail (We no longer try to learn here)
        print(f"[BRAIN] No memory found for '{TARGET_LABEL}' in '{app_name}'.")
        print(f"[BRAIN] I have not been trained for this task.")
        print(f"[BRAIN] Please run 'python sentinel_school.py' to teach me.")

if __name__ == "__main__":
    main()