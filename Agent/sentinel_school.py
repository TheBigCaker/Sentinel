import sys
import os
import json
import time
from PIL import Image, ImageDraw
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
import re 
import ctypes
from ctypes import wintypes

# --- v3.0.0: MPos Integration ---
# Make the script DPI-Aware (like MPos.exe)
# This is the most critical fix.
try:
    # SetProcessDpiAwareness(2) = PROCESS_PER_MONITOR_DPI_AWARE
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    print("[INIT] SetProcessDpiAwareness(2) successful. (Per-Monitor DPI-Aware)")
except Exception as e:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        print("[INIT] SetProcessDPIAware() successful. (System DPI-Aware)")
    except Exception as e2:
        print(f"[INIT] WARNING: Could not set DPI awareness: {e} / {e2}")

# v3.0.1: RE-ADD PYWIN32 CHECK (was accidentally deleted)
try:
    import win32process
    import win32gui
    PYWIN32_INSTALLED = True
except ImportError:
    PYWIN32_INSTALLED = False
    print("[INIT] WARNING: 'pywin32' not found. App/window perception may fail on Windows.")
    print("[INIT] Please run: pip install pywin32")

# v3.0.0: Replacement for pyautogui.position()
def get_true_mouse_position():
    """
    Uses Win32 GetCursorPos to get the true, unscaled physical
    coordinates of the mouse, bypassing pyautogui's scaling issues.
    """
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
        
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)
# --- End v3.0.0 ---


# --- 1. CONFIGURATION (Loaded from JSON) ---
try:
    with open('sentinel_config.json', 'r') as f:
        config = json.load(f)
    
    MODEL_PATH = config['model_path']
    MMPROJ_PATH = config['mmproj_path']
    DB_PATH = config['db_path']
    # v2.9.9: Three temp files
    SCREENSHOT_FILE_READ_COORDS = os.path.join(DB_PATH, "_temp_screenshot_read_coords.png") # Not used in v3.0.0
    SCREENSHOT_FILE_FULL = os.path.join(DB_PATH, "_temp_screenshot_full_marked.png")
    SCREENSHOT_FILE_CROP = os.path.join(DB_PATH, "_temp_screenshot_crop.png")
    
    memory = sentinel_memory.Memory(DB_PATH)
    llm = None
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# --- 2. PROMPTS (v3.0.0) ---
VISION_PROMPT_GET_EMBEDDING = (
    "USER: [Image]Look at this small, cropped image of a user interface element. "
    "Generate a vector embedding for this image."
)

# v2.9.9: This prompt is no longer needed as we use get_true_mouse_position()
# VISION_PROMPT_READ_COORDS = ...

VISION_PROMPT_VERIFY_COORDS = (
    "USER: [Image]Look at this screenshot of a user's entire desktop. "
    "A large, red 'X' has been drawn to mark the user's mouse position. "
    "Your goal is to verify this position. The user is also running a coordinate app. "
    "1. Find the center of the large red 'X' marker. What are its (x, y) coordinates? "
    "2. Find the coordinate application window (it has text like 'Physical', 'Scaled'). "
    "3. Read the 'Physical' X and Y coordinates from that app. "
    "4. The system reports the marker is at ({x}, {y}). Do the 'X' position and the app's 'Physical' coordinates BOTH closely match this system coordinate? "
    "Respond ONLY with JSON: "
    "{{\"marker_x\": <found_marker_x>, \"marker_y\": <found_marker_y>, \"app_x\": <read_app_x>, \"app_y\": <read_app_y>, \"match\": <true_or_false>, \"reason\": \"<your_analysis>\"}}"
)

# -------------------------------------------

# --- v3.0.0: UI Helper Functions (with positioning) ---
def create_topmost_root(x=None, y=None):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    # v3.0.0: Position the pop-up
    if x is not None and y is not None:
        # Position the window near the mouse, but offset
        # so it doesn't cover the target
        pos_x = x + 50
        pos_y = y + 50
        root.geometry(f"+{pos_x}+{pos_y}")
    return root

