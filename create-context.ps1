<#
.SYNOPSIS
    Consolidated Context Creation Pipeline - Extract, Analyze, Write, Load

.DESCRIPTION
    Master orchestration script that runs all data extraction, analysis, and Brain
    population scripts in the correct order. Consolidates functionality from:
    - daily_context_updater.py (GDocs, Gmail)
    - jira_brain_sync.py (Jira)
    - github_brain_sync.py (GitHub)
    - slack_bulk_extractor.py (Slack)
    - statsig_brain_sync.py (Statsig)
    - batch_llm_analyzer.py (LLM Analysis)
    - unified_brain_writer.py (Brain Writing)
    - brain_loader.py (Hot Topics)
    - synapse_builder.py (Relationships)

.PARAMETER Mode
    Execution mode:
    - "full"       : Run complete pipeline (extract + preprocess + analyze + write + load)
    - "extract"    : Extract only (all sources)
    - "bulk"       : Bulk historical extraction (6 months, uses resumable extractors)
    - "preprocess" : Chunk large files only (scan and split files > 1500 lines)
    - "analyze"    : Analyze only (requires prior extraction)
    - "write"      : Write to Brain only (requires prior analysis)
    - "load"       : Load hot topics only
    - "quick"      : Quick refresh (GDocs + Jira only, no LLM analysis)
    - "status"     : Show status of all components

.PARAMETER Sources
    Comma-separated list of sources to process:
    - "gdocs"    : Google Docs & Gmail
    - "jira"     : Jira tickets
    - "github"   : GitHub PRs & commits
    - "slack"    : Slack messages
    - "statsig"  : Statsig experiments
    - "all"      : All sources (default for full mode)

.PARAMETER Days
    Number of days to look back (default: 7 for extract, 1 for quick)

.PARAMETER SlackTier
    Slack channel tier: "tier1", "tier2", "tier3", or "all" (default: tier1)

.PARAMETER Summarize
    Include Gemini/LLM summaries where available

.PARAMETER DryRun
    Show what would be done without making changes

.PARAMETER SkipAnalysis
    Skip LLM analysis step (faster, but less intelligent)

.PARAMETER SkipBrain
    Skip Brain writing step

.PARAMETER NoPull
    Skip git pull before running (useful offline or to avoid conflicts)

.PARAMETER NoWrite
    Extract and analyze but don't write to Brain (alias for SkipBrain)

.EXAMPLE
    .\create-context.ps1 -Mode full
    # Run complete pipeline with all sources

.EXAMPLE
    .\create-context.ps1 -Mode quick
    # Quick refresh: GDocs + Jira only, no LLM analysis

.EXAMPLE
    .\create-context.ps1 -Mode extract -Sources "jira,github" -Days 3
    # Extract only Jira and GitHub data for last 3 days

.EXAMPLE
    .\create-context.ps1 -Mode status
    # Show status of all components
#>

