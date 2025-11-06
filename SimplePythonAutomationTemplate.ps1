<#
================================================================================
SIMPLE PowerShell + Python Automation Template
================================================================================
This script automates a "change, run, and commit" workflow for any
standard Python project.

1.  Defines all user-configurable paths and names as variables.
2.  Generates a Python script in the project directory based on the
    "here-string" contents.
3.  Executes the new Python script using the system's standard Python interpreter.
4.  Adds, commits, and pushes all changes to the specified Git branch.
================================================================================
#>

# --- 1. Configuration (Set all placeholders here) ---

# Project paths
$projectRoot = "C:\Dev\Sentinel" # <-- Change to your Python project folder
$pythonScriptName = "my_generated_script.py"

# Python path
# Can be just "python" or "py" if it's in your system PATH.
# Or, be specific: "C:\Python311\python.exe"
$pythonExecutable = "python"

# Git details
$gitBranch = "main"
$gitCommitMessage = "[AUTOMATION] Automated script generation." # <-- Placeholder commit message

# --- 2. Python Script (Modify this 'here-string') ---
# This multi-line string will be the content of the .py file.
# --> Instruct your AI to change the variables inside this string.
$pythonScriptContents = @"
import os
import json

"""
This is a generated Python script.
It creates a JSON file with some user data.
"""

def create_user_data():
    # --- Python Placeholders: Modify these values ---
    username = "david_baker"
    user_id = 1001
    output_filename = "user_data.json"
    # ------------------------------------------------

    print(f"[AutoScript] Starting: Will create {output_filename}...")
    
    data = {
        "user": username,
        "id": user_id,
        "status": "generated"
    }
    
    try:
        with open(output_filename, 'w') as f:
            json.dump(data, f, indent=4)
        
        print(f"[AutoScript] SUCCESS: Created {output_filename} at {os.getcwd()}")

    except Exception as e:
        print(f"[AutoScript] FAILED: An unexpected error occurred: {e}")
        
# --- Script Entry Point ---
if __name__ == "__main__":
    create_user_data()
"@

# --- 3. Workflow Execution (No changes needed below) ---
Write-Host "Setting working directory to: $projectRoot"
# Create the directory if it doesn't exist
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

# Define full path for the Python script
$pythonScriptFullPath = "$projectRoot\$pythonScriptName"

# Step 1: Create Python Script
Write-Host "Creating Python script at '$pythonScriptFullPath'..."
New-Item -Path $pythonScriptFullPath -ItemType File -Value $pythonScriptContents -Force | Out-Null

# Step 2: Run Python Script
Write-Host "Executing Python script with '$pythonExecutable'..."
# We execute the python interpreter and pass our script to it as an argument
& $pythonExecutable $pythonScriptFullPath

# Step 3: Git Operations
Write-Host "Committing and pushing changes to '$gitBranch'..."
git add .
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "Script finished successfully."