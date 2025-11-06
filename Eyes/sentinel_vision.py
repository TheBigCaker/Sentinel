import sys
import os
import json
import subprocess
import time
import re # <-- THIS IS THE FIX
from PIL import ImageGrab
from llama_cpp import Llama
# We REMOVED Llava15ChatHandler, as Gemma 3 uses a different, auto-detected method

# --- 1. CONFIGURATION (MANUALLY UPDATE) ---

# Updated to the model you are using
MODEL_PATH = r"C:\Dev\Models\gemma-3-4b-it-q4_0.gguf"

# Path to the "Hands" script
CLICKER_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "click_at_position.py")

# The prompt for PaliGemma.
# We are asking it to find the 'Copy' icon and give us its coordinates.
# This prompt is a "best guess" for Gemma 3. We may need to tune it.
VISION_PROMPT = "USER: [Image]Look at this screenshot. Find the icon that means 'Copy'. What are its center coordinates? Respond ONLY with JSON: {\"x\": <center_x>, \"y\": <center_y>}"

# Path for the temporary screenshot (fixed SyntaxWarning)
SCREENSHOT_FILE = r"C:\Dev\Sentinel\_temp_screenshot.png"

# -------------------------------------------

def get_clipboard_content():
    """Uses PowerShell to get clipboard content (more reliable)."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except Exception as e:
        print(f"[ERROR] Could not get clipboard content: {e}")
        return None

def run_clicker_script(x, y):
    """
    This function has a critical security flaw! It is vulnerable to
    Command Injection because it formats strings directly into a shell command.
    DO NOT use this in a real application.
    
    For this demo, it reads the clicker script, replaces the coordinates,
    and executes it.
    """
    print(f"[HANDS] Activating 'click_at_position.py' with coords ({x}, {y})...")
    
    try:
        with open(CLICKER_SCRIPT_PATH, 'r') as f:
            script_content = f.read()
        
        # Replace the hard-coded coordinates in the script template
        script_content = script_content.replace("TARGET_X = 100", f"TARGET_X = {x}")
        script_content = script_content.replace("TARGET_Y = 100", f"TARGET_Y = {y}")
        
        # Create a temporary script to run
        temp_script_path = "_temp_clicker.py"
        with open(temp_script_path, 'w') as f:
            f.write(script_content)
            
        # Run the temporary script
        subprocess.run(["python", temp_script_path], check=True)
        
        # Clean up
        os.remove(temp_script_path)
        return True
        
    except Exception as e:
        print(f"[HANDS] Error: Could not run clicker script: {e}")
        return False

def main():
    print("--- Sentinel Vision v1.1 (Gemma 3) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        print("Please download the PaliGemma GGUF model and update the MODEL_PATH variable.")
        sys.exit(1)
        
    # --- 1. THE "BRAIN": Give user time to switch windows ---
    print("Giving you 3 seconds to switch to the target window...")
    print("3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)

    # --- 2. THE "EYES": Take screenshot ---
    print("Taking screenshot...")
    try:
        img = ImageGrab.grab()
        img.save(SCREENSHOT_FILE)
        print(f"Screenshot saved to {SCREENSHOT_FILE}")
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return
    # --- 3. THE "EYES": Load Gemma 3 and analyze ---
    print(f"[EYES] Loading Gemma 3 model... (This may take a moment)")
    try:
        # We REMOVED the chat_handler. llama-cpp-python will auto-detect
        # the 'gemma3' chat format from the GGUF file's metadata.
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            logits_all=True,
            n_batch=512,
            verbose=True # Added for more detailed output
        )
        print("[EYES] Model loaded.")
        
        # Create the vision prompt
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that responds in JSON."
            },
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
        
        # Clean up the screenshot
        os.remove(SCREENSHOT_FILE)
        
        # Parse the JSON response
        # We will try to find the JSON block, even if the model adds extra text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError("AI did not respond with valid JSON.")
            
        coords = json.loads(json_match.group(0))
        x = int(coords['x'])
        y = int(coords['y'])
        
        if x <= 0 or y <= 0:
            raise ValueError("Invalid coordinates received from AI.")
            
    except Exception as e:
        print(f"[EYES] Error: Failed to analyze image: {e}")
        print("This may be due to a bad model path, llama-cpp-python install issue, or the AI not returning valid JSON.")
        return

    # --- 4. THE "HANDS": Activate clicker ---
    print(f"[BRAIN] AI found the 'Copy' button at ({x}, {y}).")
    
    # Get clipboard content *before* clicking
    content_before = get_clipboard_content()
    
    if not run_clicker_script(x, y):
        return
        
    # --- 5. THE "BRAIN": Verify and Save ---
    print("[BRAIN] Verifying clipboard content...")
    time.sleep(1) # Give clipboard time to update
    
    content_after = get_clipboard_content()
    
    if not content_after:
        print("[ERROR] Failed to get new clipboard content.")
        return
        
    if content_after == content_before:
        print("[ERROR] Clipboard content did not change. Click may have failed.")
        return
        
    print("[SUCCESS] New content detected on clipboard!")
    
    # --- DANGER ZONE: This is where you would save the content ---
    #
    # We will save it to a temporary file for this demo.
    # In a real workflow, you would paste this into your template.
    #
    output_file = "clipboard_content.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content_after)
        
    print(f"Pasted content saved to '{output_file}'.")
    print("--- Sentinel Vision Run Complete ---")


if __name__ == "__main__":
    main()