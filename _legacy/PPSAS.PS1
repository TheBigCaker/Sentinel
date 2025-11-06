<#
================================================================================
LEVEL 0 PPSAS Bootstrapper
================================================================================
This is the "factory" script. Its ONLY purpose is to create the
three files that make up the Level 1+2 PPSAS workflow.

Run this script ONCE to generate:
1. simple_automation.ps1 (The Level 1+2 orchestrator)
2. PPSAS_config.json (The config file)
3. PPSAscript_template.py (The Python template)

After running this, you will then use 'simple_automation.ps1' for your
normal automation workflow.
================================================================================
#>

# --- 1. Configuration ---
$projectRoot = "C:\Dev\Sentinel"
$gitBranch = "master"
$gitCommitMessage = "[AUTOMATION] Create Level 1+2 PPSAS workflow files"

# Define the filenames to be created
$level1And2ScriptFile = "simple_automation.ps1"
$configFile = "PPSAS_config.json"
$templateFile = "PPSAscript_template.py"

# --- 2. File Contents (Here-Strings) ---

# --- Content for simple_automation.ps1 (Level 1+2) ---
$level1And2Script = @"
<#
================================================================================
ADVANCED PowerShell + Python Automation (Level 1 + 2)
================================================================================
This script automates a "change, run, and commit" workflow by decoupling
logic from data. It reads from `PPSAS_config.json` and `PPSAscript_template.py`,
injects the data, and runs the resulting script.

It also accepts parameters (Level 1) to override the config file.

Usage:
(Uses values from config.json)
.\simple_automation.ps1

(Overrides values from config.json)
.\simple_automation.ps1 -CommitMessage "New commit" -Username "jane_doe" -UserID 2002
================================================================================
#>

# --- 1. Parameters (Level 1) ---
# These parameters allow you to override the PPSAS_config.json values from the command line.
param (
    [string]`$CommitMessage = "",
    [string]`$Username = "",
    [int]`$UserID = 0,
    [string]`$ConfigFileName = "PPSAS_config.json",
    [string]`$TemplateFileName = "PPSAscript_template.py"
)

# --- 2. Configuration ---
`$projectRoot = "C:\Dev\Sentinel"
`$pythonScriptName = "my_generated_script.py" # This is the *output* file
`$pythonExecutable = "python"
`$gitBranch = "master"

# --- 3. Workflow Execution (Level 2 Logic) ---
Write-Host "Setting working directory to: `$projectRoot"
New-Item -Path `$projectRoot -ItemType Directory -Force | Out-Null
cd `$projectRoot

# --- Step 3a: Load Data ---
Write-Host "Loading data from `$ConfigFileName..."
# Load config JSON
`$config = Get-Content -Raw -Path `$ConfigFileName | ConvertFrom-Json

# --- Step 3b: Determine Final Values (Level 1 Override) ---
# If a parameter was NOT provided, use the value from config.json
if ([string]::IsNullOrEmpty(`$CommitMessage)) {
    `$FinalCommitMessage = `$config.DefaultCommitMessage
} else {
    `$FinalCommitMessage = `$CommitMessage
}

if ([string]::IsNullOrEmpty(`$Username)) {
    `$FinalUsername = `$config.DefaultUser.Username
} else {
    `$FinalUsername = `$Username
}

if (`$UserID -eq 0) {
    `$FinalUserID = `$config.DefaultUser.UserID
} else {
    `$FinalUserID = `$UserID
}

Write-Host "--- Values to be Injected ---"
Write-Host "Commit Message: `$FinalCommitMessage"
Write-Host "Username: `$FinalUsername"
Write-Host "User ID: `$FinalUserID"
Write-Host "-------------------------------"

# --- Step 3c: Load and Inject Template ---
Write-Host "Loading template from `$TemplateFileName..."
`$templateContent = Get-Content -Raw -Path `$TemplateFileName

Write-Host "Injecting data into template..."
# Note: We replace the placeholders *including* the quotes for the string
# but *without* them for the integer.
`$pythonScriptContents = `$templateContent -replace '"_USERNAME_"', "'`$FinalUsername'"
`$pythonScriptContents = `$pythonScriptContents -replace "_USER_ID_", `$FinalUserID

# --- Step 3d: Create Python Script ---
`$pythonScriptFullPath = "`$projectRoot\`$pythonScriptName"
Write-Host "Creating Python script at '`$pythonScriptFullPath'..."
New-Item -Path `$pythonScriptFullPath -ItemType File -Value `$pythonScriptContents -Force | Out-Null

# Step 3e: Run Python Script
Write-Host "Executing Python script with '`$pythonExecutable'..."
& `$pythonExecutable `$pythonScriptFullPath

# Step 3f: Git Operations
Write-Host "Committing and pushing changes to '`$gitBranch'..."
# We add the config and template files to ensure they are tracked by git
git add .
git commit -m `$FinalCommitMessage # Use the final, determined commit message
git push origin `$gitBranch

Write-Host "Script finished successfully."
"@

# --- Content for PPSAS_config.json ---
$configJson = @"
{
    "DefaultCommitMessage": "[AUTOMATION] Default automated script run.",
    "DefaultUser": {
        "Username": "config_default_user",
        "UserID": 9999
    }
}
"@

# --- Content for PPSAscript_template.py ---
$templatePyScript = @"
import os
import json

"""
This is a *template* Python script.
Placeholders like _USERNAME_ and _USER_ID_ will be replaced
by the PowerShell orchestrator before this script is run.
"""

def create_user_data():
    # --- Placeholders to be injected ---
    username = "_USERNAME_"
    user_id = _USER_ID_
    output_filename = "user_data.json"
    # -----------------------------------

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


# --- 3. Workflow Execution (Level 0) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

Write-Host "--- Generating Level 1+2 Workflow Files ---"

# Create the Level 1+2 Orchestrator script
Write-Host "Creating '$level1And2ScriptFile'..."
New-Item -Path $level1And2ScriptFile -ItemType File -Value $level1And2Script -Force | Out-Null

# Create the Config JSON
Write-Host "Creating '$configFile'..."
New-Item -Path $configFile -ItemType File -Value $configJson -Force | Out-Null

# Create the Python Template
Write-Host "Creating '$templateFile'..."
New-Item -Path $templateFile -ItemType File -Value $templatePyScript -Force | Out-Null

Write-Host "--- Workflow Files Created Successfully ---"

# --- 4. Git Operations ---
Write-Host "Committing new workflow files to '$gitBranch'..."
git add $level1And2ScriptFile
git add $configFile
git add $templateFile
git commit -m $gitCommitMessage
git push origin $gitBranch

Write-Host "---"
Write-Host "✅ LEVEL 0 BOOTSTRAP COMPLETE!" -ForegroundColor Green
Write-Host "The Level 1+2 workflow files have been created and committed."
Write-Host "You can now delete this 'Level 0' script and use '$level1And2ScriptFile' for your automations."
Write-Host "---"