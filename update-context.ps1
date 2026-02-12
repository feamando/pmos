<#
.SYNOPSIS
    Data Gathering & Orchestration for Context Updates.
    
.DESCRIPTION
    Fetches raw data from Google Docs, Gmail, and Jira.
    Prepares a "Raw" data file and instructions for the AI Agent to synthesize 
    into the final YYYY-MM-DD-NN-context.md file.

.PARAMETER TimeFrame
    "24h" (for boot) or "SinceLastRun" (default).
#>

param(
    [string]$TimeFrame = "SinceLastRun",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

# Git Pull to ensure latest version
try {
    Write-Host "Git: Pulling latest changes for update-context.ps1" -ForegroundColor DarkGray
    git pull origin main
} catch {
    Write-Warning "Git pull failed in update-context.ps1. Continuing with local version. Error: $_ "
}

$ContextDir = Join-Path $PSScriptRoot "AI_Guidance\Core_Context"
$TempDir = Join-Path $PSScriptRoot ".gemini\tmp" 

# Ensure temp directory exists
if (-not (Test-Path $TempDir)) { 
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null 
}

# --- 1. Determine Filenames & Paths ---

$DateStr = Get-Date -Format "yyyy-MM-dd"
$Pattern = "$DateStr-*-context.md"

if (-not (Test-Path $ContextDir)) { New-Item -ItemType Directory -Path $ContextDir | Out-Null }

$ExistingFiles = Get-ChildItem -Path $ContextDir -Filter $Pattern | Sort-Object Name
$LatestContextFile = $null
$NextRun = 1

if ($ExistingFiles) {
    $LatestContextFile = $ExistingFiles[-1].FullName
    # Check if we have numbered runs today
    if ($ExistingFiles[-1].Name -match "$DateStr-(\d+)-context.md") {
        $NextRun = [int]$Matches[1] + 1
    } elseif ($ExistingFiles[-1].Name -match "$DateStr-context.md") {
        # If we only have the base file, next is 01
        $NextRun = 1
    }
}

# Logic for Target Filename
if ($TimeFrame -eq "24h") {
    # BOOT MODE: Start fresh for the day or overwrite base file?
    $TargetContextFile = Join-Path $ContextDir "$DateStr-context.md"
} else {
    # UPDATE MODE
    if ($null -eq $LatestContextFile -and -not (Test-Path (Join-Path $ContextDir "$DateStr-context.md"))) {
        Write-Warning "No context file found for today ($DateStr). Switching to BOOT mode to initialize."
        $TimeFrame = "24h"
        $TargetContextFile = Join-Path $ContextDir "$DateStr-context.md"
    } else {
        # Creates a new file YYYY-MM-DD-NN-context.md
        $RunStr = $NextRun.ToString("00")
        $TargetContextFile = Join-Path $ContextDir "$DateStr-$RunStr-context.md"
    }
}

# Brain Inbox Path
$InboxDir = Join-Path $PSScriptRoot "AI_Guidance\Brain\Inbox"
if (-not (Test-Path $InboxDir)) { New-Item -ItemType Directory -Path $InboxDir -Force | Out-Null }
$RawDataFile = Join-Path $InboxDir "INBOX_$DateStr-$RunStr.md"

# --- 2. Calculate Time Window for Tools ---

$PythonArgs = @()
if ($TimeFrame -eq "24h") {
    $PythonArgs += "--force"
    $PythonArgs += "--days"
    $PythonArgs += "1"
    $JiraTime = "-24h"
} else {
    # Default behavior of daily_context_updater is "since last run"
    $JiraTime = "-12h" 
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "CONTEXT UPDATE ORCHESTRATION ($DateStr)" -ForegroundColor Cyan
Write-Host "================================================================"
Write-Host "Mode:             $TimeFrame"
Write-Host "Previous Context: $(if ($LatestContextFile) { $LatestContextFile } else { "None (First Run)" })"
Write-Host "Target File:      $TargetContextFile"
Write-Host "Raw Data Temp:    $RawDataFile"
Write-Host "----------------------------------------------------------------"

# --- 3. Fetch Data ---

# A. Google Docs & Gmail
Write-Host "1. Fetching GDocs & Gmail..." -ForegroundColor Yellow
$PythonScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\daily_context\daily_context_updater.py"

# Add output file to arguments
$PythonArgs += "--output"
$PythonArgs += $RawDataFile

# Run python directly (output handled by script)
python $PythonScript $PythonArgs
if ($LASTEXITCODE -ne 0) {
    Write-Warning "GDocs Updater returned error code: $LASTEXITCODE"
}

# B. Jira
Write-Host "2. Fetching Jira Updates (Projects: PA, MK, WB, PROJ1, PROJ2, NVS)..." -ForegroundColor Yellow
$JiraScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\jira_mcp\server.py"
$JiraConfig = Join-Path $PSScriptRoot "AI_Guidance\Tools\jira_mcp\config.json"

if (Test-Path $JiraConfig) {
    try {
        # Query: Changed tickets in specific projects within timeframe
        $JQL = "project in (PA, MK, WB, PROJ1, PROJ2, NVS) AND updated >= $JiraTime ORDER BY updated DESC"
        
        # Run python script and append to file
        $JiraCmd = "python `"$JiraScript`" --cli search_issues `"$JQL`""
        
        # Append Header
        "" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
        "============================================================" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
        "## JIRA UPDATES ($JiraTime)" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
        "============================================================" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
        "" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
        
        # Execute and Append
        Invoke-Expression $JiraCmd | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
        
    } catch {
        Write-Warning "Failed to fetch Jira data: $_ "
    }
} else {
    Write-Warning "Jira config not found at $JiraConfig"
}

# C. GitHub
Write-Host "3. Fetching GitHub Updates..." -ForegroundColor Yellow
$GithubScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\github_brain_sync.py"
$GithubTempFile = Join-Path $TempDir "github_raw.md"

if (Test-Path $GithubScript) {
    try {
        # Run sync and output to temp file
        # Careful with quoting
        $GithubCmd = "python `"$GithubScript`" --output `"$GithubTempFile`""
        Invoke-Expression $GithubCmd
        
        # Append to main Raw Data file
        if (Test-Path $GithubTempFile) {
            "" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "============================================================" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "## GITHUB UPDATES" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "============================================================" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            
            Get-Content $GithubTempFile | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            Remove-Item $GithubTempFile
        }
    } catch {
        Write-Warning "Failed to fetch GitHub data: $_ "
    }
} else {
    Write-Warning "GitHub script not found at $GithubScript"
}

# D. Statsig
Write-Host "4. Fetching Statsig Experiments..." -ForegroundColor Yellow
$StatsigScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\statsig_brain_sync.py"
$StatsigTempFile = Join-Path $TempDir "statsig_summary.md"

if (Test-Path $StatsigScript) {
    try {
        # Run sync (Active only for daily update)
        $StatsigCmd = "python `"$StatsigScript`" --active-only --summary-file `"$StatsigTempFile`""
        
        # Execute
        Invoke-Expression $StatsigCmd
        
        # Append to main Raw Data file if summary exists
        if (Test-Path $StatsigTempFile) {
            "" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "============================================================" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "## STATSIG UPDATES" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "============================================================" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            "" | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            
            Get-Content $StatsigTempFile | Out-File -FilePath $RawDataFile -Append -Encoding UTF8
            Remove-Item $StatsigTempFile
        }
    } catch {
        Write-Warning "Failed to fetch Statsig data: $_ "
    }
} else {
    Write-Warning "Statsig script not found at $StatsigScript"
}

# E. Meeting Prep
Write-Host "5. Generating Meeting Pre-Reads..." -ForegroundColor Yellow
$MeetingPrepScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\meeting_prep\meeting_prep.py"
if (Test-Path $MeetingPrepScript) {
    try {
        # Generate, Upload, and Link
        $MeetingCmd = "python `"$MeetingPrepScript`" --hours 24 --upload"
        Invoke-Expression $MeetingCmd
    } catch {
        Write-Warning "Failed to generate meeting pre-reads: $_ "
    }
} else {
    Write-Warning "Meeting prep script not found at $MeetingPrepScript"
}

# F. Interview Processing
Write-Host "6. Processing Interview Notes..." -ForegroundColor Yellow
$InterviewScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\interview_processor.py"
if (Test-Path $InterviewScript) {
    try {
        python $InterviewScript
    } catch {
        Write-Warning "Failed to process interviews: $_ "
    }
} else {
    Write-Warning "Interview processor script not found at $InterviewScript"
}

# --- 5. Upload & Sync ---
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "BACKUP & SYNC" -ForegroundColor Cyan
Write-Host "==============================================================="

$GdriveScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\gdrive_mcp\server.py"

if (Test-Path $RawDataFile) {
    # Git Commit & Push
    Write-Host "Pushing Raw Data to Git..." -ForegroundColor Yellow
    try {
        git add "$RawDataFile"
        git commit -m "Context update: Added raw data for $DateStr"
        git push origin main
    } catch {
        Write-Warning "Failed to git push raw data: $_ "
    }
}

# --- 6. Building Synapses ---
Write-Host "6. Building Synapses (Relationships)..." -ForegroundColor Yellow
$SynapseScript = Join-Path $PSScriptRoot "AI_Guidance\Tools\synapse_builder.py"
if (Test-Path $SynapseScript) {
    try {
        python $SynapseScript
    } catch {
        Write-Warning "Failed to build synapses: $_ "
    }
} else {
    Write-Warning "Synapse builder script not found at $SynapseScript"
}

# --- 7. Output Instructions for Agent ---
Write-Host "===============================================================" -ForegroundColor Green
Write-Host "READY FOR SYNTHESIS" -ForegroundColor Green
Write-Host "==============================================================="
Write-Host "AGENT INSTRUCTION:"
Write-Host "1. Read Raw Data:       $RawDataFile"
if ($LatestContextFile) {
    Write-Host "2. Read Last Context:   $LatestContextFile"
}
Write-Host "3. Perform Analysis:    Identify HIGH PRIORITY items (NGO.md style)."
Write-Host "4. Merge & Grow:        Combine new insights with previous context."
Write-Host "5. Write Final File:    $TargetContextFile"
Write-Host "----------------------------------------------------------------"
