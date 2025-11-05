import sys
import os
import argparse
import re
import time
import subprocess
import ast
import io
import json
import uuid

# --- Try to import GUI libraries (for 'register' command) ---
try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_INSTALLED = True
except ImportError:
    TKINTER_INSTALLED = False

# --- Try to import watcher libraries ---
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_INSTALLED = True
except ImportError:
    WATCHDOG_INSTALLED = False

# --- Try to import Google API libraries ---
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    GOOGLE_API_INSTALLED = True
except ImportError:
    GOOGLE_API_INSTALLED = False

# --- Configuration ---
# Sentinel now lives in its own "home" directory
SENTINEL_HOME_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SENTINEL_HOME_DIR, "sentinel_config.json")
TEMP_SCRIPT_NAME = "_current_patch.ps1" # Will be created *inside* the target project
POLL_INTERVAL_SECONDS = 30 # How often to check Google Drive

# Google Drive:
SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = os.path.join(SENTINEL_HOME_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SENTINEL_HOME_DIR, "token.json")
# ---------------------

def load_config():
    """Loads the project-to-path mapping from the JSON config."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: Config file {CONFIG_FILE} is corrupted. Returning empty config.", file=sys.stderr)
        return {}

def save_config(config_data):
    """Saves the project-to-path mapping to the JSON config."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config file: {e}", file=sys.stderr)
        return False

# ==============================================================================
# --- "LOCAL WATCHER" (SERVICE) LOGIC ---
# ==============================================================================

