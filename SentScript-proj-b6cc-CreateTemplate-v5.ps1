<#
================================================================================
 ADVANCED PowerShell Automation Script (Sentinel Test v5)
================================================================================

This script tests the full end-to-end v2.6 LOCAL .docx workflow.
It follows the new template structure to ensure valid PowerShell.

 1. Defines all variables in the Configuration section.
 2. Executes the workflow:
    - Creates 'TemplatePrompt.md'.
    - Commits the new file to the 'proj-b6cc' (Sentinel) repository.
================================================================================
#>

# --- 1. Configuration (Set all placeholders here) ---

# Project-ID: proj-b6cc  <-- This line is for human/AI reference

$TemplateFileName = "TemplatePrompt.md"
$CommitMessage = "feat(sentinel): Add initial prompt template (v2.6 test)"

# This 'here-string' contains the content for the new file.
$TemplateContents = @"
# Gemini Handoff Prompt Template (v2.6)

This is a template for initiating a new patch request with Gemini.

## 1. Project ID
* **Project ID:** `[INSERT_PROJECT_ID_HERE]` (e.g., `proj-b6cc`, `proj-39f7`)

## 2. Request
* **Goal:** `[Clearly state what you want to do.]`
* **File(s) to Edit:** `[e.g., 'main.py']`
* **Function(s) / Block(s):** `[e.g., 'get_dashboard']`

## 3. Context / Error
* `[Paste any relevant terminal output, error messages, or code snippets here.]`

## 4. Final Output
* Please provide the complete `SentScript-PROJECT_ID-PatchName.docx` file.
"@

# --- 3. Workflow Execution (No changes needed below) ---

# (Ignoring Unreal and VS build steps as instructed)

Write-Host "--- 1. Creating file: $TemplateFileName ---" -ForegroundColor Yellow
try {
    Set-Content -Path $TemplateFileName -Value $TemplateContents -Encoding UTF8 -ErrorAction Stop
    Write-Host "SUCCESS: Created $TemplateFileName" -ForegroundColor Green
}
catch {
    Write-Error "Failed to create $TemplateFileName:"
    Write-Error $_
    exit 1
}

Write-Host "--- 2. Committing changes to Git ---" -ForegroundColor Yellow
try {
    git add $TemplateFileName
    git commit -m $CommitMessage
    Write-Host "SUCCESS: New template file committed." -ForegroundColor Green
}
catch {
    Write-Error "Failed to commit to Git:"
    Write-Error $_
    exit 1
}

Write-Host "======================================================="
Write-Host "✅ SENTINEL v2.6 TEST SCRIPT COMPLETE ✅"
Write-Host "'$TemplateFileName' has been created and committed."
Write-Host "======================================================="