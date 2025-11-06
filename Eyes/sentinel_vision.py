import sys
import os
import json
import re
import time
from PIL import ImageGrab
from llama_cpp import Llama
import pyautogui  # <-- "Hands" are now imported directly
import pyperclip  # <-- A better way to get clipboard content

# --- 1. CONFIGURATION (MANUALLY UPDATE) ---

MODEL_PATH = r"C:\Dev\Models\gemma-3-4b-it-q4_0.gguf"

# A more specific prompt
VISION_PROMPT = "USER: [Image]Look at this screenshot of an application. Find the 'Copy' icon that is inside a code block, on the right-hand side. What are its center coordinates? Respond ONLY with JSON: {\"x\": <center_x>, \"y\": <center_y>}"

SCREENSHOT_FILE = r"C:\Dev\Sentinel\_temp_screenshot.png"
OUTPUT_CLIPBOARD_FILE = "clipboard_content.txt"

# -------------------------------------------

def click_at_position(x, y):
    """
    The "Hands" function, now part of the main script.
    """
    print(f"[HANDS] Activating with coords ({x}, {y})...")
    try:
        print(f"Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.25)
        
        print("Clicking...")
        pyautogui.click()
        
        print("--- Click Complete ---")
        return True
    except Exception as e:
        print(f"[HANDS] Error: Could not run clicker: {e}")
        return False

def main():
    print("--- Sentinel Vision v1.3 (Merged + Cropping) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)
        
    # --- 1. THE "BRAIN": Give user time to switch windows ---
    print("Giving you 3 seconds to switch to the target window...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    # --- 2. THE "EYES": Take CROPPED screenshot ---
    print("Taking screenshot (right half of screen)...")
    try:
        screen_width, screen_height = pyautogui.size()
        
        # Define the crop box: (left, top, right, bottom)
        # This captures only the right half of the screen.
        left = screen_width // 2
        top = 0
        right = screen_width
        bottom = screen_height
        
        img = ImageGrab.grab(bbox=(left, top, right, bottom))
        img.save(SCREENSHOT_FILE)
        print(f"Screenshot saved to {SCREENSHOT_FILE}")
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return
        
    # --- 3. THE "EYES": Load Gemma 3 and analyze ---
    print(f"[EYES] Loading Gemma 3 model... (This may take a moment)")
    try:
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            logits_all=True,
            n_batch=512,
            verbose=False # Set to True for full logs
        )
        print("[EYES] Model loaded.")
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that responds in JSON."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"file://{SCREENSHOT_FILE}"}}
                ]
            }
        ]
        
        print("[EYES] Analyzing screenshot...")
        response = llm.create_chat_completion(messages=messages, max_tokens=100)
        
        response_text = response['choices'][0]['message']['content'].strip()
        print(f"[EYES] AI Response: {response_text}")
        
        os.remove(SCREENSHOT_FILE)
        
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError("AI did not respond with valid JSON.")
            
        coords = json.loads(json_match.group(0))
        
        # *** CRITICAL FIX ***
        # The AI gives coords *relative* to the cropped image.
        # We must add the 'left' offset back to get the *real* screen coordinate.
        x = int(coords['x']) + left
        y = int(coords['y']) # Y coordinate doesn't change
        
        if x <= left or y <= 0:
            raise ValueError(f"Invalid coordinates received from AI: ({coords['x']}, {coords['y']})")
            
    except Exception as e:
        print(f"[EYES] Error: Failed to analyze image: {e}")
        return

    # --- 4. THE "HANDS": Activate clicker ---
    print(f"[BRAIN] AI found the 'Copy' button at ({x}, {y}).")
    
    # Get clipboard content *before* clicking
    content_before = pyperclip.paste()
    
    if not click_at_position(x, y):
        return
        
    # --- 5. THE "BRAIN": Verify and Save ---
    print("[BRAIN] Verifying clipboard content...")
    time.sleep(1) # Give clipboard time to update
    
    content_after = pyperclip.paste()
    
    if not content_after:
        print("[ERROR] Failed to get new clipboard content.")
        return
        
    if content_after == content_before:
        print("[ERROR] Clipboard content did not change. Click may have failed.")
        return
        
    print("[SUCCESS] New content detected on clipboard!")
    
    with open(OUTPUT_CLIPBOARD_FILE, 'w', encoding='utf-8') as f:
        f.write(content_after)
        
    print(f"Pasted content saved to '{OUTPUT_CLIPBOARD_FILE}'.")
    print("--- Sentinel Vision Run Complete ---")


if __name__ == "__main__":
    main()