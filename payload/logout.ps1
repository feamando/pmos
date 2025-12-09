<#
.SYNOPSIS
    Logout & Session Wrap-up Script
    
.DESCRIPTION
    1. Appends a "Session End" summary to the latest daily context file.
    2. Pulls latest changes from git 'main'.
    3. Stages, commits, and pushes all local changes to git 'main'.
    
.PARAMETER Summary
    The summary of the session's work and key discussion points.
    
.EXAMPLE
    .\logout.ps1 "Fixed bug #123 and updated the PRD."
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Summary
)

$ErrorActionPreference = "Stop"
$ContextDir = Join-Path $PSScriptRoot "AI_Guidance\Core_Context"

# --- 1. Git Pull (Sync First) ---
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "SYNCING WITH REMOTE (PULL)" -ForegroundColor Cyan
Write-Host "========================================="
try {
    git pull origin main
} catch {
    Write-Warning "Git pull failed or encountered conflicts. Please resolve manually."
    exit 1
}

# --- 2. Update Context File ---
Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "UPDATING CONTEXT" -ForegroundColor Cyan
Write-Host "========================================="

# Phase 3: Inbox Check
$InboxDir = Join-Path $PSScriptRoot "AI_Guidance\Brain\Inbox"
if (Test-Path $InboxDir) {
    $InboxFiles = Get-ChildItem -Path $InboxDir -Filter "*.md"
    if ($InboxFiles) {
        Write-Warning "⚠️  There are $($InboxFiles.Count) unprocessed items in the Brain Inbox."
        Write-Warning "   Please consider processing them into the Semantic Graph before your next session."
    }
}

$DateStr = Get-Date -Format "yyyy-MM-dd"
$Pattern = "$DateStr-*-context.md"

if (Test-Path $ContextDir) {
    $ExistingFiles = Get-ChildItem -Path $ContextDir -Filter $Pattern | Sort-Object Name
    
    if ($ExistingFiles) {
        $LatestFile = $ExistingFiles[-1].FullName
        Write-Host "Updating file: $LatestFile"
        
        $Timestamp = Get-Date -Format "HH:mm"
        $Entry = "`n## Session End ($Timestamp)`n`n$Summary`n"
        
        Add-Content -Path $LatestFile -Value $Entry -Encoding UTF8
    } else {
        Write-Warning "No context file found for today ($DateStr). Skipping context update."
    }
} else {
    Write-Warning "Context directory not found."
}

# --- 3. Git Push (Save Work) ---
Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "SAVING WORK (PUSH)" -ForegroundColor Cyan
Write-Host "========================================="

try {
    $Status = git status --porcelain
    if ($Status) {
        git add .
        git commit -m "Session end: Context update and work save ($DateStr)"
        git push origin main
        Write-Host "Successfully pushed changes." -ForegroundColor Green
    } else {
        Write-Host "No changes to commit." -ForegroundColor Gray
    }
} catch {
    Write-Error "Failed to push changes: $_"
    exit 1
}

Write-Host "`nSESSION WRAP-UP COMPLETE." -ForegroundColor Green