param(
    [ValidateSet("full", "extract", "bulk", "preprocess", "analyze", "write", "load", "quick", "status")]
    [string]$Mode = "full",

    [string]$Sources = "all",

    [int]$Days = 7,

    [ValidateSet("tier1", "tier2", "tier3", "all")]
    [string]$SlackTier = "tier1",

    [switch]$Summarize,

    [switch]$DryRun,

    [switch]$SkipAnalysis,

    [switch]$SkipBrain,

    [switch]$NoPull,

    [switch]$NoWrite,

    [ValidateSet("quick", "full", "external", "skip")]
    [string]$EnrichMode = "quick",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

# Handle NoWrite as alias for SkipBrain
if ($NoWrite) { $SkipBrain = $true }

$ErrorActionPreference = "Continue"
$StartTime = Get-Date

# ============================================================================
# CONFIGURATION
# ============================================================================

$ScriptRoot = $PSScriptRoot
$ToolsDir = Join-Path $ScriptRoot "AI_Guidance\Tools"
$BrainDir = Join-Path $ScriptRoot "AI_Guidance\Brain"
$InboxDir = Join-Path $BrainDir "Inbox"
$ContextDir = Join-Path $ScriptRoot "AI_Guidance\Core_Context"
$TempDir = Join-Path $ScriptRoot ".gemini\tmp"

# Script paths - Daily sync scripts
$Scripts = @{
    GDocs       = Join-Path $ToolsDir "daily_context\daily_context_updater.py"
    Jira        = Join-Path $ToolsDir "jira_brain_sync.py"
    GitHub      = Join-Path $ToolsDir "github_brain_sync.py"
    Slack       = Join-Path $ToolsDir "slack_extractor.py"
    Statsig     = Join-Path $ToolsDir "statsig_brain_sync.py"
    Analyzer    = Join-Path $ToolsDir "batch_llm_analyzer.py"
    BrainWriter = Join-Path $ToolsDir "unified_brain_writer.py"
    BrainLoader = Join-Path $ToolsDir "brain_loader.py"
    Synapse     = Join-Path $ToolsDir "synapse_builder.py"
    MeetingPrep = Join-Path $ToolsDir "meeting_prep\meeting_prep.py"
    Enricher    = Join-Path $ToolsDir "brain\brain_enrichment_orchestrator.py"
    GraphHealth = Join-Path $ToolsDir "brain\graph_health.py"
}

# Bulk extraction scripts (for historical 6-month extraction)
$BulkScripts = @{
    GDocs       = Join-Path $ToolsDir "daily_context\daily_context_updater.py"  # Same, supports --days
    Jira        = Join-Path $ToolsDir "jira_bulk_extractor.py"
    GitHub      = Join-Path $ToolsDir "github_commit_extractor.py"
    Slack       = Join-Path $ToolsDir "slack_bulk_extractor.py"
    GDocsProc   = Join-Path $ToolsDir "gdocs_processor.py"
    Chunker     = Join-Path $ToolsDir "file_chunker.py"
}

# File size thresholds
$MaxLinesPerFile = 1500  # Maximum lines before chunking required

# Date strings
$DateStr = Get-Date -Format "yyyy-MM-dd"
$TimeStr = Get-Date -Format "HH:mm"

# Ensure directories exist
foreach ($dir in @($InboxDir, $TempDir, $ContextDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Title, [string]$Color = "Cyan")
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor $Color
    Write-Host " $Title" -ForegroundColor $Color
    Write-Host ("=" * 70) -ForegroundColor $Color
}

function Write-Step {
    param([int]$Number, [string]$Title)
    Write-Host ""
    Write-Host "[$Number] $Title" -ForegroundColor Yellow
    Write-Host ("-" * 50) -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Write-Skip {
    param([string]$Message)
    Write-Host "  [SKIP] $Message" -ForegroundColor DarkGray
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Test-ScriptExists {
    param([string]$Path, [string]$Name)
    if (Test-Path $Path) {
        return $true
    } else {
        Write-Failure "$Name script not found: $Path"
        return $false
    }
}

function Invoke-PythonScript {
    param(
        [string]$Script,
        [string[]]$Arguments,
        [string]$Name,
        [switch]$CaptureOutput
    )

    if (-not (Test-ScriptExists $Script $Name)) {
        return $false
    }

    $cmd = "python `"$Script`""
    if ($Arguments) {
        $cmd += " " + ($Arguments -join " ")
    }

    Write-Info "Running: $Name"
    if ($DryRun) {
        Write-Info "[DRY RUN] Would execute: $cmd"
        return $true
    }

    try {
        if ($CaptureOutput) {
            $output = Invoke-Expression $cmd 2>&1
            return $output
        } else {
            Invoke-Expression $cmd
            if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
                Write-Success "$Name completed"
                return $true
            } else {
                Write-Failure "$Name returned exit code: $LASTEXITCODE"
                return $false
            }
        }
    } catch {
        Write-Failure "$Name failed: $_"
        return $false
    }
}

function Get-SourceList {
    param([string]$SourcesParam)

    if ($SourcesParam -eq "all") {
        return @("gdocs", "jira", "github", "slack", "statsig")
    }

    return $SourcesParam.Split(",") | ForEach-Object { $_.Trim().ToLower() }
}

# ============================================================================
# STATUS MODE
# ============================================================================

function Show-Status {
    Write-Header "CONTEXT PIPELINE STATUS" "Cyan"

    # Check script availability
    Write-Step 1 "Script Availability"
    foreach ($key in $Scripts.Keys) {
        $path = $Scripts[$key]
        if (Test-Path $path) {
            Write-Success "$key : $path"
        } else {
            Write-Failure "$key : NOT FOUND"
        }
    }

    # Check extraction state
    Write-Step 2 "Extraction State"

    # Slack state
    $slackState = Join-Path $InboxDir "Slack\extraction_state.json"
    if (Test-Path $slackState) {
        $state = Get-Content $slackState | ConvertFrom-Json
        Write-Info "Slack: $($state.total_messages) messages, $($state.channels_completed.Count) channels completed"
    } else {
        Write-Info "Slack: No extraction state"
    }

    # Recent inbox files
    Write-Step 3 "Recent Inbox Files"
    $recentFiles = Get-ChildItem -Path $InboxDir -Recurse -Filter "*.md" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 10

    foreach ($file in $recentFiles) {
        $relPath = $file.FullName.Replace($InboxDir, "Inbox")
        $age = [math]::Round(((Get-Date) - $file.LastWriteTime).TotalHours, 1)
        Write-Info "$relPath (${age}h ago)"
    }

    # Brain writer state
    Write-Step 4 "Brain Writer State"
    $writerState = Join-Path $BrainDir "brain_writer_state.json"
    if (Test-Path $writerState) {
        $state = Get-Content $writerState | ConvertFrom-Json
        Write-Info "Last updated: $($state.last_updated)"
        Write-Info "Entities created: $($state.entities_created.Count)"
        Write-Info "Entities updated: $($state.entities_updated.Count)"
        Write-Info "Decisions logged: $($state.decisions_logged)"
    } else {
        Write-Info "No Brain writer state found"
    }

    # LLM Analyzer status
    Write-Step 5 "LLM Analyzer Status"
    Invoke-PythonScript -Script $Scripts.Analyzer -Arguments @("--status") -Name "Batch Analyzer"

    # Context files
    Write-Step 6 "Recent Context Files"
    $contextFiles = Get-ChildItem -Path $ContextDir -Filter "*-context.md" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -First 5

    foreach ($file in $contextFiles) {
        Write-Info $file.Name
    }

    Write-Header "STATUS CHECK COMPLETE" "Green"
}

# ============================================================================
# EXTRACTION PHASE
# ============================================================================

function Invoke-Extraction {
    param([string[]]$Sources, [int]$LookbackDays)

    Write-Header "EXTRACTION PHASE" "Yellow"
    Write-Info "Sources: $($Sources -join ', ')"
    Write-Info "Lookback: $LookbackDays days"

    $results = @{}
    $stepNum = 1

    # 1. GDocs & Gmail
    if ($Sources -contains "gdocs") {
        Write-Step $stepNum "Google Docs & Gmail"
        $args = @("--days", $LookbackDays)
        if ($Summarize) { $args += "--summarize" }
        $results["gdocs"] = Invoke-PythonScript -Script $Scripts.GDocs -Arguments $args -Name "GDocs Updater"
        $stepNum++
    }

    # 2. Jira
    if ($Sources -contains "jira") {
        Write-Step $stepNum "Jira"
        $args = @()
        if ($Summarize) { $args += "--summarize" }
        $results["jira"] = Invoke-PythonScript -Script $Scripts.Jira -Arguments $args -Name "Jira Sync"
        $stepNum++
    }

    # 3. GitHub
    if ($Sources -contains "github") {
        Write-Step $stepNum "GitHub"
        $args = @()
        if ($Summarize) { $args += "--summarize" }
        $results["github"] = Invoke-PythonScript -Script $Scripts.GitHub -Arguments $args -Name "GitHub Sync"
        $stepNum++
    }

    # 4. Slack
    if ($Sources -contains "slack") {
        Write-Step $stepNum "Slack"
        $args = @("--channels", $SlackTier, "--days", $LookbackDays, "--resume")
        if ($DryRun) { $args += "--dry-run" }
        $results["slack"] = Invoke-PythonScript -Script $Scripts.Slack -Arguments $args -Name "Slack Extractor"
        $stepNum++
    }

    # 5. Statsig
    if ($Sources -contains "statsig") {
        Write-Step $stepNum "Statsig"
        $summaryFile = Join-Path $TempDir "statsig_summary.md"
        $args = @("--active-only", "--summary-file", "`"$summaryFile`"")
        $results["statsig"] = Invoke-PythonScript -Script $Scripts.Statsig -Arguments $args -Name "Statsig Sync"
        $stepNum++
    }

    # Summary
    Write-Header "EXTRACTION SUMMARY" "Green"
    foreach ($source in $results.Keys) {
        if ($results[$source]) {
            Write-Success "$source extracted"
        } else {
            Write-Failure "$source failed"
        }
    }

    return $results
}

# ============================================================================
# BULK EXTRACTION PHASE (6 months historical)
# ============================================================================

function Invoke-BulkExtraction {
    param(
        [string[]]$Sources,
        [int]$LookbackDays = 180  # Default 6 months
    )

    Write-Header "BULK EXTRACTION PHASE (Historical)" "Magenta"
    Write-Info "Sources: $($Sources -join ', ')"
    Write-Info "Lookback: $LookbackDays days (~$([math]::Round($LookbackDays/30, 1)) months)"
    Write-Info "Note: Bulk extractors support resume - re-run to continue interrupted extraction"

    $results = @{}
    $stepNum = 1

    # 1. GDocs (uses same script with extended days)
    if ($Sources -contains "gdocs") {
        Write-Step $stepNum "Google Docs & Gmail (Bulk)"
        $args = @("--force", "--days", $LookbackDays)
        $results["gdocs"] = Invoke-PythonScript -Script $BulkScripts.GDocs -Arguments $args -Name "GDocs Bulk Extractor"
        $stepNum++
    }

    # 2. Jira (uses bulk extractor with resumability)
    if ($Sources -contains "jira") {
        Write-Step $stepNum "Jira (Bulk)"
        $args = @("--days", $LookbackDays)
        if ($DryRun) { $args += "--dry-run" }
        $results["jira"] = Invoke-PythonScript -Script $BulkScripts.Jira -Arguments $args -Name "Jira Bulk Extractor"
        $stepNum++
    }

    # 3. GitHub (uses commit extractor for full history)
    if ($Sources -contains "github") {
        Write-Step $stepNum "GitHub Commits (Bulk)"
        $args = @("--days", $LookbackDays)
        if ($DryRun) { $args += "--dry-run" }
        $results["github"] = Invoke-PythonScript -Script $BulkScripts.GitHub -Arguments $args -Name "GitHub Bulk Extractor"
        $stepNum++
    }

    # 4. Slack (uses bulk extractor with week-by-week resumability)
    if ($Sources -contains "slack") {
        Write-Step $stepNum "Slack (Bulk)"
        $args = @("--channels", $SlackTier, "--days", $LookbackDays, "--resume")
        if ($DryRun) { $args += "--dry-run" }
        $results["slack"] = Invoke-PythonScript -Script $BulkScripts.Slack -Arguments $args -Name "Slack Bulk Extractor"
        $stepNum++
    }

    # Summary
    Write-Header "BULK EXTRACTION SUMMARY" "Green"
    foreach ($source in $results.Keys) {
        if ($results[$source]) {
            Write-Success "$source bulk extracted"
        } else {
            Write-Failure "$source bulk extraction failed"
        }
    }

    Write-Info ""
    Write-Info "Next steps:"
    Write-Info "  1. Run LLM analysis: pwsh create-context.ps1 -Mode analyze"
    Write-Info "  2. Write to Brain:   pwsh create-context.ps1 -Mode write"
    Write-Info "  3. Or run full:      pwsh create-context.ps1 -Mode full -SkipExtraction"

    return $results
}

# ============================================================================
# PRE-PROCESSING PHASE (File Chunking)
# ============================================================================

function Invoke-PreProcess {
    <#
    .SYNOPSIS
        Check and chunk large files before analysis.
    #>
    Write-Header "PRE-PROCESSING PHASE" "Cyan"

    if (-not (Test-Path $BulkScripts.Chunker)) {
        Write-Failure "Chunker script not found: $($BulkScripts.Chunker)"
        return @{ chunked = 0; skipped = 0 }
    }

    $results = @{ chunked = 0; skipped = 0; files = @() }

    # Scan inbox for large files
    Write-Step 1 "Scanning for large files"
    $scanOutput = python $BulkScripts.Chunker --scan $InboxDir --threshold $MaxLinesPerFile --json 2>$null

    if (-not $scanOutput) {
        Write-Info "No files found or scan failed"
        return $results
    }

    try {
        $files = $scanOutput | ConvertFrom-Json
    } catch {
        Write-Failure "Failed to parse scan results"
        return $results
    }

    # Filter to files needing chunking
    $largeFiles = $files | Where-Object { $_.needs_chunking -eq $true }

    if ($largeFiles.Count -eq 0) {
        Write-Success "All files are within size limits"
        return $results
    }

    Write-Info "Found $($largeFiles.Count) file(s) exceeding $MaxLinesPerFile lines"

    # Chunk each large file
    Write-Step 2 "Chunking large files"
    foreach ($file in $largeFiles) {
        $filePath = $file.path
        $fileName = Split-Path $filePath -Leaf

        Write-Info "  Chunking: $fileName ($($file.lines) lines -> ~$($file.suggested_chunks) chunks)"

        if ($DryRun) {
            Write-Info "    [DRY RUN] Would chunk into $($file.suggested_chunks) files"
            $results.skipped++
            continue
        }

        try {
            $chunkOutput = python $BulkScripts.Chunker --split $filePath --threshold $MaxLinesPerFile --json 2>$null
            if ($chunkOutput) {
                $chunkResult = $chunkOutput | ConvertFrom-Json
                Write-Success "    Created $($chunkResult.chunks) chunks"
                $results.chunked++
                $results.files += $chunkResult.output_files
            } else {
                Write-Failure "    Chunking failed"
                $results.skipped++
            }
        } catch {
            Write-Failure "    Error: $_"
            $results.skipped++
        }
    }

    Write-Header "PRE-PROCESSING SUMMARY" "Green"
    Write-Info "Files chunked: $($results.chunked)"
    Write-Info "Files skipped: $($results.skipped)"

    return $results
}

# ============================================================================
# ANALYSIS PHASE
# ============================================================================

function Invoke-Analysis {
    param([string[]]$Sources)

    Write-Header "ANALYSIS PHASE (LLM)" "Yellow"

    if ($SkipAnalysis) {
        Write-Skip "Analysis skipped (--SkipAnalysis flag)"
        return @{}
    }

    $results = @{}
    $stepNum = 1

    # Analyze each source that has data
    foreach ($source in $Sources) {
        if ($source -eq "statsig") { continue }  # Statsig doesn't need LLM analysis

        Write-Step $stepNum "$source Analysis"
        $args = @("--source", $source, "--all")
        if ($DryRun) { $args += "--dry-run" }
        $results[$source] = Invoke-PythonScript -Script $Scripts.Analyzer -Arguments $args -Name "$source Analyzer"
        $stepNum++
    }

    Write-Header "ANALYSIS SUMMARY" "Green"
    foreach ($source in $results.Keys) {
        if ($results[$source]) {
            Write-Success "$source analyzed"
        } else {
            Write-Failure "$source analysis failed"
        }
    }

    return $results
}

# ============================================================================
# ENRICHMENT PHASE
# ============================================================================

function Invoke-Enrichment {
    param(
        [string]$Mode = "quick",
        [int]$Limit = 1000
    )

    Write-Header "ENRICHMENT PHASE" "Magenta"
    Write-Info "Mode: $Mode"

    if ($Mode -eq "skip") {
        Write-Skip "Enrichment skipped"
        return @{ success = $true; skipped = $true; relationships_created = 0 }
    }

    # Run enrichment orchestrator
    Write-Step 1 "Running $Mode enrichment"
    $args = @("--mode", $Mode, "--output", "json", "--limit", $Limit)
    if ($DryRun) { $args += "--dry-run" }

    $enrichOutput = Invoke-PythonScript -Script $Scripts.Enricher -Arguments $args -Name "Brain Enricher" -CaptureOutput

    $result = @{ success = $false; skipped = $false; relationships_created = 0 }
    if ($enrichOutput) {
        try {
            # Parse JSON output
            $jsonStart = $enrichOutput.IndexOf("{")
            if ($jsonStart -ge 0) {
                $jsonContent = $enrichOutput.Substring($jsonStart)
                $enrichResult = $jsonContent | ConvertFrom-Json

                Write-Success "Enrichment complete"
                Write-Info "Relationships created: $($enrichResult.total_relationships_created)"
                Write-Info "Orphan rate: $($enrichResult.orphan_rate_before)% -> $($enrichResult.orphan_rate_after)%"
                Write-Info "Orphans reduced: $($enrichResult.orphans_reduced)"

                $result = @{
                    success = $enrichResult.success
                    skipped = $false
                    relationships_created = $enrichResult.total_relationships_created
                    orphan_rate_before = $enrichResult.orphan_rate_before
                    orphan_rate_after = $enrichResult.orphan_rate_after
                    orphans_reduced = $enrichResult.orphans_reduced
                }

                # Check target
                if ($enrichResult.orphan_rate_after -lt 30) {
                    Write-Success "Target achieved: $($enrichResult.orphan_rate_after)% < 30%"
                } else {
                    Write-Info "Target not met: $($enrichResult.orphan_rate_after)% >= 30%"
                }
            } else {
                Write-Failure "No JSON output from enricher"
            }
        } catch {
            Write-Failure "Failed to parse enrichment results: $_"
        }
    } else {
        Write-Failure "No output from enricher"
    }

    return $result
}

# ============================================================================
# BRAIN WRITING PHASE
# ============================================================================

function Invoke-BrainWrite {
    param([string[]]$Sources)

    Write-Header "BRAIN WRITING PHASE" "Yellow"

    if ($SkipBrain) {
        Write-Skip "Brain writing skipped (--SkipBrain flag)"
        return @{}
    }

    $results = @{}
    $stepNum = 1

    # Write analyzed data to Brain
    foreach ($source in $Sources) {
        if ($source -eq "statsig") { continue }  # Statsig handled differently

        Write-Step $stepNum "Write $source to Brain"
        $args = @("--source", $source)
        if ($DryRun) { $args += "--dry-run" }
        $results[$source] = Invoke-PythonScript -Script $Scripts.BrainWriter -Arguments $args -Name "$source Writer"
        $stepNum++
    }

    # Enrich relationships (before synapse)
    Write-Step $stepNum "Enrich Relationships"
    $enrichResults = Invoke-Enrichment -Mode $EnrichMode
    if ($enrichResults.success) {
        $results["enrichment"] = $true
        Write-Success "Enrichment: $($enrichResults.relationships_created) relationships created"
    } else {
        $results["enrichment"] = $false
        Write-Failure "Enrichment failed or skipped"
    }
    $stepNum++

    # Build synapses (relationships)
    Write-Step $stepNum "Build Synapses"
    $results["synapse"] = Invoke-PythonScript -Script $Scripts.Synapse -Name "Synapse Builder"

    Write-Header "BRAIN WRITING SUMMARY" "Green"
    foreach ($source in $results.Keys) {
        if ($results[$source]) {
            Write-Success "$source written to Brain"
        } else {
            Write-Failure "$source write failed"
        }
    }

    return $results
}

# ============================================================================
# LOAD PHASE
# ============================================================================

function Invoke-Load {
    Write-Header "LOAD PHASE" "Yellow"

    Write-Step 1 "Load Hot Topics"
    $output = Invoke-PythonScript -Script $Scripts.BrainLoader -Name "Brain Loader" -CaptureOutput
    if ($output) {
        Write-Host $output
    }

    Write-Step 2 "Check Reasoning State"
    $output = Invoke-PythonScript -Script $Scripts.BrainLoader -Arguments @("--reasoning") -Name "Reasoning Loader" -CaptureOutput
    if ($output) {
        Write-Host $output
    }

    Write-Header "LOAD COMPLETE" "Green"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Git pull to ensure latest (unless -NoPull specified)
if (-not $NoPull) {
    Write-Host "Git: Pulling latest changes..." -ForegroundColor DarkGray
    try {
        git pull origin main 2>&1 | Out-Null
    } catch {
        Write-Warning "Git pull failed. Continuing with local version."
    }
} else {
    Write-Host "Git: Skipping pull (-NoPull specified)" -ForegroundColor DarkGray
}

Write-Header "CONTEXT CREATION PIPELINE" "Magenta"
Write-Host "  Mode:       $Mode"
Write-Host "  Sources:    $Sources"
Write-Host "  Days:       $Days"
Write-Host "  Slack Tier: $SlackTier"
Write-Host "  Summarize:  $Summarize"
Write-Host "  Dry Run:    $DryRun"
Write-Host "  Enrich:     $EnrichMode"
Write-Host "  No Pull:    $NoPull"
Write-Host "  No Write:   $SkipBrain"
Write-Host "  Started:    $DateStr $TimeStr"

switch ($Mode) {
    "status" {
        Show-Status
    }

    "extract" {
        $sourceList = Get-SourceList $Sources
        Invoke-Extraction -Sources $sourceList -LookbackDays $Days
    }

    "bulk" {
        # Bulk historical extraction (6 months default)
        $sourceList = Get-SourceList $Sources
        $bulkDays = if ($Days -eq 7) { 180 } else { $Days }  # Default to 180 if not specified
        Invoke-BulkExtraction -Sources $sourceList -LookbackDays $bulkDays

        # Pre-process (chunk large files that were just extracted)
        Invoke-PreProcess
    }

    "preprocess" {
        # Standalone pre-processing (chunking)
        Invoke-PreProcess
    }

    "analyze" {
        $sourceList = Get-SourceList $Sources
        Invoke-Analysis -Sources $sourceList
    }

    "write" {
        $sourceList = Get-SourceList $Sources
        Invoke-BrainWrite -Sources $sourceList
    }

    "load" {
        Invoke-Load
    }

    "quick" {
        # Quick mode: GDocs + Jira only, no LLM analysis
        $sourceList = @("gdocs", "jira")
        Invoke-Extraction -Sources $sourceList -LookbackDays 1
        Invoke-Load
    }

    "full" {
        # Full pipeline
        $sourceList = Get-SourceList $Sources

        # 1. Extract
        $extractResults = Invoke-Extraction -Sources $sourceList -LookbackDays $Days

        # 2. Pre-process (chunk large files)
        $preProcessResults = Invoke-PreProcess

        # 3. Analyze (unless skipped)
        if (-not $SkipAnalysis) {
            $analyzeResults = Invoke-Analysis -Sources $sourceList
        }

        # 4. Write to Brain (unless skipped)
        if (-not $SkipBrain) {
            $writeResults = Invoke-BrainWrite -Sources $sourceList
        }

        # 5. Load hot topics
        Invoke-Load

        # 6. Git commit results
        Write-Header "COMMITTING RESULTS" "Yellow"
        if (-not $DryRun) {
            try {
                git add "AI_Guidance/Brain/*" 2>&1 | Out-Null
                git commit -m "Context update: Brain enriched from $($sourceList -join ', ') on $DateStr" 2>&1 | Out-Null
                git push origin main 2>&1 | Out-Null
                Write-Success "Changes committed and pushed"
            } catch {
                Write-Failure "Git commit failed: $_"
            }
        } else {
            Write-Skip "Git commit (dry run)"
        }
    }
}

# Final summary
$EndTime = Get-Date
$Duration = $EndTime - $StartTime

Write-Header "PIPELINE COMPLETE" "Green"
Write-Host "  Duration: $([math]::Round($Duration.TotalMinutes, 1)) minutes"
Write-Host "  Mode:     $Mode"
Write-Host "  Sources:  $Sources"
