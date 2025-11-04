# Sentinel.py (v1.2): AI-Driven Patch Workflow

Sentinel.py is a Python utility designed to bridge the gap between a human developer, a generative AI (like Gemini), and a local codebase. It creates a seamless, "hot-folder" workflow for applying, verifying, and deploying AI-generated code patches.

It operates in two modes:
1.  **"Watcher" (Service):** A background service that watches for new patch files (.txt), either in a **local folder** or on **Google Drive**.
2.  **"Tool" (Surgeon):** A command-line tool used to perform surgical code-patching (patch) or prepare a file for patching (ootstrap).

## The "Rinse and Repeat" Workflow

This system is designed for a fast, iterative loop.

1.  **Developer:** Starts a new chat with Gemini using a handoff_*.txt prompt. "Gemini, I need to fix a bug in main.py."
2.  **Gemini:** Provides a self-contained PowerShell script (formatted as a .txt file) containing the code patch and Git commands.
3.  **Developer:** Exports this .txt file from the Canvas **with a name starting with 'SentScript'** (e.g., SentScript(Patch1).txt) to their Google Drive or local "hot folder".
4.  **Sentinel (Watcher):** (Running in a dedicated terminal) Instantly detects the new, correctly-named file.
5.  **Sentinel (Watcher):** Prints the *entire content* of the script for the developer to review and asks: Do you approve and want to RUN this patch? (y/n):
6.  **Developer:** Reviews the patch script and types y to approve.
7.  **Sentinel (Watcher):** Executes the PowerShell script, which in turn calls Sentinel (Tool).
8.  **Sentinel (Tool):** Surgically replaces the code block in main.py and the script pushes the changes to Git.
9.  **Developer:** "Gemini, the patch is live. Please verify the repo."

---

## 1. One-Time Environment Setup

Before first use, you must set up your environment.

### A. Install Python Dependencies

Sentinel has dependencies for its different modes. Install all of them.

`ash
# Install from requirements.txt
pip install -r requirements.txt
`

### B. PowerShell Execution Policy

PowerShell is locked down by default. You must run this **one-time** command in an **Administrator** PowerShell window to allow your local scripts to run.

`powershell
# This tells PowerShell to trust scripts you (the current user) create.
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
`

### C. (Optional) Google Drive Watcher Setup

**This is a 15-minute, one-time setup.** If you only want to use the local watcher, you can skip this. This text is based on the guide you provided.

**Step 1: Enable the Google Drive API**
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project (or select an existing one).
3.  In the search bar at the top, type "**Google Drive API**" and select it.
4.  Click the "**Enable**" button.

**Step 2: Configure Consent Screen**
1.  Click "**Credentials**" in the left-hand menu.
2.  If prompted, click "**Configure Consent Screen**".
3.  Select "**External**" and click "**Create**".
4.  **App name:** "Sentinel Drive Watcher"
5.  **User support email:** Your email.
6.  **Developer contact:** Your email.
7.  Click "**Save and Continue**" for the rest of the steps. You don't need to add scopes or test users. Finally, click "**Back to Dashboard**".

**Step 3: Create Credentials**
1.  Go back to "**Credentials**".
2.  Click "**+ CREATE CREDENTIALS**" > "**OAuth client ID**".
3.  For "**Application type**", select "**Desktop app**".
4.  Give it a name (e.g., "Sentinel CLI") and click "**Create**".
5.  A window will pop up. Click "**DOWNLOAD JSON**".
6.  **CRITICAL:** Rename the downloaded file to credentials.json and save it in the exact same directory as your Sentinel.py script.

**Step 4: First-Time Run**
The first time you run python Sentinel.py watch drive, your web browser will automatically open. You will be asked to log in and grant permission. This will create a 	oken.json file so you don't have to log in again.

---

## 2. Project Setup (ootstrap)

Before you can patch a file, you must add "sentinel blocks." The ootstrap command does this automatically for Python files.

`ash
# Run this command ONCE on your Python code
python Sentinel.py bootstrap main.py
`

---

## 3. How to Use Sentinel

### Mode 1: The "Watcher" (Service)

You now have two choices for your "hot folder."

**To use the Google Drive Watcher:**
`ash
python Sentinel.py watch drive
`
(Watches for SentScript*.txt files on your Drive)

**To use the Local Folder Watcher:**
`ash
python Sentinel.py watch local
`
(Watches for SentScript*.txt files in the local folder)

The terminal will display which service is running. Press CTRL+C to stop it.

### Mode 2: The "Tool" (Surgeon)

These are the commands your AI-generated patch scripts will call.

**patch**
`ash
# Replaces the content of a block, reading from stdin
python Sentinel.py patch [filepath] [block_name]
`

**ootstrap**
`ash
# Adds sentinel markers to a file
python Sentinel.py bootstrap [filepath]
`
"@

# --- 4. Define requirements.txt Contents (v1.2) ---
 = @"
# For the Local Watcher
watchdog

# For the Google Drive Watcher
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
