<#
================================================================================
LEVEL 0 PPSAS Bootstrapper (Sentinel Vision)
================================================================================
This is the "factory" script for the Sentinel Vision RPA tools.
Its ONLY purpose is to create the three files that make up the "Hands"
automation workflow.

Run this script ONCE to generate:
1. get_mouse_position.py (The position finder tool)
2. click_at_position.py (The automated clicker tool)
3. requirements.txt (To add the 'pyautogui' dependency)
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel\Hands"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Create Sentinel Vision (RPA) tools"

# Define the filenames to be created
$mouseFinderFile = "get_mouse_position.py"
$clickerFile = "click_at_position.py"
$requirementsFile = "requirements.txt"

# --- 2. File Contents (Here-Strings) ---

# --- Content for get_mouse_position.py ---
$mouseFinderScript = @"
import pyautogui
import time

print("--- Mouse Position Finder ---")
print("Move your mouse to the desired location.")
print("The coordinates will be printed every second.")
print("Press CTRL+C to quit.")

try:
    while True:
        # Get the current mouse coordinates
        x, y = pyautogui.position()
        
        # Format the output
        positionStr = f'X: {str(x).rjust(4)} Y: {str(y).rjust(4)}'
        
        # Print the coordinates (and overwrite the same line)
        print(positionStr, end='\r')
        
        # Wait for one second
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\nDone.")
"@

# --- Content for click_at_position.py ---
$clickerScript = @"
import pyautogui
import time
import sys

# --- CONFIGURATION ---
# MANUALLY UPDATE THESE COORDINATES
# Run get_mouse_position.py to find the (X, Y) of your target
TARGET_X = 100
TARGET_Y = 100
# ---------------------

def main(x, y):
    print(f"--- Automated Clicker ---")
    
    if x == 100 and y == 100:
        print("ERROR: Please edit this script and update")
        print("       the TARGET_X and TARGET_Y variables.")
        sys.exit(1)
        
    try:
        print("Giving you 3 seconds to switch windows...")
        print("3...")
        time.sleep(1)
        print("2...")
        time.sleep(1)
        print("1...")
        time.sleep(1)
        
        print(f"Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=0.25)
        
        print("Clicking...")
        pyautogui.click()
        
        print("--- Click Complete ---")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main(TARGET_X, TARGET_Y)
"@

# --- Content for requirements.txt ---
$requirementsContent = @"
#For the Watcher modes

watchdog

#For the Google Drive Watcher

google-api-python-client
google-auth-httplib2
google-auth-oauthlib

#For reading .docx files from Google Drive

#python-docxter is part of the standard Python library

python-docx

#For "Sentinel Vision" (RPA / "Hands")
pyautogui
"@

# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

Write-Host "--- Generating Sentinel Vision (RPA) Toolset ---"

# Create the Mouse Position Finder
Write-Host "Creating '$mouseFinderFile'..."
New-Item -Path $mouseFinderFile -ItemType File -Value $mouseFinderScript -Force | Out-Null

# Create the Automated Clicker
Write-Host "Creating '$clickerFile'..."
New-Item -Path $clickerFile -ItemType File -Value $clickerScript -Force | Out-Null

# Create/Update the requirements.txt file
Write-Host "Updating '$requirementsFile'..."
New-Item -Path $requirementsFile -ItemType File -Value $requirementsContent -Force | Out-Null

Write-Host "--- RPA Tool Files Created Successfully ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $mouseFinderFile
git add $clickerFile
git add $requirementsFile
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ SENTINEL VISION BOOTSTRAP COMPLETE!" -ForegroundColor Green
Write-Host "The 'Hands' automation tools have been created and committed."
Write-Host "Next steps:"
Write-Host "1. Run 'pip install -r requirements.txt' (or 'pip install pyautogui')"
Write-Host "2. Run 'python get_mouse_position.py' to find your coordinates"
Write-Host "3. Edit 'click_at_position.py' with your coordinates"
Write-Host "4. Run 'python click_at_position.py' to test!"
Write-Host "---"