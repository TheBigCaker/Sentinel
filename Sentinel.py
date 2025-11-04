import sys
import os
import argparse
import re
import time
import subprocess
import ast
import io

# --- Try to import watcher libraries ---
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_INSTALLED = True
except ImportError:
    WATCHDOG_INSTALLED = False

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
WATCH_DIRECTORY = "."  # Default for local watcher
TEMP_SCRIPT_NAME = "_current_patch.ps1"
POLL_INTERVAL_SECONDS = 30 # How often to check Google Drive
# Google Drive:
# If modifying these scopes, delete token.json.
SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
# ---------------------

# ==============================================================================
# --- "LOCAL WATCHER" (SERVICE) LOGIC ---
# ==============================================================================

# DELETING OLD BUGGY CLASS DEFINITION FROM HERE

def start_local_watcher():
    if not WATCHDOG_INSTALLED:
        print("Error: The 'watchdog' library is required to run the local watcher.", file=sys.stderr)
        print("Please run: pip install watchdog", file=sys.stderr)
        sys.exit(1)
        
    # --- Define the handler class *inside* the function ---
    # This prevents the NameError if watchdog isn't installed
    class LocalPatchHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory: return
            filepath = event.src_path
            filename = os.path.basename(filepath)
    
            if filename.endswith(".txt"):
                print(f"\n\n--- [Local Watcher] New File Detected: {filename} ---", flush=True)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    
                    # --- Pass to the shared verification and execution logic ---
                    if verify_and_run_patch(script_content, filename):
                        print(f"[Local Watcher] Cleaning up '{filename}'...", flush=True)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    else:
                        print(f"[Local Watcher] Patch failed or was aborted. Deleting '{filename}'.", flush=True)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                except Exception as e:
                    print(f"[Local Watcher] Error processing file: {e}. Ignoring.", flush=True)

    path = WATCH_DIRECTORY
    event_handler = LocalPatchHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    
    print("==================================================")
    print("✅ Sentinel 'Local Watcher' Service Started")
    print(f"Watching for new .txt files in: {os.path.abspath(path)}")
    print("Save a patch .txt from Gemini here to begin.")
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
                print("Please follow the setup guide in readme.md to get this file.", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def start_drive_watcher():
    if not GOOGLE_API_INSTALLED:
        print("Error: The Google API libraries are required to run the Drive watcher.", file=sys.stderr)
        print("Please run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib", file=sys.stderr)
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
    print(f"Polling for new .txt files every {POLL_INTERVAL_SECONDS} seconds.")
    print("Export a patch .txt from Gemini to your Google Drive to begin.")
    print("Press CTRL+C to stop the watcher.")
    print("==================================================")
    
    processed_file_ids = set()

    try:
        while True:
            try:
                # Search for .txt files, ordered by creation time
                results = service.files().list(
                    q="mimeType='text/plain'",
                    pageSize=10,
                    orderBy="createdTime desc",
                    fields="files(id, name, createdTime)"
                ).execute()
                
                items = results.get('files', [])

                if not items:
                    print(f"[{time.ctime()}] No new .txt files found. Sleeping...", end="\r", flush=True)
                else:
                    # Process files in reverse order (oldest first)
                    for item in reversed(items):
                        file_id = item['id']
                        filename = item['name']
                        
                        if file_id not in processed_file_ids:
                            print(f"\n--- [Drive Watcher] New File Detected: {filename} (ID: {file_id}) ---", flush=True)
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
                                
                                # --- Pass to the shared verification and execution logic ---
                                if verify_and_run_patch(script_content, filename):
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

def verify_and_run_patch(script_content, source_filename):
    """
    Shared logic to verify and execute a patch script.
    Returns True on success, False on failure or abort.
    """
    if not script_content.strip():
        print(f"[Watcher] File '{source_filename}' is empty. Ignoring.", flush=True)
        return False
        
    # --- 1. Verification Step ---
    print("--------------------------------------------------")
    print(f"--- VERIFY PATCH FROM: {source_filename} ---")
    print("--------------------------------------------------")
    print(script_content)
    print("--------------------------------------------------")
    print("--- END OF PATCH SCRIPT ---")
    print("--------------------------------------------------")
    
    # --- 2. Confirmation Gate ---
    try:
        choice = input(f"Do you approve and want to RUN this patch? (y/n): ")
    except EOFError:
        choice = 'n'

    if choice.lower().strip() != 'y':
        print("[Watcher] User aborted.", flush=True)
        return False

    # --- 3. Save as .ps1 and Execute ---
    print("[Watcher] User approved. Executing patch...", flush=True)
    try:
        with open(TEMP_SCRIPT_NAME, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", TEMP_SCRIPT_NAME],
            check=True, shell=True
        )
        print("[Watcher] Patch script executed successfully.", flush=True)
        return True

    except Exception as e:
        print(f"[Watcher] ERROR: The patch script failed to run: {e}", flush=True)
        return False
    finally:
        # --- 4. Cleanup local temp script ---
        if os.path.exists(TEMP_SCRIPT_NAME):
            os.remove(TEMP_SCRIPT_NAME)

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
    insertions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and isinstance(node.__dict__.get('_parent'), ast.Module):
            func_name = node.name
            start_line = node.lineno
            end_line = node.end_lineno
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

# ==============================================================================
# --- MAIN "BOOTLOADER" ---
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Warcamp Sentinel: An AI-driven patch workflow manager.")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # --- "watch" command ---
    watch_parser = subparsers.add_parser("watch", help="Start the watcher service.")
    watch_parser.add_argument("mode", choices=["local", "drive"], help="The type of watcher to run.")

    # --- "patch" command ---
    patch_parser = subparsers.add_parser("patch", help="Patch a block in a file.")
    patch_parser.add_argument("filepath", help="The file to patch (e.g., 'main.py')")
    patch_parser.add_argument("block_name", help="The name of the block to patch (e.g., 'get_dashboard')")

    # --- "bootstrap" command ---
    bootstrap_parser = subparsers.add_parser("bootstrap", help="One-time setup to add sentinel markers to a file.")
    bootstrap_parser.add_argument("filepath", help="The file to bootstrap (e.g., 'main.py')")
    
    try:
        args = parser.parse_args()
    except SystemExit:
        # argparse prints help, so we just exit
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

if __name__ == "__main__":
    main()