def start_local_watcher():
    if not WATCHDOG_INSTALLED:
        print("Error: 'watchdog' is required. Please run: pip install watchdog", file=sys.stderr)
        sys.exit(1)
        
    config = load_config()
    if not config:
        print("Error: No projects registered. Run 'python Sentinel.py register' first.", file=sys.stderr)
        sys.exit(1)
        
    print("Local Watcher scanning for registered projects:")
    for proj_id, path in config.items():
        print(f"  - {proj_id}: {path}")

    class LocalPatchHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory: return
            filepath = event.src_path
            filename = os.path.basename(filepath)
            
            # Check for our new file format: SentScript-PROJECT_ID-*.txt
            if filename.endswith(".txt") and filename.startswith("SentScript-"):
                try:
                    # Extract Project ID
                    project_id = filename.split('-')[1]
                    config = load_config()
                    
                    if project_id not in config:
                        print(f"\n[Local Watcher] Detected file for unknown project ID: {project_id}. Ignoring.", flush=True)
                        return
                        
                    target_project_path = config[project_id]
                    print(f"\n\n--- [Local Watcher] New Patch File Detected: {filename} ---", flush=True)
                    print(f"--- Target Project: {project_id} ({target_project_path}) ---", flush=True)

                    with open(filepath, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    
                    if verify_and_run_patch(script_content, filename, target_project_path):
                        print(f"[Local Watcher] Cleaning up '{filename}'...", flush=True)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    else:
                        print(f"[Local Watcher] Patch failed or aborted. Deleting '{filename}'.", flush=True)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                except Exception as e:
                    print(f"[Local Watcher] Error processing file: {e}. Ignoring.", flush=True)

    # Watcher must now watch all registered directories
    observer = Observer()
    for path in config.values():
        if os.path.exists(path):
            observer.schedule(LocalPatchHandler(), path, recursive=False)
        else:
            print(f"Warning: Path not found for project. Not watching: {path}", file=sys.stderr)

    print("==================================================")
    print("✅ Sentinel 'Local Watcher' Service Started")
    print(f"Watching for new 'SentScript-ID-*.txt' files in all registered project folders.")
    print("Press CTRL+C to stop the watcher.")
    print("==================================================")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[Local Watcher] Service stopped by user.")
    observer.join()

# ==============================================================================
# --- "GOOGLE DRIVE WATCHER" (SERVICE) LOGIC ---
# ==============================================================================

def get_drive_service():
    """Authenticates and returns a Google Drive API service object."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"FATAL ERROR: '{CREDENTIALS_FILE}' not found.", file=sys.stderr)
                print(f"Please follow the setup guide in readme.md to get this file.", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def start_drive_watcher():
    if not GOOGLE_API_INSTALLED:
        print("Error: Google API libraries are required. Please run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    print("Authenticating with Google Drive...")
    try:
        service = get_drive_service()
        print("Authentication successful.")
    except Exception as e:
        print(f"Failed to authenticate with Google Drive: {e}", file=sys.stderr)
        sys.exit(1)

    print("==================================================")
    print("✅ Sentinel 'Google Drive Watcher' Service Started")
    print(f"Polling for new 'SentScript-ID-*.txt' files every {POLL_INTERVAL_SECONDS} seconds.")
    print("Press CTRL+C to stop the watcher.")
    print("==================================================")
    
    processed_file_ids = set()

    try:
        while True:
            try:
                # Search for .txt files that start with "SentScript-"
                results = service.files().list(
                    q="mimeType='text/plain' and name starts with 'SentScript-'",
                    pageSize=10,
                    orderBy="createdTime desc",
                    fields="files(id, name, createdTime)"
                ).execute()
                
                items = results.get('files', [])

                if not items:
                    print(f"[{time.ctime()}] No new .txt files found. Sleeping...", end="\r", flush=True)
                else:
                    config = load_config()
                    for item in reversed(items):
                        file_id = item['id']
                        filename = item['name']
                        
                        if file_id in processed_file_ids:
                            continue

                        # --- New Multi-Project Logic ---
                        try:
                            project_id = filename.split('-')[1]
                        except IndexError:
                            print(f"\n[Drive Watcher] Invalid filename format (no ID): {filename}. Ignoring.", flush=True)
                            processed_file_ids.add(file_id) # Mark as processed to avoid re-checking
                            continue
                            
                        if project_id not in config:
                            print(f"\n[Drive Watcher] Detected file for unknown project ID: {project_id}. Ignoring.", flush=True)
                            processed_file_ids.add(file_id)
                            continue
                        
                        target_project_path = config[project_id]
                        print(f"\n--- [Drive Watcher] New Patch File Detected: {filename} (ID: {file_id}) ---", flush=True)
                        print(f"--- Target Project: {project_id} ({target_project_path}) ---", flush=True)
                        processed_file_ids.add(file_id) # Mark as processed
                        
                        try:
                            # Download the file content
                            request = service.files().get_media(fileId=file_id)
                            file_handle = io.BytesIO()
                            downloader = MediaIoBaseDownload(file_handle, request)
                            done = False
                            while done is False:
                                status, done = downloader.next_chunk()
                            script_content = file_handle.getvalue().decode('utf-8')
                            
                            if verify_and_run_patch(script_content, filename, target_project_path):
                                print(f"[Drive Watcher] Deleting '{filename}' from Google Drive...", flush=True)
                                service.files().delete(fileId=file_id).execute()
                            else:
                                print(f"[Drive Watcher] Patch failed or aborted. Deleting '{filename}' from Drive.", flush=True)
                                service.files().delete(fileId=file_id).execute()

                        except HttpError as e:
                            print(f"[Drive Watcher] Error processing file {filename}: {e}", flush=True)
                        except Exception as e:
                            print(f"[Drive Watcher] A critical error occurred processing {filename}: {e}", flush=True)
                                
            except HttpError as e:
                print(f"\n[Drive Watcher] API Error: {e}. Retrying...", flush=True)
            except Exception as e:
                print(f"\n[Drive Watcher] An unexpected error occurred: {e}", flush=True)
            
            time.sleep(POLL_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n[Drive Watcher] Service stopped by user.")

# ==============================================================================
# --- "ROBOT SURGEON" (TOOL) & SHARED LOGIC ---
# ==============================================================================

def verify_and_run_patch(script_content, source_filename, target_project_path):
    """
    Shared logic to verify and execute a patch script *in the target project's directory*.
    """
    if not script_content.strip():
        print(f"[Watcher] File '{source_filename}' is empty. Ignoring.", flush=True)
        return False
        
    print(f"--- VERIFY PATCH FOR: {source_filename} ---")
    print(script_content)
    print("--- END OF PATCH SCRIPT ---")
    
    try:
        choice = input(f"Do you approve and want to RUN this patch? (y/n): ")
    except EOFError:
        choice = 'n'

    if choice.lower().strip() != 'y':
        print("[Watcher] User aborted.", flush=True)
        return False

    print("[Watcher] User approved. Executing patch...", flush=True)
    
    # We must run the patch script *from within* the target project directory
    temp_script_path = os.path.join(target_project_path, TEMP_SCRIPT_NAME)
    
    try:
        with open(temp_script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Execute the script *with the target path as the Current Working Directory*
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", TEMP_SCRIPT_NAME],
            check=True, shell=True, cwd=target_project_path # This is the magic!
        )
        print("[Watcher] Patch script executed successfully.", flush=True)
        return True

    except Exception as e:
        print(f"[Watcher] ERROR: The patch script failed to run: {e}", flush=True)
        return False
    finally:
        if os.path.exists(temp_script_path):
            os.remove(temp_script_path)

def get_block_regex(block_name, file_extension):
    escaped_name = re.escape(block_name)
    if file_extension == ".py":
        start_sentinel = rf"# --- BLOCK: {escaped_name} ---"
        end_sentinel = rf"# --- ENDBLOCK: {escaped_name} ---"
    else:
        start_sentinel = rf"<!-- BLOCK: {escaped_name} -->"
        end_sentinel = rf"<!-- ENDBLOCK: {escaped_name} -->"
    return re.compile(f"(?s)({re.escape(start_sentinel)})(.*)({re.escape(end_sentinel)})")

def patch_file(filepath, block_name, new_content):
    # This function is now called *by* the .ps1 script, so it runs
    # in the correct project directory.
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return False
    _, file_extension = os.path.splitext(filepath)
    regex_pattern = get_block_regex(block_name, file_extension)
    if not regex_pattern.search(file_content):
        print(f"Error: Could not find sentinels for block '{block_name}' in {filepath}", file=sys.stderr)
        return False
    match = regex_pattern.search(file_content)
    if match.group(2).strip() == new_content.strip():
        print(f"Validation Failed: Patch content for '{block_name}' is identical to existing code.", file=sys.stderr)
        return True
    replacement = f"\\1\n{new_content}\n\\3"
    new_file_content = regex_pattern.sub(replacement, file_content)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_file_content)
        print(f"SUCCESS: Patched block '{block_name}' in '{filepath}'")
        return True
    except Exception as e:
        print(f"Error writing to file: {e}", file=sys.stderr)
        return False

def bootstrap_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return False
    if "# --- BLOCK:" in file_content or "<!-- BLOCK:" in file_content:
        print("Error: File already appears to be bootstrapped. Aborting.", file=sys.stderr)
        return False
    try:
        tree = ast.parse(file_content)
        lines = file_content.splitlines(True)
    except Exception as e:
        print(f"Error parsing Python file: {e}", file=sys.stderr)
        return False
    
    # Add parent links to tree for accurate filtering
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            setattr(child, '_parent', node)

    insertions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(node, '_parent') and isinstance(node._parent, ast.Module):
            func_name = node.name
            start_line = node.lineno
            end_line = node.end_lineno
            
            if node.decorator_list:
                start_line = node.decorator_list[0].lineno

            if node.body:
                last_body_item = node.body[-1]
                end_line = getattr(last_body_item, 'end_lineno', last_body_item.lineno)

            indent = " " * node.col_offset
            insertions.append((start_line - 1, f"{indent}# --- BLOCK: {func_name} ---\n"))
            insertions.append((end_line, f"{indent}# --- ENDBLOCK: {func_name} ---\n"))

    if not insertions:
        print("No top-level functions found. Nothing to bootstrap.", file=sys.stderr)
        return False
        
    insertions.sort(key=lambda x: x[0], reverse=True)
    new_lines = list(lines)
    for line_index, text_to_insert in insertions:
        new_lines.insert(line_index, text_to_insert)
    new_file_content = "".join(new_lines)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_file_content)
        print(f"SUCCESS: Bootstrapped '{filepath}' with {len(insertions)//2} blocks.")
        return True
    except Exception as e:
        print(f"Error writing bootstrapped file: {e}", file=sys.stderr)
        return False

def register_project():
    """Uses a GUI to select a folder and registers it with a unique ID."""
    if not TKINTER_INSTALLED:
        print("Error: 'tkinter' is required for the register command.", file=sys.stderr)
        print("Tkinter is usually included with Python, but your installation may be missing it.", file=sys.stderr)
        return False
        
    print("Opening folder selection dialog...")
    root = tk.Tk()
    root.withdraw() # Hide the main window
    
    project_path = filedialog.askdirectory(title="Select Project Folder to Register")
    root.destroy()
    
    if not project_path:
        print("No folder selected. Aborting.", flush=True)
        return False
        
    project_path = os.path.normpath(project_path)
    config = load_config()
    
    # Check if this path is already registered
    for proj_id, path in config.items():
        if path == project_path:
            print(f"Project already registered with ID: {proj_id}", flush=True)
            return True
            
    # Generate a unique ID (e.g., "proj-a1b2")
    project_id = f"proj-{uuid.uuid4().hex[:4]}"
    config[project_id] = project_path
    
    if save_config(config):
        print(f"SUCCESS: Registered project at '{project_path}' with ID: {project_id}", flush=True)
        return True
    else:
        print(f"Error: Failed to save updated config.", file=sys.stderr)
        return False

# ==============================================================================
# --- MAIN "BOOTLOADER" ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Sentinel v2.0: AI-driven multi-project patch manager.")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # --- "watch" command ---
    watch_parser = subparsers.add_parser("watch", help="Start the watcher service.")
    watch_parser.add_argument("mode", choices=["local", "drive"], help="The type of watcher to run.")

    # --- "patch" command ---
    patch_parser = subparsers.add_parser("patch", help="Patch a block in a file. (Called by patch scripts)")
    patch_parser.add_argument("filepath", help="The file to patch (e.g., 'main.py')")
    patch_parser.add_argument("block_name", help="The name of the block to patch (e.g., 'get_dashboard')")

    # --- "bootstrap" command ---
    bootstrap_parser = subparsers.add_parser("bootstrap", help="One-time setup to add sentinel markers to a file.")
    bootstrap_parser.add_argument("filepath", help="The file to bootstrap (e.g., 'main.py')")
    
    # --- "register" command ---
    register_parser = subparsers.add_parser("register", help="Register a new project folder with Sentinel (opens GUI).")

    try:
        args = parser.parse_args()
    except SystemExit:
        return
        
    if args.command == "watch":
        if args.mode == "local":
            start_local_watcher()
        elif args.mode == "drive":
            start_drive_watcher()
            
    elif args.command == "patch":
        new_content = sys.stdin.read()
        if not patch_file(args.filepath, args.block_name, new_content):
            sys.exit(1)

    elif args.command == "bootstrap":
        if not bootstrap_file(args.filepath):
            sys.exit(1)
            
    elif args.command == "register":
        if not register_project():
            sys.exit(1)

if __name__ == "__main__":
    main()
