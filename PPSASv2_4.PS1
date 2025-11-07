<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Agent v2.4 - Double Bug Fix)
================================================================================
This bootstrapper upgrades our v2.3 agent to v2.4.

It fixes two critical bugs found in the last test run:
1.  [FIX-PS] Defines the missing $memoryFile, $configFile, etc. variables
           to prevent the 'Test-Path is null' error.
2.  [FIX-PY] Escapes the JSON curly braces {} in the agent's prompts
           to prevent the Python 'KeyError'.
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Agent"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Fix: Agent v2.4 (Fix PS bootstrapper and PY prompt bugs)"

# --- v2.4 FIX: Define ALL file variables ---
$agentFile = "sentinel_agent.py"
$memoryFile = "sentinel_memory.py"
$configFile = "sentinel_config.json"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for sentinel_agent.py (v2.4 - The "Brain") ---
$agentScript = @"
import sys
import os
import json
import re
import time
from PIL import Image, ImageGrab
from llama_cpp import Llama
import pyautogui
import pyperclip
import sentinel_memory
import pygetwindow as gw
import psutil

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
    llm = None # v2.3: AI model will be loaded in main()
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# --- 2. PROMPTS (v2.4 - Escaped Braces Fix) ---
VISION_PROMPT_FIND = (
    "USER: [Image]Look at this screenshot of a computer screen. "
    "I am looking for the <{target_description}>. "
    "What are its absolute center (x, y) coordinates? "
    "Respond ONLY with JSON: {{\"x\": <center_x>, \"y\": <center_y>}}"
)

VISION_PROMPT_GET_EMBEDDING = (
    "USER: [Image]Look at this small, cropped image of a user interface element. "
    "Generate a vector embedding for this image."
)

# -------------------------------------------

def get_full_screenshot_path():
    return os.path.join(DB_PATH, SCREENSHOT_FILE)

def take_screenshot(bbox=None):
    """Takes a screenshot. If bbox is provided, crops to that region."""
    full_path = get_full_screenshot_path()
    print(f"Taking screenshot... saving to {full_path}")
    try:
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        img.save(full_path)
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
        print(f"[PERCEIVE] App: {app_name}, Title: {title}")
        return app_name, title
    except Exception as e:
        print(f"[PERCEIVE] Error: Could not get active window: {e}")
        return None, None

# --- v2.3: "EYES" FUNCTIONS ---

def load_ai_model():
    """Loads the Llama model into memory."""
    global llm
    if llm:
        return # Already loaded
        
    print(f"[EYES] Loading model... (This may take a moment)")
    try:
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_batch=512,
            logits_all=True,    # Needed for get_visual_embedding
            embedding=True,     # Needed for get_visual_embedding
            verbose=False
        )
        print("[EYES] Model loaded successfully.")
    except Exception as e:
        print(f"[EYES] CRITICAL ERROR: Failed to load model: {e}")
        sys.exit(1)

def find_target_on_screen(target_label, target_description):
    """
    Takes a full-screen screenshot, asks the AI to find the target,
    and returns the (x, y) coordinates.
    """
    print(f"[EYES] Scanning for target: '{target_label}'...")
    screenshot_path = take_screenshot() # Full screen
    if not screenshot_path:
        return None, None
        
    prompt = VISION_PROMPT_FIND.format(target_description=target_description)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant that responds in JSON."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"file://{screenshot_path}"}}
            ]
        }
    ]
    
    try:
        response = llm.create_chat_completion(messages=messages, max_tokens=100)
        response_text = response['choices'][0]['message']['content'].strip()
        print(f"[EYES] AI Response: {response_text}")
        
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            print("[EYES] Error: AI did not respond with valid JSON.")
            return None, None
            
        coords = json.loads(json_match.group(0))
        x, y = int(coords['x']), int(coords['y'])
        
        if x <= 0 or y <= 0:
            raise ValueError(f"Invalid coordinates: ({x}, {y})")
            
        print(f"[EYES] Found '{target_label}' at ({x}, {y}).")
        return x, y
        
    except Exception as e:
        print(f"[EYES] Error during screen analysis: {e}")
        return None, None

def get_visual_embedding(x, y):
    """
    Takes a small, focused screenshot of a *known* target
    and returns its vector embedding to be stored in memory.
    """
    print(f"[EYES] Learning target at ({x}, {y})...")
    # Take a small 64x64 screenshot centered on the target
    crop_box = (x - 32, y - 32, x + 32, y + 32)
    screenshot_path = take_screenshot(bbox=crop_box)
    if not screenshot_path:
        return None
        
    prompt = VISION_PROMPT_GET_EMBEDDING # No .format needed
    
    messages = [
        {"role": "user",
         "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"file://{screenshot_path}"}}
         ]}
    ]
    
    try:
        # Ask the model to generate an embedding for the image
        response = llm.create_chat_completion(messages=messages, max_tokens=1)
        
        # The embedding is not in 'choices', but on the response object itself
        if hasattr(response, 'embedding'):
            embedding = response.embedding
            print(f"[EYES] Successfully generated embedding for target.")
            return embedding
        else:
            print("[EYES] Error: Model did not return an embedding.")
            return None
            
    except Exception as e:
        print(f"[EYES] Error generating embedding: {e}")
        return None

