<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Vision - EYES) - v1.4
================================================================================
This bootstrapper creates the v1.4 'sentinel_vision.py' orchestrator.

This version:
1. Upgrades the "Brain" to be a 2-step state machine.
2. It now clicks "Share & export", then "Copy contents".
3. Adds separate, specific prompts for each step.
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Eyes"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Feat: Upgrade Vision Brain to 2-step sequence (v1.4)"

# Define the filenames to be created
$visionOrchestratorFile = "sentinel_vision.py"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for sentinel_vision.py (v1.4 - Multi-Step) ---
$visionOrchestratorScript = @"
import sys
import os
import json
import re
import time
from PIL import ImageGrab
from llama_cpp import Llama
import pyautogui
import pyperclip

# --- 1. CONFIGURATION (MANUALLY UPDATE) ---

MODEL_PATH = r"C:\Dev\Models\gemma-3-4b-it-q4_0.gguf"

# --- Multi-Step Prompts ---
VISION_PROMPT_STEP_1 = "USER: [Image]Look at this screenshot of an application. Find the 'Share & export' icon, which looks like three dots or a share symbol, in the top-right of the code area. What are its center coordinates? Respond ONLY with JSON: {\"x\": <center_x>, \"y\": <center_y>}"
VISION_PROMPT_STEP_2 = "USER: [Image]Look at this screenshot of an open menu. Find the 'Copy contents' button. What are its center coordinates? Respond ONLY with JSON: {\"x\": <center_x>, \"y\": <center_y>}"

SCREENSHOT_FILE = r"C:\Dev\Sentinel\_temp_screenshot.png"
OUTPUT_CLIPBOARD_FILE = "clipboard_content.txt"

# -------------------------------------------

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

def take_cropped_screenshot(bbox=None):
    """
    Takes a screenshot. If bbox is provided, crops to that region.
    Default: Right half of the screen.
    """
    print("Taking screenshot...")
    try:
        if not bbox:
            screen_width, screen_height = pyautogui.size()
            # Default to right half of screen
            bbox = (screen_width // 2, 0, screen_width, screen_height)
            
        img = ImageGrab.grab(bbox=bbox)
        img.save(SCREENSHOT_FILE)
        print(f"Screenshot saved to {SCREENSHOT_FILE}")
        return bbox[0] # Return the 'left' offset
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return 0 # Return 0 offset on failure

def find_target_on_screen(llm, prompt, crop_box=None):
    """
    The "Eyes" function. Takes a screenshot, asks the AI, returns coordinates.
    """
    left_offset = take_cropped_screenshot(crop_box)
    
    print(f"[EYES] Analyzing screenshot for prompt: '{prompt.split(']')[1].split('.')[0]}...'")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant that responds in JSON."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"file://{SCREENSHOT_FILE}"}}
            ]
        }
    ]
    
    response = llm.create_chat_completion(messages=messages, max_tokens=100)
    response_text = response['choices'][0]['message']['content'].strip()
    print(f"[EYES] AI Response: {response_text}")
    
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if not json_match:
        raise ValueError("AI did not respond with valid JSON.")
        
    coords = json.loads(json_match.group(0))
    
    # Add the offset back to get the *real* screen coordinate
    x = int(coords['x']) + left_offset
    y = int(coords['y']) # Y coordinate is absolute
    
    if x <= left_offset or y <= 0:
        raise ValueError(f"Invalid coordinates received from AI: ({coords['x']}, {coords['y']})")
        
    return x, y

def main():
    print("--- Sentinel Vision v1.4 (Multi-Step Brain) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)
        
    print("Giving you 3 seconds to switch to the target window...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    # --- Load Model Once ---
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
    except Exception as e:
        print(f"[EYES] Error: Failed to load model: {e}")
        return

    try:
        # --- Get clipboard content *before* any actions ---
        content_before = pyperclip.paste()
    
        # === STEP 1: Find and click 'Share & export' ===
        print("\n--- STEP 1: FINDING 'Share & export' ---")
        x1, y1 = find_target_on_screen(llm, VISION_PROMPT_STEP_1)
        print(f"[BRAIN] AI found 'Share & export' at ({x1}, {y1}).")
        
        if not click_at_position(x1, y1, "Share & export"):
            raise Exception("Failed to click 'Share & export'")
            
        print("[BRAIN] Pausing for menu to open...")
        time.sleep(1) # Give the menu time to animate
        
        # === STEP 2: Find and click 'Copy contents' ===
        print("\n--- STEP 2: FINDING 'Copy contents' ---")
        # We can make the crop box smaller, assuming the menu is near the first click
        # This makes the AI much faster and more accurate.
        # Bounding box: (left, top, right, bottom)
        menu_crop_box = (x1 - 100, y1, x1 + 200, y1 + 200) 
        
        x2, y2 = find_target_on_screen(llm, VISION_PROMPT_STEP_2, crop_box=menu_crop_box)
        print(f"[BRAIN] AI found 'Copy contents' at ({x2}, {y2}).")
        
        if not click_at_position(x2, y2, "Copy contents"):
            raise Exception("Failed to click 'Copy contents'")

        # === STEP 3: Verify and Save ===
        print("\n--- STEP 3: VERIFYING CLIPBOARD ---")
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
        
    except Exception as e:
        print(f"\n--- [BRAIN] A critical error occurred: {e} ---")
    finally:
        if os.path.exists(SCREENSHOT_FILE):
            os.remove(SCREENSHOT_FILE)
        print("Cleanup complete.")


if __name__ == "__main__":
    main()
"@

# --- Content for requirements.txt (No changes, but included) ---
$requirementsContent = @"
#For the Watcher modes
watchdog

#For the Google Drive Watcher
google-api-python-client
google-auth-httplib2
google-auth-oauthlib

#For reading .docx files from Google Drive
python-docx

#For "Sentinel Vision" (RPA / "Hands")
pyautogui
pyperclip

#For "Sentinel Vision" (RPA / "Eyes")
llama-cpp-python[server]
Pillow
"@

# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

Write-Host "--- Generating Sentinel Vision v1.4 (Multi-Step) ---"

# Create the Sentinel Vision Orchestrator
Write-Host "Creating '$visionOrchestratorFile'..."
New-Item -Path $visionOrchestratorFile -ItemType File -Value $visionOrchestratorScript -Force | Out-Null

# Create/Update the requirements.txt file
Write-Host "Updating '$requirementsFile'..."
New-Item -Path $requirementsFile -ItemType File -Value $requirementsContent -Force | Out-Null

# Clean up old files just in case
Write-Host "Cleaning up old 'Hands' files..."
Remove-Item -Path "click_at_position.py" -ErrorAction SilentlyContinue
Remove-Item -Path "get_mouse_position.py" -ErrorAction SilentlyContinue


Write-Host "--- 'Eyes' Orchestrator Created Successfully ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $visionOrchestratorFile
git add $requirementsFile
git add "click_at_position.py" # Stage deletion
git add "get_mouse_position.py" # Stage deletion
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL VISION 'EYES' BOOTSTRAP COMPLETE!" -ForegroundColor Green
Write-Host "The 'sentinel_vision.py' orchestrator has been created (v1.4)."
Write-Host "This version is now a 2-step process."
Write-Host "Run 'python sentinel_vision.py' to test the full 2-click loop!"
Write-Host "---"