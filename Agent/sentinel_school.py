import sys
import os
import json
import time
from PIL import Image, ImageGrab
from llama_cpp import Llama
import pyautogui
import sentinel_memory
import pygetwindow as gw
import psutil
from pathlib import Path # <-- v2.7: IMPORT PATHLIB

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

# --- 2. PROMPTS (v2.7) ---
VISION_PROMPT_GET_EMBEDDING = (
    "USER: [Image]Describe this user interface element briefly."
)

# -------------------------------------------

def get_full_screenshot_path():
    return os.path.join(DB_PATH, SCREENSHOT_FILE)

def take_screenshot(bbox=None):
    """Takes a screenshot. If bbox is provided, crops to that region."""
    full_path = get_full_screenshot_path()
    try:
        img = ImageGrab.grab(bbox=bbox, all_screens=False)
        img.save(full_path)
        # print(f"Screenshot saved to {full_path}")
        return full_path
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
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
    try:
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_batch=512,
            logits_all=True,
            embedding=True, # MUST be true to generate embeddings
            verbose=False
        )
        print("[TEACHER] Model loaded successfully.")
    except Exception as e:
        print(f"[TEACHER] CRITICAL ERROR: Failed to load model: {e}")
        sys.exit(1)

def get_visual_embedding(x, y):
    """
    Takes a small, focused screenshot and returns its vector embedding.
    v2.7 FIX: Uses create_chat_completion and pathlib.as_uri()
    """
    print(f"[EYES] Learning target at ({x}, {y})...")
    crop_box = (x - 32, y - 32, x + 32, y + 32)
    screenshot_path = take_screenshot(bbox=crop_box)
    if not screenshot_path:
        return None
        
    try:
        # v2.7 FIX: Convert the Windows path to a valid file URI
        image_uri = Path(screenshot_path).as_uri()
        
        print(f"[EYES] Generating embedding for image at: {image_uri}")
        
        prompt = VISION_PROMPT_GET_EMBEDDING
        messages = [
            {"role": "user",
             "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_uri}}
             ]}
        ]
    
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=100
        )
        
        print(f"[EYES] Full Embedding Response: {response}")
        
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
    print("--- Sentinel School v2.7 (Learning Wizard) ---")
    
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
            print("\n--- âœ… SUCCESS! ---")
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