# -------------------------------------------

def main():
    print("--- Sentinel Agent v2.4 (Brain + Memory + Learning) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)

    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    load_ai_model() # v2.3: Load the AI model on start
    
    print("[BRAIN] Sentinel Agent v2.4 initialized.")
    print("This agent will now attempt to find and learn a target.")
    
    # --- v2.3: THE NEW AGENT LOOP ---
    
    # 1. Define our goal for this test
    TARGET_LABEL = "gemini_copy_button"
    TARGET_APP = "chrome.exe"
    TARGET_DESC = "Copy contents' button in the Gemini chat interface"
    
    print(f"\n--- GOAL: Find '{TARGET_LABEL}' in '{TARGET_APP}' ---")
    
    # 2. Perceive environment
    print("You have 3 seconds to switch to the target window (Google Gemini)...")
    time.sleep(3)
    app_name, window_title = perceive_environment()
    
    if not app_name:
        print("[BRAIN] Perception failed. Cannot continue.")
        return
        
    if app_name != TARGET_APP:
        print(f"[BRAIN] Active app is '{app_name}', not '{TARGET_APP}'. Aborting test.")
        return
        
    # 3. Retrieve Memory
    print(f"\n--- RETRIEVING MEMORY for '{TARGET_LABEL}' ---")
    fact = memory.retrieve_fact_memory(TARGET_LABEL, app_name)
    
    if fact:
        print(f"SUCCESS: Found memory for '{TARGET_LABEL}'!")
        print(f"  > Last Known Coords: ({fact.last_known_x}, {fact.last_known_y})")
        # TODO: Add verification logic here.
        # "Go to (x,y), take a small picture, and verify it matches
        # the vector in ChromaDB with id=fact.chroma_id"
    else:
        # 4. LEARN (The "Troubleshoot" Step)
        print(f"[BRAIN] No memory found for '{TARGET_LABEL}'.")
        print(f"Initiating full-screen scan to find and learn target...")
        
        x, y = find_target_on_screen(TARGET_LABEL, TARGET_DESC)
        
        if x and y:
            # 5. STORE
            print(f"[BRAIN] Target found! Now learning what it looks like...")
            embedding = get_visual_embedding(x, y)
            
            if embedding:
                print(f"[BRAIN] Learning complete. Storing in memory...")
                memory.store_visual_memory(
                    label=TARGET_LABEL,
                    embedding=embedding,
                    app_name=app_name,
                    window_title=window_title,
                    x=x,
                    y=y,
                    notes=f"First time learning {TARGET_LABEL}"
                )
            else:
                print("[BRAIN] Could not learn target (failed to get embedding).")
        else:
            print("[BRAIN] Full-screen scan failed. Could not find target.")

if __name__ == "__main__":
    main()
"@

# --- Content for sentinel_memory.py (No changes from v2.2) ---
$memoryScript = Get-Content -Raw -Path "$projectRoot\sentinel_memory.py"

# --- Content for sentinel_config.json (No changes) ---
$configJson = Get-Content -Raw -Path "$projectRoot\sentinel_config.json"

# --- Content for requirements.txt (No changes from v2.2) ---
$requirementsContent = Get-Content -Raw -Path "$projectRoot\requirements.txt"

# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

Write-Host "--- Upgrading Sentinel Agent to v2.4 (Double Bug Fix) ---"

# Create the Agent "Brain"
Write-Host "Updating '$agentFile' to v2.4..."
New-Item -Path $agentFile -ItemType File -Value $agentScript -Force | Out-Null

# Verify other files exist (no need to change them)
Write-Host "Verifying other v2.2 files..."
if (-not (Test-Path $memoryFile)) {
    Write-Error "ERROR: '$memoryFile' is missing. Cannot upgrade."
    exit 1
}
if (-not (Test-Path $configFile)) {
    Write-Error "ERROR: '$configFile' is missing. Cannot upgrade."
    exit 1
}
if (-not (Test-Path $requirementsFile)) {
    Write-Error "ERROR: '$requirementsFile' is missing. Cannot upgrade."
    exit 1
}

Write-Host "--- 'Sentinel Agent' v2.4 Upgrade Complete ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $agentFile
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL AGENT v2.4 UPGRADE COMPLETE!" -ForegroundColor Green
Write-Host "The 'Brain' and 'Prompts' have been patched."
Write-Host "Next steps:"
Write-Host "1. (No new installs needed)"
Write-Host "2. Run 'python sentinel_agent.py'."
Write-Host "3. Switch to your Google Gemini window during the 3-sec pause."
Write-Host "4. Watch the agent (hopefully) find, learn, and store the button!"
Write-Host "---"