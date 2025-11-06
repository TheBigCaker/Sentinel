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

# --- Try to import DOCX library ---
try:
    import docx
    DOCX_INSTALLED = True
except ImportError:
    DOCX_INSTALLED = False

# --- Configuration (v2.6) ---
SENTINEL_HOME_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SENTINEL_HOME_DIR, "sentinel_config.json")
PROCESSED_FILES_DB = os.path.join(SENTINEL_HOME_DIR, "sentinel_processed.json") # v2.5+ Persistent DB
TEMP_SCRIPT_NAME = "_current_patch.ps1" 
POLL_INTERVAL_SECONDS = 30 
TEMP_DOCX_DOWNLOAD = os.path.join(SENTINEL_HOME_DIR, "_temp_patch.docx") # For Drive watcher

# Google Drive:
SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = os.path.join(SENTINEL_HOME_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SENTINEL_HOME_DIR, "token.json")
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# ---------------------

# --- DB Helper Functions ---
def load_processed_files():
    """Loads the set of processed file IDs/paths from the JSON DB."""
    if not os.path.exists(PROCESSED_FILES_DB):
        return set()
    try:
        with open(PROCESSED_FILES_DB, 'r', encoding='utf-8') as f:
            return set(json.load(f)) # Load list and convert to set
    except Exception:
        print(f"Warning: Could not read {PROCESSED_FILES_DB}. Starting with empty set.", file=sys.stderr)
        return set()

def save_processed_files(processed_set):
    """Saves the set of processed file IDs/paths to the JSON DB."""
    try:
        with open(PROCESSED_FILES_DB, 'w', encoding='utf-8') as f:
            json.dump(list(processed_set), f, indent=4) # Convert set to list for saving
    except Exception as e:
        print(f"[Watcher] Error: Could not save processed files list: {e}", file=sys.stderr)
# --- End DB ---

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

def read_docx_text(filepath):
    """Uses python-docx to read the text from a .docx file."""
    if not DOCX_INSTALLED:
        print("Error: 'python-docx' is required to read .docx files.", file=sys.stderr)
        print("Please run: pip install python-docx", file=sys.stderr)
        return None
    try:
        document = docx.Document(filepath)
        full_text = []
        for para in document.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
    except Exception as e:
        print(f"[Watcher] Error: Failed to read .docx file: {e}", file=sys.stderr)
        return None

# ==============================================================================
# --- "LOCAL WATCHER" (SERVICE) LOGIC (v2.6 - UPGRADED) ---
# ==============================================================================

