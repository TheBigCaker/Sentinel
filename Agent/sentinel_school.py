import sys
import os
import json
import time
from PIL import Image
from llama_cpp import Llama
import pyautogui
import sentinel_memory
import pygetwindow as gw
import psutil
from pathlib import Path # Keep this import
import mss
import base64
import io

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
    
    MODEL_PATH = config['model_path']
    MMPROJ_PATH = config['mmproj_path']
    DB_PATH = config['db_path']
    SCREENSHOT_FILE = config['screenshot_file']
    
    memory = sentinel_memory.Memory(DB_PATH)
    llm = None
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# --- 2. PROMPTS (v2.9.2 - Reverted to v2.5 prompt) ---
VISION_PROMPT_GET_EMBEDDING = (
    "USER: [Image]Look at this small, cropped image of a user interface element. "
    "Generate a vector embedding for this image."
)

# -------------------------------------------

def get_full_screenshot_path():
    return os.path.join(DB_PATH, SCREENSHOT_FILE)

def take_screenshot_mss(x, y, width=64, height=64):
    """
    Takes a small, focused screenshot using mss and SAVES TO DISK.
    v2.9.2: Fixes Base64 bug by saving to file for file:/// URI.
    """
    full_path = get_full_screenshot_path() # Get the temp file path
    try:
        with mss.mss() as sct:
            monitor = {
                "top": y - (height // 2),
                "left": x - (width // 2),
                "width": width,
                "height": height,
            }
            sct_img = sct.grab(monitor)
            
            # Save the image to disk
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=full_path)
            print(f"[EYES] Screenshot saved to: {full_path}")
            return full_path # Return the path
            
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot with mss: {e}")
        return None

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
        print(f"[PERCEIVE] Identified App: {app_name}, Title: {title}")
        return app_name, title
    except Exception as e:
        print(f"[PERCEIVE] Error: Could not get active window: {e}")
        return None, None

def load_ai_model():
    """Loads the Llama model into memory."""
    global llm
    if llm:
        return
        
    print(f"[TEACHER] Loading Gemma 3 model... (This may take a moment)")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: 'model_path' not found: {MODEL_PATH}")
        sys.exit(1)
    if not os.path.exists(MMPROJ_PATH):
        print(f"ERROR: 'mmproj_path' not found: {MMPROJ_PATH}")
        print("This file is the 'Eyes' of the model and is required for vision.")
        sys.exit(1)

    try:
        llm = Llama(
            model_path=MODEL_PATH,
            mmproj_path=MMPROJ_PATH, # <-- This is correct
            n_ctx=2048,
            n_batch=512,
            logits_all=True,
            embedding=True,
            verbose=False
        )
        print("[TEACHER] Model loaded successfully.")
    except Exception as e:
        print(f"[TEACHER] CRITICAL ERROR: Failed to load model: {e}")
        sys.exit(1)

def get_visual_embedding(x, y):
    """
    Takes a small, focused screenshot and returns its vector embedding.
    v2.9.2: Reverts to file:/// URI scheme.
    """
    print(f"[EYES] Learning target at ({x}, {y})...")
    
    # 1. Get the path to the saved screenshot
    screenshot_path = take_screenshot_mss(x, y)
    if not screenshot_path:
        return None
        
    try:
        # 2. Convert the Windows path to a valid file URI
        # This was the fix from v2.7!
        image_uri = Path(screenshot_path).as_uri()
        print(f"[EYES] Generating embedding from file URI: {image_uri}")
        
        prompt = VISION_PROMPT_GET_EMBEDDING
        messages = [
            {"role": "user",
             "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_uri}} # Use the file URI
             ]}
        ]
    
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=100,
            embedding=True # Explicitly ask for an embedding
        )
        
        print(f"[EYES] Full Embedding Response: {response}")
        
        # Check for the embedding on the response object (from v2.5)
        if 'embedding' in response and response['embedding']:
            embedding = response['embedding']
            print(f"[EYES] Successfully generated embedding (Size: {len(embedding)}).")
            return embedding
        else:
            print("[EYES] Error: Model response did not contain an embedding.")
            return None
            
    except Exception as e:
        print(f"[EYES] Error generating embedding: {e}")
        return None

def main():
    print("--- Sentinel School v2.9.2 (Learning Wizard) ---")
    
    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    load_ai_model() # Load the heavy model for learning
    
    print("[TEACHER] Welcome to Sentinel School.")
    
    try:
        # 1. Get a label for the new memory
        target_label = input("[TEACHER] What do you want to teach me? (e.g., 'gemini_copy_button'): ")
        if not target_label:
            print("Invalid label. Aborting.")
            return

        # 2. Get the current application context
        print("\n[TEACHER] Please switch to the application window you want to teach me about.")
        print("You have 3 seconds...")
        time.sleep(3)
        
        app_name, window_title = perceive_environment()
        if not app_name:
            print("Could not identify application. Aborting.")
            return
        
        print(f"[TEACHER] OK, we are teaching a task in '{app_name}'.")

        # 3. Get the exact coordinates from the user
        print(f"\n[TEACHER] Now, please move your mouse *exactly* over the '{target_label}' button.")
        input("[TEACHER] Press ENTER when you are ready.")
        
        x, y = pyautogui.position()
        print(f"[TEACHER] Got it! Learning coordinates: ({x}, {y})")

        # 4. Generate the visual embedding
        embedding = get_visual_embedding(x, y)
        
        if embedding:
            # 5. Store in both databases
            print(f"[TEACHER] Learning complete. Storing in memory...")
            memory.store_visual_memory(
                label=target_label,
                embedding=embedding,
                app_name=app_name,
                window_title=window_title,
                x=x,
                y=y,
                notes=f"Taught by user in Sentinel School."
            )
            print("\n--- ✅ SUCCESS! ---")
            print(f"I have successfully learned the '{target_label}' for '{app_name}'.")
            print(f"You can now run 'python sentinel_agent.py' to test it.")
        else:
            print("[TEACHER] Could not learn target (failed to get embedding).")
            print("[TEACHER] Please check the model and try again.")

    except KeyboardInterrupt:
        print("\n[TEACHER] Training cancelled.")
    except Exception as e:
        print(f"\n[TEACHER] A critical error occurred: {e}")
    finally:
        # Clean up temp screenshot
        temp_shot = get_full_screenshot_path()
        if os.path.exists(temp_shot):
            os.remove(temp_shot)
        

if __name__ == "__main__":
    main()