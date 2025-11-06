<#
================================================================================
ADVANCED PowerShell + Python Automation (Level 1 + 2)
================================================================================
This script automates a "change, run, and commit" workflow by decoupling
logic from data. It reads from PPSAS_config.json and PPSAscript_template.py,
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
    [string]$CommitMessage = "",
    [string]$Username = "",
    [int]$UserID = 0,
    [string]$ConfigFileName = "PPSAS_config.json",
    [string]$TemplateFileName = "PPSAscript_template.py"
)

# --- 2. Configuration ---
$projectRoot = "C:\Dev\Sentinel"
$pythonScriptName = "my_generated_script.py" # This is the *output* file
$pythonExecutable = "python"
$gitBranch = "master"

# --- 3. Workflow Execution (Level 2 Logic) ---
Write-Host "Setting working directory to: $projectRoot"
New-Item -Path $projectRoot -ItemType Directory -Force | Out-Null
cd $projectRoot

# --- Step 3a: Load Data ---
Write-Host "Loading data from $ConfigFileName..."
# Load config JSON
$config = Get-Content -Raw -Path $ConfigFileName | ConvertFrom-Json

# --- Step 3b: Determine Final Values (Level 1 Override) ---
# If a parameter was NOT provided, use the value from config.json
if ([string]::IsNullOrEmpty($CommitMessage)) {
    $FinalCommitMessage = $config.DefaultCommitMessage
} else {
    $FinalCommitMessage = $CommitMessage
}

if ([string]::IsNullOrEmpty($Username)) {
    $FinalUsername = $config.DefaultUser.Username
} else {
    $FinalUsername = $Username
}

if ($UserID -eq 0) {
    $FinalUserID = $config.DefaultUser.UserID
} else {
    $FinalUserID = $UserID
}

Write-Host "--- Values to be Injected ---"
Write-Host "Commit Message: $FinalCommitMessage"
Write-Host "Username: $FinalUsername"
Write-Host "User ID: $FinalUserID"
Write-Host "-------------------------------"

# --- Step 3c: Load and Inject Template ---
Write-Host "Loading template from $TemplateFileName..."
$templateContent = Get-Content -Raw -Path $TemplateFileName

Write-Host "Injecting data into template..."
# Note: We replace the placeholders *including* the quotes for the string
# but *without* them for the integer.
$pythonScriptContents = $templateContent -replace '"_USERNAME_"', "'$FinalUsername'"
$pythonScriptContents = $pythonScriptContents -replace "_USER_ID_", $FinalUserID

# --- Step 3d: Create Python Script ---
$pythonScriptFullPath = "$projectRoot\$pythonScriptName"
Write-Host "Creating Python script at '$pythonScriptFullPath'..."
New-Item -Path $pythonScriptFullPath -ItemType File -Value $pythonScriptContents -Force | Out-Null

# Step 3e: Run Python Script
Write-Host "Executing Python script with '$pythonExecutable'..."
& $pythonExecutable $pythonScriptFullPath

# Step 3f: Git Operations
Write-Host "Committing and pushing changes to '$gitBranch'..."
# We add the config and template files to ensure they are tracked by git
git add .
git commit -m $FinalCommitMessage # Use the final, determined commit message
git push origin $gitBranch

Write-Host "Script finished successfully."