def start_local_watcher():
    if not WATCHDOG_INSTALLED:
        print("Error: 'watchdog' is required. Please run: pip install watchdog", file=sys.stderr)
        sys.exit(1)
        
    # v2.6: Check for .docx reader
    if not DOCX_INSTALLED:
        print("Error: 'python-docx' is required for 'watch local' to read .docx files.", file=sys.stderr)
        print("Please run: pip install python-docx", file=sys.stderr)
        sys.exit(1)
        
    config = load_config()
    if not config:
        print("Error: No projects registered. Run 'python Sentinel.py register' first.", file=sys.stderr)
        sys.exit(1)
        
    processed_file_paths = load_processed_files() # Using path for local

    print("--- [Watcher Boot] Local Watcher scanning for registered projects: ---")
    for proj_id, path in config.items():
        print(f"  - Watching {proj_id}: {path}")

    class LocalPatchHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory: 
                print(f"[Watcher Log] Ignoring directory event: {event.src_path}", flush=True)
                return
                
            filepath = os.path.normpath(event.src_path)
            filename = os.path.basename(filepath)
            
            print(f"\n[Watcher Log] File event detected: {filename}", flush=True)

            # v2.6: Fix for race condition
            print(f"[Watcher Log] Waiting 1 second for file to save...", flush=True)
            time.sleep(1)

            if not os.path.exists(filepath):
                print(f"[Watcher Log] File disappeared (likely temp file). Ignoring.", flush=True)
                return

            if filepath in processed_file_paths:
                print(f"[Watcher Log] Ignoring already processed file: {filename}", flush=True)
                return 

            # --- v2.6: UPGRADED TO WATCH FOR .docx FILES ---
            if filename.endswith(".docx") and filename.startswith("SentScript-"):
                print(f"[Watcher Log] File is a new .docx patch. Processing...", flush=True)
                try:
                    # --- FIXED v2.6 PARSER LOGIC ---
                    clean_name = os.path.splitext(filename)[0] # Remove .docx
                    parts = clean_name.split('-')
                    if len(parts) < 4: 
                        print(f"[Watcher] ERROR: Invalid filename format (not enough parts): {filename}. Ignoring.", flush=True)
                        return
                    project_id = f"{parts[1]}-{parts[2]}" # Re-combine 'proj' and 'b6cc'
                    print(f"[Watcher Log] Parsed Project ID: {project_id}", flush=True)
                    # --- END FIXED LOGIC ---
                    
                    config = load_config()
                    
                    if project_id not in config:
                        print(f"[Watcher] ERROR: Detected file for unknown project ID: {project_id}. Ignoring.", flush=True)
                        return
                        
                    target_project_path = config[project_id]
                    print(f"\n\n--- [Local Watcher] New Patch File Detected: {filename} ---")
                    print(f"--- Target Project: {project_id} ({target_project_path}) ---")

                    # --- v2.6: Read .docx file ---
                    script_content = read_docx_text(filepath)
                    if script_content is None:
                        raise Exception(f"Failed to read text from .docx file: {filepath}")
                    
                    if not script_content.lstrip().startswith("<#"):
                        print(f"[Watcher] ERROR: File {filename} is not a SentScript (missing '<#'). Ignoring.", flush=True)
                        processed_file_paths.add(filepath) # Add to DB so we don't re-check
                        save_processed_files(processed_file_paths)
                        return
                    
                    # Run the patch
                    if verify_and_run_patch(script_content, filename, target_project_path):
                        print(f"[Watcher] Patch successful for {filename}.", flush=True)
                    else:
                        print(f"[Watcher] Patch failed or aborted for {filename}.", flush=True)
                    
                    processed_file_paths.add(filepath)
                    save_processed_files(processed_file_paths)

                except Exception as e:
                    print(f"[Watcher] CRITICAL ERROR processing file: {e}. Ignoring.", flush=True)
            else:
                print(f"[Watcher Log] Ignoring file (not a SentScript .docx): {filename}", flush=True)

    observer = Observer()
    for path in config.values():
        if os.path.exists(path):
            observer.schedule(LocalPatchHandler(), path, recursive=False)
        else:
            print(f"[Watcher] Warning: Path not found for project. Not watching: {path}", file=sys.stderr)

    print("==================================================")
    print("✅ Sentinel 'Local Watcher' Service Started (v2.6)")
    print(f"Loaded {len(processed_file_paths)} already-processed file paths.")
    print(f"Watching for new 'SentScript-ID-*.docx' files in all registered project folders.")
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
# --- "GOOGLE DRIVE WATCHER" (SERVICE) LOGIC (v2.6 - All Fixes) ---
# ==============================================================================
def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"FATAL ERROR: '{CREDENTIALS_FILE}' not found.", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def start_drive_watcher():
    if not GOOGLE_API_INSTALLED or not DOCX_INSTALLED:
        print("Error: Missing required libraries for Drive Watcher.", file=sys.stderr)
        if not GOOGLE_API_INSTALLED:
            print("Please run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib", file=sys.stderr)
        if not DOCX_INSTALLED:
            print("Please run: pip install python-docx", file=sys.stderr)
        sys.exit(1)

    print("Authenticating with Google Drive...")
    try:
        service = get_drive_service()
        print("Authentication successful.")
    except Exception as e:
        print(f"Failed to authenticate with Google Drive: {e}", file=sys.stderr)
        sys.exit(1)

    processed_file_ids = load_processed_files() # Using file ID for drive

    print("==================================================")
    print("✅ Sentinel 'Google Drive Watcher' Service Started (v2.6)")
    print(f"Loaded {len(processed_file_ids)} already-processed file IDs.")
    print(f"Polling for new 'SentScript-ID-*.docx' files every {POLL_INTERVAL_SECONDS} seconds.")
    print("Press CTRL+C to stop the watcher.")
    print("==================================================")
    
    try:
        while True:
            try:
                results = service.files().list(
                    q=f"mimeType='{DOCX_MIME_TYPE}' and name starts with 'SentScript-'",
                    pageSize=20,
                    orderBy="createdTime desc",
                    fields="files(id, name, createdTime)"
                ).execute()
                
                items = results.get('files', [])
                new_files_found = 0

                if items:
                    config = load_config()
                    for item in reversed(items):
                        file_id = item['id']
                        filename = item['name']
                        
                        if file_id in processed_file_ids:
                            continue

                        new_files_found += 1
                        print(f"\n[Watcher Log] Drive file event detected: {filename}", flush=True)
                        
                        try:
                            # --- FIXED v2.6 PARSER LOGIC ---
                            clean_name = os.path.splitext(filename)[0]
                            parts = clean_name.split('-')
                            if len(parts) < 4: 
                                print(f"[Drive Watcher] ERROR: Invalid filename format (not enough parts): {filename}. Ignoring.", flush=True)
                                processed_file_ids.add(file_id) 
                                save_processed_files(processed_file_ids)
                                continue
                            project_id = f"{parts[1]}-{parts[2]}" # Re-combine 'proj' and 'b6cc'
                            print(f"[Watcher Log] Parsed Project ID: {project_id}", flush=True)
                            # --- END FIXED LOGIC ---
                        except IndexError:
                            print(f"[Drive Watcher] ERROR: Invalid filename format (no ID): {filename}. Ignoring.", flush=True)
                            processed_file_ids.add(file_id)
                            continue
                        
                        if project_id not in config:
                            print(f"[Drive Watcher] ERROR: Detected file for unknown project ID: {project_id}. Ignoring.", flush=True)
                            processed_file_ids.add(file_id)
                            save_processed_files(processed_file_ids)
                            continue
                        
                        target_project_path = config[project_id]
                        print(f"\n--- [Drive Watcher] New Patch File Detected: {filename} (ID: {file_id}) ---")
                        print(f"--- Target Project: {project_id} ({target_project_path}) ---")
                        
                        try:
                            request = service.files().get_media(fileId=file_id)
                            fh = io.FileIO(TEMP_DOCX_DOWNLOAD, 'wb')
                            downloader = MediaIoBaseDownload(fh, request)
                            done = False
                            while done is False:
                                status, done = downloader.next_chunk()
                            fh.close()
                            
                            print(f"[Watcher Log] Download complete. Parsing .docx file...", flush=True)
                            script_content = read_docx_text(TEMP_DOCX_DOWNLOAD)
                            
                            if os.path.exists(TEMP_DOCX_DOWNLOAD):
                                os.remove(TEMP_DOCX_DOWNLOAD) 

                            if script_content is None:
                                raise Exception("Failed to read text from .docx file.")
                            
                            if not script_content.lstrip().startswith("<#"):
                                print(f"[Watcher] ERROR: File {filename} is not a SentScript (missing '<#'). Ignoring.", flush=True)
                                processed_file_ids.add(file_id) 
                                save_processed_files(processed_file_ids)
                                continue

                            if verify_and_run_patch(script_content, filename, target_project_path):
                                print(f"[Watcher] Patch script ran successfully for {filename}.", flush=True)
                            else:
                                print(f"[Watcher] Patch failed or aborted for {filename}.", flush=True)

                            processed_file_ids.add(file_id)
                            save_processed_files(processed_file_ids)

                        except HttpError as e:
                            print(f"[Drive Watcher] Error processing file {filename}: {e}", flush=True)
                        except Exception as e:
                            print(f"[Drive Watcher] A critical error occurred processing {filename}: {e}", flush=True)
                
                if new_files_found == 0:
                    print(f"[{time.ctime()}] No new .docx files found. Sleeping...", end="\r", flush=True)
                else:
                    print(f"[{time.ctime()}] All new files processed. Sleeping...", end="\r", flush=True)
                                
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
    temp_script_path = os.path.join(target_project_path, TEMP_SCRIPT_NAME)
    
    try:
        with open(temp_script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Run PowerShell
        process = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", TEMP_SCRIPT_NAME],
            check=True, shell=True, cwd=target_project_path,
            capture_output=True, text=True, encoding='utf-8'
        )
        print(f"[PowerShell Output]:\n{process.stdout}")
        if process.stderr:
             print(f"[PowerShell Error]:\n{process.stderr}")
        print("[Watcher] Patch script executed successfully.", flush=True)
        return True

    except subprocess.CalledProcessError as e:
        print(f"[Watcher] ERROR: The patch script failed to run (non-zero exit code).", flush=True)
        print(f"[PowerShell Output]:\n{e.stdout}")
        print(f"[PowerShell Error]:\n{e.stderr}")
        return False
    except Exception as e:
        print(f"[Watcher] CRITICAL ERROR: Failed to execute subprocess: {e}", flush=True)
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
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return False
    try:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except UnicodeDecodeError:
            print(f"[Patcher] Warning: UTF-8 decode failed on {filepath}. Retrying with 'latin-1'...", file=sys.stderr)
            with open(filepath, 'r', encoding='latin-1') as f:
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
    clean_old_content = re.sub(r'\s+', ' ', match.group(2).strip())
    clean_new_content = re.sub(r'\s+', ' ', new_content.strip())

    if clean_old_content == clean_new_content:
        print(f"Validation Failed: Patch content for '{block_name}' is identical to existing code.", file=sys.stderr)
        return True 
        
    replacement = f"\\1\n{new_content}\n\\3"
    new_file_content = regex_pattern.sub(replacement, file_content)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_file_content)
    except UnicodeEncodeError:
        print(f"[Patcher] Warning: UTF-8 encode failed. Retrying with 'latin-1'...", file=sys.stderr)
        with open(filepath, 'w', encoding='latin-1') as f:
            f.write(new_file_content)
    except Exception as e:
        print(f"Error writing to file: {e}", file=sys.stderr)
        return False
        
    print(f"SUCCESS: Patched block '{block_name}' in '{filepath}'")
    return True

