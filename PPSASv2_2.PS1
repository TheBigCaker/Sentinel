<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Agent v2.2 - Bug Fixes)
================================================================================
This bootstrapper upgrades our v2.1 framework to v2.2.

It fixes two critical bugs found in the last test run:
1.  [FIX] sentinel_memory.py: Explicitly binds the database to the peewee models.
2.  [FIX] sentinel_agent.py: Uses 'pywin32' to correctly get the PID from HWND.
3.  [ADD] requirements.txt: Adds the 'pywin32' dependency.
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Agent"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Fix: Agent v2.2 (Fix SQLite and PID bugs)"

# Define the filenames to be created
$agentFile = "sentinel_agent.py"
$memoryFile = "sentinel_memory.py"
$configFile = "sentinel_config.json"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for sentinel_agent.py (v2.2 - The "Brain") ---
$agentScript = @"
import sys
import os
import json
import re
import time
from PIL import ImageGrab
from llama_cpp import Llama
import pyautogui
import pyperclip
import sentinel_memory
import pygetwindow as gw # v2.1: Import perception library
import psutil # v2.1: Import process utility

# --- v2.2: Import Windows-specific libraries for PID fix ---
try:
    import win32process
    import win32gui
    PYWIN32_INSTALLED = True
except ImportError:
    PYWIN32_INSTALLED = False
    print("Warning: 'pywin32' not found. Perception may fail on Windows.")
    print("Please run: pip install pywin32")

# --- 1. CONFIGURATION (Loaded from JSON) ---
try:
    with open('sentinel_config.json', 'r') as f:
        config = json.load(f)
    
    MODEL_PATH = config['model_path']
    DB_PATH = config['db_path']
    SCREENSHOT_FILE = config['screenshot_file']
    
    # Initialize the "Memory"
    memory = sentinel_memory.Memory(DB_PATH)
    
except FileNotFoundError:
    print("ERROR: sentinel_config.json not found.")
    sys.exit(1)
except KeyError as e:
    print(f"ERROR: Config file is missing a key: {e}")
    sys.exit(1)

# --- 2. PROMPTS ---
VISION_PROMPT_FIND = "USER: [Image]Scan this screenshot. Find the <{target_description}>. What are its center coordinates? Respond ONLY with JSON: {\"x\": <center_x>, \"y\": <center_y>}"
VISION_PROMPT_VERIFY = "USER: [Image]Look at this small image. Does this image contain a <{target_description}>? Respond ONLY with JSON: {\"answer\": \"yes\" or \"no\"}"

# -------------------------------------------

def get_full_screenshot_path():
    return os.path.join(DB_PATH, SCREENSHOT_FILE)

def take_screenshot(bbox=None):
    """Takes a screenshot. If bbox is provided, crops to that region."""
    full_path = get_full_screenshot_path()
    print(f"Taking screenshot... saving to {full_path}")
    try:
        img = ImageGrab.grab(bbox=bbox, all_screens=True) # v2.1: Grab all screens
        img.save(full_path)
        return full_path
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return None

# --- v2.2: "PERCEIVE" FUNCTION (with PID Fix) ---
def perceive_environment():
    """
    The "Brain's" perception function.
    Determines the currently active application and window.
    """
    print("[PERCEIVE] Analyzing active window...")
    try:
        active_window = gw.getActiveWindow()
        if not active_window:
            print("[PERCEIVE] No active window found.")
            return None, None

        title = active_window.title
        
        # --- v2.2 FIX for Windows PID ---
        # _hWnd is a Window Handle (HWND), not a Process ID (PID)
        # We need to translate it.
        pid = None
        if os.name == 'nt' and PYWIN32_INSTALLED:
            try:
                hwnd = active_window._hWnd
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception as e:
                print(f"[PERCEIVE] pywin32 error: {e}")
        else:
             # Fallback for non-Windows or if pywin32 is missing
             # This is a guess and may be wrong.
             pid = active_window._hWnd 
        # --- End Fix ---
        
        if not pid:
             print(f"[PERCEIVE] Could not determine Process ID for window.")
             return None, None

        process = psutil.Process(pid)
        app_name = process.name()
        
        print(f"[PERCEIVE] App: {app_name}, Title: {title}")
        return app_name, title
        
    except psutil.NoSuchProcess:
         print(f"[PERCEIVE] Error: Process with PID {pid} not found.")
         return None, None
    except Exception as e:
        print(f"[PERCEIVE] Error: Could not get active window: {e}")
        return None, None

