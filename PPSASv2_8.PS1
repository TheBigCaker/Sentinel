<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Agent v2.8 - "Dual Fix")
================================================================================
This bootstrapper upgrades our v2.7 "School" to v2.8.

It fixes TWO critical bugs:
1.  [FIX-PY] The `(x, y)` coordinate bug: Replaces `ImageGrab` with `mss`,
           which fully supports multi-monitor setups and negative coordinates.
2.  [FIX-PY] The `image_url` bug: Stops using `file:///` URIs. It now
           converts the screenshot to Base64 and injects the raw data
           directly into the prompt. This is a much more robust method.
3.  [ADD] requirements.txt: Adds the `mss` dependency.
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Agent"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Fix: Agent v2.8 (Implement mss + base64)"

# Define the filenames
$agentFile = "sentinel_agent.py"
$schoolFile = "sentinel_school.py" # The new "Teacher"
$memoryFile = "sentinel_memory.py"
$configFile = "sentinel_config.json"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for sentinel_agent.py (v2.6 - The "Worker") ---
# (No changes to the agent, it's already correct)
$agentScript = Get-Content -Raw -Path "$projectRoot\sentinel_agent.py"

# --- Content for sentinel_school.py (v2.8 - The "Teacher") ---
$schoolScript = @"
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
import mss               # <-- v2.8: Import mss
import base64            # <-- v2.8: Import base64
import io                # <-- v2.8: Import io

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

def take_screenshot_mss(x, y, width=64, height=64):
    """
    Takes a small, focused screenshot using mss.
    v2.8: This handles multi-monitor and negative coordinates.
    """
    full_path = get_full_screenshot_path()
    try:
        with mss.mss() as sct:
            # Define the capture region centered on (x, y)
            monitor = {
                "top": y - (height // 2),
                "left": x - (width // 2),
                "width": width,
                "height": height,
            }
            
            # Grab the data
            sct_img = sct.grab(monitor)
            
            # Save to an in-memory buffer
            img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            print(f"[EYES] Screenshot captured in memory.")
            
            # --- v2.8: Convert to Base64 ---
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            print(f"[EYES] Image converted to Base64.")
            
            # Optional: Save to disk for debugging
            # with open(full_path, "wb") as f:
            #     f.write(img_bytes)
            # print(f"Screenshot saved to {full_path}")
            
            return img_base64
            
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
    v2.8 FIX: Uses mss and base64 data URI
    """
    print(f"[EYES] Learning target at ({x}, {y})...")
    
    # 1. Get the base64-encoded image data
    image_base64 = take_screenshot_mss(x, y)
    if not image_base64:
        return None
        
    try:
        # 2. Format as a data URI
        image_uri = f"data:image/png;base64,{image_base64}"
        
        print(f"[EYES] Generating embedding from data URI...")
        
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
    print("--- Sentinel School v2.8 (Learning Wizard) ---")
    
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
"@

# --- Content for sentinel_memory.py (No changes) ---
$memoryScript = Get-Content -Raw -Path "$projectRoot\sentinel_memory.py"

# --- Content for sentinel_config.json (No changes) ---
$configJson = Get-Content -Raw -Path "$projectRoot\sentinel_config.json"

# --- Content for requirements.txt (v2.8 - ADDS mss) ---
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
mss

#For "Sentinel Agent" (RPA / "Memory")
chromadb
peewee

#For "Sentinel Agent" (RPA / "Perception")
pygetwindow
psutil
pywin32
"@

# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

Write-Host "--- Upgrading Sentinel Agent to v2.8 (mss + base64 Fix) ---"

# Update the "Teacher"
Write-Host "Updating '$schoolFile' to v2.8..."
New-Item -Path $schoolFile -ItemType File -Value $schoolScript -Force | Out-Null

# Update requirements.txt
Write-Host "Updating '$requirementsFile' (adding mss)..."
New-Item -Path $requirementsFile -ItemType File -Value $requirementsContent -Force | Out-Null

# Verify other files exist
Write-Host "Verifying other v2.6 files..."
if (-not (Test-Path $agentFile)) {
    Write-Error "ERROR: '$agentFile' is missing. Cannot upgrade."
    exit 1
}
if (-not (Test-Path $memoryFile)) {
    Write-Error "ERROR: '$memoryFile' is missing. Cannot upgrade."
    exit 1
}
if (-not (Test-Path $configFile)) {
    Write-Error "ERROR: '$configFile' is missing. Cannot upgrade."
    exit 1
}

Write-Host "--- 'Sentinel Agent' v2.8 Upgrade Complete ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $schoolFile
git add $requirementsFile
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL AGENT v2.8 UPGRADE COMPLETE!" -ForegroundColor Green
Write-Host "The 'sentinel_school.py' script has been patched."
Write-Host "This version uses 'mss' (for multi-monitor) and 'base64' (for image data)."
Write-Host "Next steps:"
Write-Host "1. Run 'pip install -r requirements.txt' (This will install mss)"
Write-Host "2. Run 'python sentinel_school.py' to TEACH the agent."
Write-Host "3. This should *finally* work."
Write-Host "---"