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
from pathlib import Path 
import mss
import base64
import io
import tkinter as tk
from tkinter import simpledialog, messagebox

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
    # v2.9.5: Two temp files
    SCREENSHOT_FILE_FULL = os.path.join(DB_PATH, "_temp_screenshot_full.png")
    SCREENSHOT_FILE_CROP = os.path.join(DB_PATH, "_temp_screenshot_crop.png")
    
    memory = sentinel_memory.Memory(DB_PATH)
    llm = None
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# --- 2. PROMPTS (v2.9.5) ---
VISION_PROMPT_GET_EMBEDDING = (
    "USER: [Image]Look at this small, cropped image of a user interface element. "
    "Generate a vector embedding for this image."
)

VISION_PROMPT_VERIFY_COORDS = (
    "USER: [Image]Look at this screenshot of a user's entire desktop. "
    "Your goal is to verify the mouse position. The user is also running a coordinate app. "
    "1. Find the mouse cursor (the pointer). What are its (x, y) coordinates? "
    "2. Find the coordinate application window (it has text like 'Physical', 'Scaled'). "
    "3. Read the 'Physical' X and Y coordinates from that app. "
    "4. The system reports the mouse is at ({x}, {y}). Do the cursor's position and the app's 'Physical' coordinates BOTH closely match this system coordinate? "
    "Respond ONLY with JSON: "
    "{{\"cursor_x\": <found_cursor_x>, \"cursor_y\": <found_cursor_y>, \"app_x\": <read_app_x>, \"app_y\": <read_app_y>, \"match\": <true_or_false>, \"reason\": \"<your_analysis>\"}}"
)

# -------------------------------------------

# --- v2.9.4: UI Helper Functions ---
def create_topmost_root():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root

def show_info_popup(title, message):
    root = create_topmost_root()
    messagebox.showinfo(title, message, parent=root)
    root.destroy()

def ask_text_popup(title, prompt):
    root = create_topmost_root()
    result = simpledialog.askstring(title, prompt, parent=root)
    root.destroy()
    return result

def ask_yes_no_popup(title, question):
    root = create_topmost_root()
    result = messagebox.askyesno(title, question, parent=root)
    root.destroy()
    return result
# --- End v2.9.4 ---


def take_screenshot_mss(mode='full', x=0, y=0, width=64, height=64):
    """
    Takes a screenshot using mss.
    - 'full': Captures all monitors.
    - 'crop': Captures a small area around (x, y).
    Returns (image_bytes, save_path)
    """
    try:
        with mss.mss() as sct:
            if mode == 'full':
                print("[EYES] Capturing full screen...")
                # Grab all monitors combined
                sct_img = sct.grab(sct.monitors[0])
                save_path = SCREENSHOT_FILE_FULL
            else: # mode == 'crop'
                print(f"[EYES] Capturing crop at ({x}, {y})...")
                monitor = {
                    "top": y - (height // 2),
                    "left": x - (width // 2),
                    "width": width,
                    "height": height,
                }
                sct_img = sct.grab(monitor)
                save_path = SCREENSHOT_FILE_CROP
            
            img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            
            with open(save_path, "wb") as f:
                f.write(img_bytes)
            print(f"[EYES] Screenshot saved to: {save_path}")
            
            return img_bytes, save_path
            
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot with mss: {e}")
        return None, None

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
            mmproj_path=MMPROJ_PATH, 
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

def verify_coordinates_with_ai(img_bytes, x, y):
    """
    Asks the AI to find the mouse and coord app in a full screenshot.
    """
    print(f"[TEACHER] Asking AI to verify coordinates ({x}, {y})...")
    try:
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        image_uri = f"data:image/png;base64,{img_base64}"
        
        prompt = VISION_PROMPT_VERIFY_COORDS.format(x=x, y=y)
        
        messages = [
            {"role": "user",
             "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_uri}}
             ]}
        ]
    
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=256 # Increased for the JSON response
        )
        
        response_text = response['choices'][0]['message']['content'].strip()
        print(f"[TEACHER] AI Verification Response Text: {response_text}")

        # Extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            print("[TEACHER] AI did not return valid JSON for verification.")
            return False, "AI did not return valid JSON."

        data = json.loads(json_match.group(0))
        print(f"[TEACHER] AI Verification Data: {data}")
        
        if data.get("match") == True:
            print("[TEACHER] AI verification successful!")
            return True, data.get("reason", "No reason provided.")
        else:
            print("[TEACHER] AI verification failed.")
            return False, data.get("reason", "No reason provided.")

    except Exception as e:
        print(f"[TEACHER] Error during AI verification: {e}")
        return False, str(e)


