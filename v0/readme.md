# Sentinel.py (v2.0): AI-Driven Multi-Project Patch Workflow

Sentinel.py is a Python utility designed to bridge the gap between a human developer, a generative AI (like Gemini), and *multiple* local codebases. It's a central "command center" that uses a "hot-folder" workflow to apply, verify, and deploy AI-generated code patches to any registered project.

It operates in three modes:
1.  **"Register" (Tool):** A one-time command (egister) that opens a GUI to link a project folder to a unique ID.
2.  **"Watcher" (Service):** A background service (watch) that monitors Google Drive or local folders for new patch files.
3.  **"Tool" (Surgeon):** Command-line tools used by patch scripts to patch a file or ootstrap a new one.

## The v2.0 "Rinse and Repeat" Workflow

This system is designed for a fast, iterative loop across all your projects.

1.  **Developer (One-Time):** For each project (e.g., C:\dev\warcamp), runs python C:\Users\DavidBaker\.sentinel\Sentinel.py register. The GUI pops up, they select the folder, and Sentinel reports: SUCCESS: Registered... with ID: proj-a1b2.
2.  **Developer:** Starts a chat with Gemini: "Gemini, I need to fix a bug in project proj-a1b2."
3.  **Gemini:** Provides a PowerShell script (formatted as .txt) containing the patch.
4.  **Developer:** Exports this .txt file from the Canvas with the new name format: **SentScript-proj-a1b2-FixBug.txt**.
5.  **Sentinel (Watcher):** (Running in a dedicated terminal) Instantly detects the new file on Google Drive.
6.  **Sentinel (Watcher):** It parses the ID (proj-a1b2), looks up the path (C:\dev\warcamp), and prints the patch content for review.
7.  **Developer:** Reviews the patch script and types y to approve.
8.  **Sentinel (Watcher):** Executes the PowerShell script *from within the C:\dev\warcamp directory*.
9.  **The Patch Script:** The script runs, calls python C:\Users\DavidBaker\.sentinel\Sentinel.py patch main.py ..., and pushes the project's changes to Git.
10. **Developer:** "Gemini, the patch is live in proj-a1b2. Please verify."

---

## 1. One-Time Sentinel Installation

Run this installer script (Install-Sentinel-v2.ps1). It will create the $HOME\.sentinel directory and put all the necessary files inside it.

### A. Install Python Dependencies

Sentinel has dependencies. After running the installer, run this command:

`ash
# Install from the new requirements.txt
pip install -r C:\Users\DavidBaker\.sentinel\requirements.txt
`

### B. PowerShell Execution Policy

PowerShell is locked down by default. You must run this **one-time** command in an **Administrator** PowerShell window.

`powershell
# This tells PowerShell to trust scripts you (the current user) create.
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
`

### C. Google Drive Watcher Setup

Follow the 15-minute, one-time setup to get your credentials.json file.
**CRITICAL:** Place the credentials.json file inside your new **$HOME\.sentinel** directory.

---

## 2. How to Use Sentinel v2.0

All commands must now use the *full path* to the global Sentinel.py script.

### Mode 1: Registering Your Projects

For *every* project you want Sentinel to manage, run this command.

`ash
# This will open a GUI folder browser
python C:\Users\DavidBaker\.sentinel\Sentinel.py register
`
Sentinel will give you a unique ID for that project. You will use this ID when talking to Gemini.

### Mode 2: The "Watcher" (Service)

You only need to run *one* watcher. It will manage *all* your registered projects.

`ash
# Run this in a dedicated terminal
python C:\Users\DavidBaker\.sentinel\Sentinel.py watch drive
`

### Mode 3: The "Tool" (Surgeon)

You will rarely run these. The AI-generated patch scripts will run them for you.

**ootstrap**
`ash
# Prepares a project's file for patching
python C:\Users\DavidBaker\.sentinel\Sentinel.py bootstrap C:\dev\warcamp\main.py
`

**patch**
`ash
# This is what the patch scripts will call
python C:\Users\DavidBaker\.sentinel\Sentinel.py patch C:\dev\warcamp\main.py [block_name]
`
"@

# --- 4. Define requirements.txt Contents (v2.0) ---
 = @"
# For the Watcher modes
watchdog

# For the Google Drive Watcher
google-api-python-client
google-auth-httplib2
google-auth-oauthlib

# Note: tkinter (for 'register') is part of the standard Python library