def bootstrap_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return False
    try:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except UnicodeDecodeError:
            print(f"[Bootstrapper] Warning: UTF-8 decode failed. Retrying with 'latin-1'...", file=sys.stderr)
            with open(filepath, 'r', encoding='latin-1') as f:
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
    except UnicodeEncodeError:
        print(f"[Bootstrapper] Warning: UTF-8 encode failed. Retrying with 'latin-1'...", file=sys.stderr)
        with open(filepath, 'w', encoding='latin-1') as f:
            f.write(new_file_content)
    except Exception as e:
        print(f"Error writing bootstrapped file: {e}", file=sys.stderr)
        return False
        
    print(f"SUCCESS: Bootstrapped '{filepath}' with {len(insertions)//2} blocks.")
    return True

def register_project():
    if not TKINTER_INSTALLED:
        print("Error: 'tkinter' is required for the register command.", file=sys.stderr)
        return False
        
    print("Opening folder selection dialog...")
    root = tk.Tk()
    root.withdraw() 
    
    project_path = filedialog.askdirectory(title="Select Project Folder to Register")
    root.destroy()
    
    if not project_path:
        print("No folder selected. Aborting.", flush=True)
        return False
        
    project_path = os.path.normpath(project_path)
    config = load_config()
    
    for proj_id, path in config.items():
        if path == project_path:
            print(f"Project already registered with ID: {proj_id}", flush=True)
            return True
            
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
    parser = argparse.ArgumentParser(description="Sentinel v2.6: AI-driven multi-project patch manager.")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    watch_parser = subparsers.add_parser("watch", help="Start the watcher service.")
    watch_parser.add_argument("mode", choices=["local", "drive"], help="The type of watcher to run.")

    patch_parser = subparsers.add_parser("patch", help="Patch a block in a file. (Called by patch scripts)")
    patch_parser.add_argument("filepath", help="The file to patch (e.g., 'main.py')")
    patch_parser.add_argument("block_name", help="The name of the block to patch (e.g., 'get_dashboard')")

    bootstrap_parser = subparsers.add_parser("bootstrap", help="One-time setup to add sentinel markers to a file.")
    bootstrap_parser.add_argument("filepath", help="The file to bootstrap (e.g., 'main.py')")
    
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
        # This command reads from stdin
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