def show_info_popup(title, message, x=None, y=None):
    root = create_topmost_root(x, y)
    messagebox.showinfo(title, message, parent=root)
    root.destroy()

def ask_text_popup(title, prompt, x=None, y=None):
    root = create_topmost_root(x, y)
    result = simpledialog.askstring(title, prompt, parent=root)
    root.destroy()
    return result

def ask_yes_no_popup(title, question, x=None, y=None):
    root = create_topmost_root(x, y)
    result = messagebox.askyesno(title, question, parent=root)
    root.destroy()
    return result
# --- End v3.0.0 UI ---


def take_and_process_screenshots(x, y, crop_width=64, crop_height=64):
    """
    v2.9.8: "One Grab, Two Crops"
    Takes ONE screenshot, draws the 'X', and generates both
    the full image and the cropped image using PIL.
    """
    try:
        with mss.mss() as sct:
            # 1. Grab the entire virtual screen
            print("[EYES] Capturing full virtual screen...")
            monitor_bbox = sct.monitors[0]
            sct_img = sct.grab(monitor_bbox)
            
            # 2. Convert to PIL Image
            pil_img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            draw = ImageDraw.Draw(pil_img)

            # 3. Draw the "X" marker
            # Adjust coords from absolute virtual screen to relative PIL image coords
            draw_x = x - monitor_bbox["left"]
            draw_y = y - monitor_bbox["top"]
            
            size = 30
            color = (255, 0, 0) # Bright red
            stroke_width = 5
            
            print(f"[EYES] Drawing 'X' at relative image coords ({draw_x}, {draw_y})...")
            draw.line((draw_x - size, draw_y - size, draw_x + size, draw_y + size), fill=color, width=stroke_width)
            draw.line((draw_x + size, draw_y - size, draw_x - size, draw_y + size), fill=color, width=stroke_width)

            # 4. Save the FULL marked-up image to bytes
            print("[EYES] Saving full image to bytes...")
            full_img_byte_arr = io.BytesIO()
            pil_img.save(full_img_byte_arr, format='PNG')
            full_img_bytes = full_img_byte_arr.getvalue()
            with open(SCREENSHOT_FILE_FULL, "wb") as f:
                f.write(full_img_bytes)
            print(f"[EYES] Full screenshot saved to: {SCREENSHOT_FILE_FULL}")

            # 5. CROP the PIL image
            print(f"[EYES] Cropping image at relative coords ({draw_x}, {draw_y})...")
            crop_box = (
                draw_x - (crop_width // 2),
                draw_y - (crop_height // 2),
                draw_x + (crop_width // 2),
                draw_y + (crop_height // 2)
            )
            pil_crop = pil_img.crop(crop_box)

            # 6. Save the CROP image to bytes
            print("[EYES] Saving cropped image to bytes...")
            crop_img_byte_arr = io.BytesIO()
            pil_crop.save(crop_img_byte_arr, format='PNG')
            crop_img_bytes = crop_img_byte_arr.getvalue()
            with open(SCREENSHOT_FILE_CROP, "wb") as f:
                f.write(crop_img_bytes)
            print(f"[EYES] Cropped screenshot saved to: {SCREENSHOT_FILE_CROP}")

            # 7. Return everything
            return (full_img_bytes, SCREENSHOT_FILE_FULL, 
                    crop_img_bytes, SCREENSHOT_FILE_CROP)

    except Exception as e:
        print(f"[EYES] Error: Could not take/process screenshots: {e}")
        return None, None, None, None


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


def get_coordinates_from_ai(img_bytes):
    """
    v2.9.9: This function is no longer needed in v3.0.0
    """
    pass


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
    print("--- Sentinel School v3.0.1 (Learning Wizard) ---")
    
    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    load_ai_model() 
    
    # v3.0.0: Get initial mouse pos for first pop-up
    current_x, current_y = get_true_mouse_position()
    print("[TEACHER] Welcome to Sentinel School.")
    
    try:
        # 1. Get target label
        target_label = ask_text_popup(
            "Sentinel Teacher",
            "What do you want to teach me? (e.g., 'gemini_copy_button')",
            x=current_x, y=current_y
        )
        if not target_label:
            print("Invalid label. Aborting.")
            return
        print(f"[TEACHER] Teaching target: '{target_label}'")

        # 2. Get application context
        current_x, current_y = get_true_mouse_position()
        show_info_popup(
            "Sentinel Teacher",
            "Please switch to the application window you want to teach me about.\n\nClick 'OK' *after* you have switched.",
            x=current_x, y=current_y
        )
        app_name, window_title = perceive_environment()
        if not app_name:
            print("Could not identify application. Aborting.")
            return
        print(f"[TEACHER] OK, we are teaching a task in '{app_name}'.")

        # 3. Get mouse position
        current_x, current_y = get_true_mouse_position()
        show_info_popup(
            "Sentinel Teacher",
            f"Please move your mouse *exactly* over the '{target_label}' button.\n"
            "Also, ensure your 'MPos' coordinate app is visible.\n\n"
            "Click 'OK' *after* your mouse is in position.",
            x=current_x, y=current_y
        )
        
        # v3.0.0: Use our new reliable function
        x, y = get_true_mouse_position() 
        print(f"[TEACHER] Got TRUE physical coordinates: ({x}, {y})")

        # 4. --- AI-FIRST COORDINATE READ (Skipped in v3.0.0) ---
        # We now trust our get_true_mouse_position() function
        print(f"[TEACHTCH] Trusting local physical coordinates. Proceeding to AI verification.")


        # 5. --- AI VERIFICATION STEP ---
        (full_screen_bytes, full_screen_path, 
         crop_bytes, crop_path) = take_and_process_screenshots(x=x, y=y)
        
        if not full_screen_bytes:
            raise Exception("Failed to take screenshots.")

        Image.open(full_screen_path).show()
        is_visible = ask_yes_no_popup(
            "Sentinel Teacher",
            "I've opened the SECOND screenshot.\n\nIs the RED 'X' on the correct target?\nIs the MPos app also visible?",
            x=x, y=y
        )
        if not is_visible:
            print("[TEACHER] Aborting. The 'X' was not on target or MPos was not visible.")
            return
            
        # v3.0.0: Re-enabled verification
        is_verified, reason = verify_coordinates_with_ai(full_screen_bytes, x, y)
        if not is_verified:
           print(f"[TEACHER] AI coordinate verification failed: {reason}")
           show_info_popup("Sentinel Teacher", f"AI VERIFICATION FAILED:\n\n{reason}\n\nAborting.", x=x, y=y)
           return
        print(f"[TEACHER] AI verification successful: {reason}")


        # 6. --- EMBEDDING STEP ---
        Image.open(crop_path).show()
        is_correct_target = ask_yes_no_popup(
            "Sentinel Teacher",
            "I've opened the CROPPED screenshot.\n\nIs this the correct image of the target?",
            x=x, y=y
        )
        if not is_correct_target:
            print("[TEACHER] Aborting.")
            return

        embedding = get_visual_embedding(crop_bytes)
        
        if embedding:
            # 7. Store in memory
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
                f"SUCCESS!\n\nI have learned the '{target_label}' for '{app_name}'.",
                x=x, y=y
            )
        else:
            print("[TEACHER] Could not learn target (failed to get embedding).")
            show_info_popup(
                "Sentinel Teacher",
                "FAILED.\n\nCould not learn target (failed to get embedding).\nPlease check the console for errors.",
                x=x, y=y
            )

    except KeyboardInterrupt:
        print("\n[TEACHER] Training cancelled.")
    except Exception as e:
        print(f"\n[TEACHER] A critical error occurred: {e}")
    finally:
        # Clean up temp screenshots
        if os.path.exists(SCREENSHOT_FILE_READ_COORDS):
            os.remove(SCREENSHOT_FILE_READ_COORDS)
        if os.path.exists(SCREENSHOT_FILE_FULL):
            os.remove(SCREENSHOT_FILE_FULL)
        if os.path.exists(SCREENSHOT_FILE_CROP):
            os.remove(SCREENSHOT_FILE_CROP)
        print("Cleanup complete.")
        

if __name__ == "__main__":
    main()