def main():
    print("--- Sentinel Agent v2.2 (Brain + Memory + Perception) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)

    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db() # This will now fix the SQLite binding
    
    print("[BRAIN] Sentinel Agent v2.2 initialized.")
    
    # --- v2.2: Run the "Perceive" test ---
    print("\n--- TEST: Running Perception Module ---")
    print("You have 3 seconds to switch to a target window (e.g., Chrome, Notepad)...")
    time.sleep(3)
    
    app_name, window_title = perceive_environment()
    
    if app_name:
        print("\n--- TEST: Retrieving Memory Based on Perception ---")
        # Now we try to retrieve a memory using what we just perceived
        fact = memory.retrieve_fact_memory("test_button", app_name)
        if fact:
            print(f"SUCCESS: Found a memory for {app_name}!")
            print(f"  > Label: {fact.label}, Coords: ({fact.last_known_x}, {fact.last_known_y})")
        else:
            print(f"No memories found for {app_name}.")
            # This is where the agent would decide to do a "full scan"
            # and then call memory.store_visual_memory(...) to learn.
    else:
        print("Perception test failed.")


if __name__ == "__main__":
    main()
"@

# --- Content for sentinel_memory.py (v2.2 - The "Memory") ---
$memoryScript = @"
import sqlite3
import chromadb
import json
import os
from peewee import (Model, SqliteDatabase, CharField, IntegerField, 
                    TextField, ForeignKeyField, DoesNotExist)

# This will hold our ChromaDB and SQLite DB
db = SqliteDatabase(None) # v2.2: Initialize as a proxy
client = None

# --- 1. SQL DATABASE (The "Facts" / "Where") ---
# Defines the structure for our Factual (SQL) memory.

class BaseModel(Model):
    class Meta:
        database = db # v2.2: Point to the proxy

class AppContext(BaseModel):
    """e.g., 'chrome.exe', 'Google Chrome'"""
    app_name = CharField(unique=True)
    window_title = CharField() # Can be a regex later

class VisualFact(BaseModel):
    """
    A fact linking a visual object to its context.
    'This 'copy_button' (a vector in ChromaDB) was last
    seen in the 'chrome.exe' app at (x, y).'
    """
    app_context = ForeignKeyField(AppContext, backref='facts')
    label = CharField() # e.g., 'gemini_copy_button'
    chroma_id = CharField() # The ID of the vector in ChromaDB
    last_known_x = IntegerField()
    last_known_y = IntegerField()
    notes = TextField(null=True)

# --- 2. VECTOR DATABASE (The "Looks" / "What") ---
# Manages the ChromaDB connection for visual memory.

class Memory:
    def __init__(self, db_path):
        self.db_path = db_path
        self.sqlite_file = os.path.join(db_path, 'sentinel_facts.db')
        self.chroma_path = os.path.join(db_path, 'sentinel_visuals')
        
        global db, client
        db.init(self.sqlite_file) # v2.2: Initialize the proxy with the real file path
        
        # We use a persistent client that saves to disk
        client = chromadb.PersistentClient(path=self.chroma_path)
        
        self.visual_collection = None

    def init_db(self):
        """Initializes both databases and creates tables/collections."""
        try:
            # v2.2: The database is already bound, just connect and create.
            db.connect()
            db.create_tables([AppContext, VisualFact])
            print("[Memory] SQLite tables initialized.")
        except Exception as e:
            print(f"[Memory] Error initializing SQLite: {e}")
            
        try:
            # Get or create the collection for visual embeddings
            self.visual_collection = client.get_or_create_collection(
                name="visual_elements",
                metadata={"hnsw:space": "cosine"} # Use cosine distance for search
            )
            print(f"[Memory] ChromaDB collection 'visual_elements' initialized.")
        except Exception as e:
            print(f"[Memory] Error initializing ChromaDB: {e}")

    def store_visual_memory(self, label, embedding, app_name, window_title, x, y, notes=""):
        """
        Stores a new memory, linking both databases.
        This is the main "learning" function.
        """
        if self.visual_collection is None:
            self.init_db()
            
        try:
            # 1. Store the "Fact" in
            app, _ = AppContext.get_or_create(app_name=app_name, defaults={'window_title': window_title})
            
            # Use the label as the ID for simplicity
            chroma_id = f"{app_name}_{label}"
            
            fact, created = VisualFact.get_or_create(
                app_context=app,
                label=label,
                defaults={
                    'chroma_id': chroma_id,
                    'last_known_x': x,
                    'last_known_y': y,
                    'notes': notes
                }
            )
            
            if not created:
                # If it already exists, update its position
                fact.last_known_x = x
                fact.last_known_y = y
                fact.save()
                
            # 2. Store the "Look" in ChromaDB
            self.visual_collection.upsert(
                ids=[chroma_id],
                embeddings=[embedding],
                metadatas=[{"app": app_name, "label": label, "sql_id": fact.id}]
            )
            
            print(f"[Memory] Stored/Updated memory for '{label}' in '{app_name}'.")
            
        except Exception as e:
            print(f"[Memory] Error storing memory: {e}")

    def retrieve_fact_memory(self, label, app_name):
        """
        Retrieves the "Fact" (where) for a given element.
        "Where was the 'copy_button' in 'chrome.exe'?"
        """
        try:
            app = AppContext.get(AppContext.app_name == app_name)
            fact = VisualFact.get(VisualFact.app_context == app, VisualFact.label == label)
            return fact
        except DoesNotExist:
            print(f"[Memory] No fact memory found for '{label}' in '{app_name}'.")
            return None
        except Exception as e:
            print(f"[Memory] Error retrieving fact: {e}")
            return None

    def find_visual_match(self, query_embedding, num_results=1):
        """
        Finds the closest "Look" (what) in the vector database.
        "What element on screen is closest to this embedding?"
        """
        if self.visual_collection is None:
            self.init_db()
            
        try:
            results = self.visual_collection.query(
                query_embeddings=[query_embedding],
                n_results=num_results
            )
            return results
        except Exception as e:
            print(f"[Memory] Error querying ChromaDB: {e}")
            return None
"@

# --- Content for sentinel_config.json (No changes) ---
$configJson = Get-Content -Raw -Path "$projectRoot\sentinel_config.json"

# --- Content for requirements.txt (UPDATED) ---
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

Write-Host "--- Upgrading Sentinel Agent to v2.2 (Bug Fixes) ---"

# Create the Agent "Brain"
Write-Host "Updating '$agentFile' to v2.2..."
New-Item -Path $agentFile -ItemType File -Value $agentScript -Force | Out-Null

# Update the "Memory"
Write-Host "Updating '$memoryFile' to v2.2..."
New-Item -Path $memoryFile -ItemType File -Value $memoryScript -Force | Out-Null

# Create/Update the requirements.txt file
Write-Host "Updating '$requirementsFile' (adding pywin32)..."
New-Item -Path $requirementsFile -ItemType File -Value $requirementsContent -Force | Out-Null

# Verify other files exist (no need to change them)
if (-not (Test-Path $configFile)) {
    Write-Error "ERROR: '$configFile' is missing. Cannot upgrade."
    exit 1
}

Write-Host "--- 'Sentinel Agent' v2.2 Upgrade Complete ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $agentFile
git add $memoryFile
git add $requirementsFile
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL AGENT v2.2 UPGRADE COMPLETE!" -ForegroundColor Green
Write-Host "The 'Brain' and 'Memory' have been patched."
Write-Host "Next steps:"
Write-Host "1. Run 'pip install -r requirements.txt' (This will install pywin32)"
Write-Host "2. Run 'python sentinel_agent.py' to test the new Perception loop."
Write-Host "---"