def get_visual_embedding(img_bytes):
    """
    Gets a visual embedding from a CROPPED image's bytes.
    """
    print(f"[EYES] Generating embedding from cropped image...")
    try:
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        image_uri = f"data:image/png;base64,{img_base64}"
        
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
    print("--- Sentinel School v2.9.5 (Learning Wizard) ---")
    
    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    load_ai_model() 
    
    print("[TEACHER] Welcome to Sentinel School.")
    
    try:
        # 1. Get target label
        target_label = ask_text_popup(
            "Sentinel Teacher",
            "What do you want to teach me? (e.g., 'gemini_copy_button')"
        )
        if not target_label:
            print("Invalid label. Aborting.")
            return
        print(f"[TEACHER] Teaching target: '{target_label}'")

        # 2. Get application context
        show_info_popup(
            "Sentinel Teacher",
            "Please switch to the application window you want to teach me about.\n\nClick 'OK' *after* you have switched."
        )
        app_name, window_title = perceive_environment()
        if not app_name:
            print("Could not identify application. Aborting.")
            return
        print(f"[TEACHER] OK, we are teaching a task in '{app_name}'.")

        # 3. Get mouse position
        show_info_popup(
            "Sentinel Teacher",
            f"Please move your mouse *exactly* over the '{target_label}' button.\n"
            "Also, ensure your 'Mouse Coord' app is visible.\n\n"
            "Click 'OK' *after* your mouse is in position."
        )
        x, y = pyautogui.position()
        print(f"[TEACHER] Got it! Learning coordinates: ({x}, {y})")

        # 4. --- AI VERIFICATION STEP ---
        full_screen_bytes, full_screen_path = take_screenshot_mss(mode='full')
        if not full_screen_bytes:
            raise Exception("Failed to take full screenshot.")

        Image.open(full_screen_path).show()
        is_visible = ask_yes_no_popup(
            "Sentinel Teacher",
            "I've opened the FULL screenshot.\n\nAre your MOUSE CURSOR and COORD APP clearly visible?"
        )
        if not is_visible:
            print("[TEACHER] Aborting. Please make sure both are visible.")
            return

        is_verified, reason = verify_coordinates_with_ai(full_screen_bytes, x, y)
        
        if not is_verified:
            print(f"[TEACHER] AI coordinate verification failed: {reason}")
            show_info_popup("Sentinel Teacher", f"AI VERIFICATION FAILED:\n\n{reason}\n\nAborting.")
            return
        
        print(f"[TEACHER] AI verification successful: {reason}")

        # 5. --- EMBEDDING STEP ---
        crop_bytes, crop_path = take_screenshot_mss(mode='crop', x=x, y=y)
        if not crop_bytes:
            raise Exception("Failed to take cropped screenshot.")

        Image.open(crop_path).show()
        is_correct_target = ask_yes_no_popup(
            "Sentinel Teacher",
            "I've opened the CROPPED screenshot.\n\nIs this the correct image of the target?"
        )
        if not is_correct_target:
            print("[TEACHER] Aborting.")
            return

        embedding = get_visual_embedding(crop_bytes)
        
        if embedding:
            # 6. Store in memory
            print(f"[TEACHER] Learning complete. Storing in memory...")
            memory.store_visual_memory(
                label=target_label,
                embedding=embedding,
                app_name=app_name,
                window_title=window_title,
                x=x,
                y=y,
                notes=f"Taught by user in Sentinel School. AI Verified: {reason}"
            )
            print("\n--- ✅ SUCCESS! ---")
            show_info_popup(
                "Sentinel Teacher",
                f"SUCCESS!\n\nI have learned the '{target_label}' for '{app_name}'."
            )
        else:
            print("[TEACHER] Could not learn target (failed to get embedding).")
            show_info_popup(
                "Sentinel Teacher",
                "FAILED.\n\nCould not learn target (failed to get embedding).\nPlease check the console for errors."
            )

    except KeyboardInterrupt:
        print("\n[TEACHER] Training cancelled.")
    except Exception as e:
        print(f"\n[TEACHER] A critical error occurred: {e}")
    finally:
        # Clean up temp screenshots
        if os.path.exists(SCREENSHOT_FILE_FULL):
            os.remove(SCREENSHOT_FILE_FULL)
        if os.path.exists(SCREENSHOT_FILE_CROP):
            os.remove(SCREENSHOT_FILE_CROP)
        print("Cleanup complete.")
        

if __name__ == "__main__":
    main()