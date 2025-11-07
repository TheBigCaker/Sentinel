<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Agent v2.9.1 - The *REAL* "mmproj" Fix)
================================================================================
This bootstrapper makes ONE tiny, critical change to fix the "Golden Retriever"
hallucination bug.

1.  [FIX-JSON] sentinel_config.json: Adds the "mmproj_path" key.
2.  [FIX-PY] sentinel_school.py: Loads the "mmproj_path" from the config.

This *finally* "plugs in the Eyes" of the model.
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Agent"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Fix: Agent v2.9.1 (Actually load mmproj_path)"

# Define the filenames
$agentFile = "sentinel_agent.py"
$schoolFile = "sentinel_school.py"
$memoryFile = "sentinel_memory.py"
$configFile = "sentinel_config.json"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for sentinel_agent.py (v2.6 - The "Worker") ---
# (No changes to the agent, it's already correct)
$agentScript = Get-Content -Raw -Path "$projectRoot\sentinel_agent.py"

# --- Content for sentinel_school.py (v2.9.1 - The "Teacher") ---
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
    MMPROJ_PATH = config['mmproj_path'] # <-- v2.9.1: LOAD MMPROJ PATH
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

# --- 2. PROMPTS (v2.9) ---
VISION_PROMPT_GET_EMBEDDING = (
    "USER: [Image]What is in this image?"
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
            monitor = {
                "top": y - (height // 2),
                "left": x - (width // 2),
                "width": width,
                "height": height,
            }
            sct_img = sct.grab(monitor)
            img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
            print(f"[EYES] Screenshot captured in memory.")
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            print(f"[EYES] Image converted to Base64.")
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
            mmproj_path=MMPROJ_PATH, # <-- v2.9.1: PLUG IN THE "EYES"
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
    """
    print(f"[EYES] Learning target at ({x}, {y})...")
    
    image_base64 = take_screenshot_mss(x, y)
    if not image_base64:
        return None
        
    try:
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
        
        # We need BOTH the embedding AND a text response
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
    print("--- Sentinel School v2.9.1 (Learning Wizard) ---")
    
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

# --- Content for sentinel_config.json (v2.9.1 - ADDS mmproj_path) ---
$configJson = @"
{
    "model_path": "C:\\Dev\\Models\\gemma-3-4b-it-q4_0.gguf",
    "mmproj_path": "C:\\Dev\\Models\\mmproj-model-f16-4B.gguf",
    "db_path": "C:\\Dev\\Sentinel\\Agent\\memory",
    "screenshot_file": "_temp_screenshot.png"
}
"@

# --- Content for requirements.txt (No changes from v2.8) ---
$requirementsContent = Get-Content -Raw -Path "$projectRoot\requirements.txt"

# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

Write-Host "--- Upgrading Sentinel Agent to v2.9.1 ('mmproj' Fix) ---"

# Update the "Teacher"
Write-Host "Updating '$schoolFile' to v2.9.1..."
New-Item -Path $schoolFile -ItemType File -Value $schoolScript -Force | Out-Null

# Update the Config JSON
Write-Host "Updating '$configFile' (correcting 'mmproj_path')..."
New-Item -Path $configFile -ItemType File -Value $configJson -Force | Out-Null

# Verify other files exist
Write-Host "Verifying other v2.8 files..."
if (-not (Test-Path $agentFile)) {
    Write-Error "ERROR: '$agentFile' is missing. Cannot upgrade."
    exit 1
}
if (-not (Test-Path $memoryFile)) {
    Write-Error "ERROR: '$memoryFile' is missing. Cannot upgrade."
    exit 1
}
if (-not (Test-Path $requirementsFile)) {
    Write-Error "ERROR: '$requirementsFile' is missing. Cannot upgrade."
    exit 1
}

Write-Host "--- 'Sentinel Agent' v2.9.1 Upgrade Complete ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $schoolFile
git add $configFile
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL AGENT v2.9.11 UPGRADE COMPLETE!" -ForegroundColor Green
Write-Host "The 'sentinel_school.py' and 'sentinel_config.json' have been patched."
Write-Host "This version *finally* loads the 'mmproj' file."
Write-Host "Next steps:"
Write-Host "1. Run 'python sentinel_school.py' to TEACH the agent."
Write-Host "2. This should fix the 'golden retriever' bug."
Write-Host "---"