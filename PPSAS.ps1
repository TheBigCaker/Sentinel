<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Agent v2.0)
================================================================================
This bootstrapper creates the v2.0 "Sentinel Agent" framework.
This is a MAJOR upgrade. It lays the foundation for the "Memory" system.

It creates:
1. sentinel_agent.py (The new "Brain")
2. sentinel_memory.py (The "Memory" manager for ChromaDB + SQLite)
3. sentinel_config.json (A new config file for paths)
4. requirements.txt (Adds chromadb, peewee)
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Agent"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Feat: Create Sentinel Agent v2.0 framework"

# Define the filenames to be created
$agentFile = "sentinel_agent.py"
$memoryFile = "sentinel_memory.py"
$configFile = "sentinel_config.json"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for sentinel_agent.py (The "Brain") ---
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
        img = ImageGrab.grab(bbox=bbox)
        img.save(full_path)
        return full_path
    except Exception as e:
        print(f"[EYES] Error: Could not take screenshot: {e}")
        return None

def main():
    print("--- Sentinel Agent v2.0 (Brain + Memory) ---")
    
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at '{MODEL_PATH}'")
        sys.exit(1)

    print(f"Initializing memory at: {DB_PATH}")
    memory.init_db()
    
    print("[BRAIN] Sentinel Agent v2.0 initialized.")
    print("This script is the new foundation.")
    print("Next steps will be to build the 'perceive' and 'act' loops.")
    
    # --- TODO: Build the full agent loop here ---
    # 1. Perceive: "What app am I in?"
    # 2. Retrieve: "What do I know about this app?" (from SQLite)
    # 3. Act: "Find the 'Copy' button."
    # 4. Verify: "Does this look like the 'Copy' button I have in memory?" (from ChromaDB)
    # 5. Execute: Click the button.
    # 6. Learn: If the button moved, update the SQLite DB.
    
    print("\n--- TEST: Storing a new memory ---")
    # This is an example of how we'll use the memory
    try:
        # We would get this embedding from the AI
        example_embedding = [0.1] * 1536 # Placeholder embedding
        memory.store_visual_memory(
            label="test_button",
            embedding=example_embedding,
            app_name="notepad.exe",
            window_title="Untitled - Notepad",
            x=100,
            y=200,
            notes="This is a test entry."
        )
        print("Successfully stored a test memory.")
        
        print("\n--- TEST: Retrieving a memory ---")
        retrieved = memory.retrieve_fact_memory("test_button", "notepad.exe")
        if retrieved:
            print(f"Successfully retrieved fact memory:")
            print(f"  App: {retrieved.app_name}")
            print(f"  Coords: ({retrieved.last_known_x}, {retrieved.last_known_y})")
            
            print("\n--- TEST: Finding a visual match ---")
            matches = memory.find_visual_match(example_embedding, num_results=1)
            if matches:
                print(f"Successfully found visual match in ChromaDB!")
                print(f"  ID: {matches['ids'][0]}")
                
    except Exception as e:
        print(f"Database test failed: {e}")
        print("Please ensure you have run 'pip install -r requirements.txt'")


if __name__ == "__main__":
    main()
"@

# --- Content for sentinel_memory.py (The "Memory") ---
$memoryScript = @"
import sqlite3
import chromadb
import json
import os
from peewee import (Model, SqliteDatabase, CharField, IntegerField, 
                    TextField, ForeignKeyField, DoesNotExist)

# This will hold our ChromaDB and SQLite DB
db = None
client = None

# --- 1. SQL DATABASE (The "Facts" / "Where") ---
# Defines the structure for our Factual (SQL) memory.

class BaseModel(Model):
    class Meta:
        database = None

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
        db = SqliteDatabase(self.sqlite_file)
        BaseModel._meta.database = db
        
        # We use a persistent client that saves to disk
        client = chromadb.PersistentClient(path=self.chroma_path)
        
        self.visual_collection = None

    def init_db(self):
        """Initializes both databases and creates tables/collections."""
        try:
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

# --- Content for sentinel_config.json ---
$configJson = @"
{
    "model_path": "C:\\Dev\\Models\\gemma-3-4b-it-q4_0.gguf",
    "db_path": "C:\\Dev\\Sentinel\\Agent\\memory",
    "screenshot_file": "_temp_screenshot.png"
}
"@

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
"@

# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

# Create a 'memory' subdirectory
$memoryDbPath = "C:\Dev\Sentinel\Agent\memory"
New-Item -Path $memoryDbPath -ItemType Directory -Force | Out-Null

Write-Host "--- Generating Sentinel Agent v2.0 Framework ---"

# Create the Agent "Brain"
Write-Host "Creating '$agentFile'..."
New-Item -Path $agentFile -ItemType File -Value $agentScript -Force | Out-Null

# Create the "Memory"
Write-Host "Creating '$memoryFile'..."
New-Item -Path $memoryFile -ItemType File -Value $memoryScript -Force | Out-Null

# Create the Config JSON
Write-Host "Creating '$configFile'..."
New-Item -Path $configFile -ItemType File -Value $configJson -Force | Out-Null

# Create/Update the requirements.txt file
Write-Host "Updating '$requirementsFile'..."
New-Item -Path $requirementsFile -ItemType File -Value $requirementsContent -Force | Out-Null

Write-Host "--- 'Sentinel Agent' Framework Created Successfully ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $agentFile
git add $memoryFile
git add $configFile
git add $requirementsFile
git add $memoryDbPath # Add the new directory
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL AGENT v2.0 BOOTSTRAP COMPLETE!" -ForegroundColor Green
Write-Host "The new 'Brain' and 'Memory' framework is in place."
Write-Host "Next steps:"
Write-Host "1. Run 'pip install -r requirements.txt' (This will install chromadb and peewee)"
Write-Host "2. Run 'python sentinel_agent.py' to initialize the databases."
Write-Host "---"