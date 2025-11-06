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
        img = ImageGrab.grab(bbox=bbox)
        img.save(full_path)
        return full_path
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return None

def main():
    print("--- Sentinel Agent v2.0 (Brain + Memory) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)

    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    
    print("[BRAIN] Sentinel Agent v2.0 initialized.")
    print("This script is the new foundation.")
    print("Next steps will be to build the 'perceive' and 'act' loops.")
    
    # --- TODO: Build the full agent loop here ---
    # 1. Perceive: "What app am I in?"
    # 2. Retrieve: "What do I know about this app?" (from SQLite)
    # 3. Act: "Find the 'Copy' button."
    # 4. Verify: "Does this look like the 'Copy' button I have in memory?" (from ChromaDB)
    # 5. Execute: Click the button.
    # 6. Learn: If the button moved, update the SQLite DB.
    
    print("\n--- TEST: Storing a new memory ---")
    # This is an example of how we'll use the memory
    try:
        # We would get this embedding from the AI
        example_embedding = [0.1] * 1536 # Placeholder embedding
        memory.store_visual_memory(
            label="test_button",
            embedding=example_embedding,
            app_name="notepad.exe",
            window_title="Untitled - Notepad",
            x=100,
            y=200,
            notes="This is a test entry."
        )
        print("Successfully stored a test memory.")
        
        print("\n--- TEST: Retrieving a memory ---")
        retrieved = memory.retrieve_fact_memory("test_button", "notepad.exe")
        if retrieved:
            print(f"Successfully retrieved fact memory:")
            print(f"  App: {retrieved.app_name}")
            print(f"  Coords: ({retrieved.last_known_x}, {retrieved.last_known_y})")
            
            print("\n--- TEST: Finding a visual match ---")
            matches = memory.find_visual_match(example_embedding, num_results=1)
            if matches:
                print(f"Successfully found visual match in ChromaDB!")
                print(f"  ID: {matches['ids'][0]}")
                
    except Exception as e:
        print(f"Database test failed: {e}")
        print("Please ensure you have run 'pip install -r requirements.txt'")


if __name__ == "__main__":
    main()