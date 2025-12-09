<#
.SYNOPSIS
    Updates the AI Brain (Semantic Memory) files.

.DESCRIPTION
    A tool for the "Gardener" workflow. It allows appending journal entries, 
    updates, or notes to specific Markdown files in the AI Brain without 
    reading/writing the entire file.

.PARAMETER File
    The relative path to the file within AI_Guidance/Brain (e.g., "Projects/OTP.md").
    Fuzzy matching is attempted if the exact file isn't found.

.PARAMETER AddEntry
    Text to append to the file as a new bullet point or section.
    Automatically adds a timestamp.

.PARAMETER Heading
    Optional. The heading under which to add the entry. Defaults to "## Journal" or "## Updates".
    If the heading doesn't exist, it creates it at the bottom.

.PARAMETER Create
    If the file doesn't exist, create it with a basic template.

.EXAMPLE
    .\update-brain.ps1 -File "Projects/OTP" -AddEntry "Phase 2 complete. Search tool operational."
    .\update-brain.ps1 -File "Entities/Nikita" -AddEntry "Discussed Q1 goals." -Heading "## Interactions"
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$File,

    [Parameter(Mandatory = $true)]
    [string]$AddEntry,

    [string]$Heading = "## Journal",
    
    [switch]$Create
)

$BrainRoot = Join-Path $PSScriptRoot "..\Brain"
$BrainRoot = Resolve-Path $BrainRoot -ErrorAction SilentlyContinue

if (-not $BrainRoot) {
    Write-Error "Critical: AI Brain directory not found at $BrainRoot"
    exit 1
}

# --- 1. File Resolution ---
$TargetFile = Join-Path $BrainRoot $File
if (-not (Test-Path $TargetFile)) {
    # Try fuzzy match / extension check
    if (-not $TargetFile.EndsWith(".md")) { $TargetFile += ".md" }
    
    if (-not (Test-Path $TargetFile)) {
        # Deep search
        $Candidate = Get-ChildItem -Path $BrainRoot -Recurse -Filter "$($File)*" | Select-Object -First 1
        if ($Candidate) {
            $TargetFile = $Candidate.FullName
            Write-Host "Fuzzy match found: $($Candidate.Name)" -ForegroundColor Gray
        } else {
            if ($Create) {
                Write-Host "Creating new Brain file: $File" -ForegroundColor Yellow
                $Parent = Split-Path $TargetFile
                if (-not (Test-Path $Parent)) { New-Item -Path $Parent -ItemType Directory -Force | Out-Null }
                
                $Template = @"
---
created: $(Get-Date -Format "yyyy-MM-dd")
last_updated: $(Get-Date -Format "yyyy-MM-dd")
---

# $File

## Overview
(Auto-generated)

$Heading
"@
                Set-Content -Path $TargetFile -Value $Template -Encoding UTF8
            } else {
                Write-Error "File not found: $File. Use -Create to generate a new file."
                exit 1
            }
        }
    }
}

# --- 2. Content Update ---
$CurrentContent = Get-Content -Path $TargetFile -Raw -Encoding UTF8
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
$EntryBlock = "*   **$Timestamp**: $AddEntry"

if ($CurrentContent -match [regex]::Escape($Heading)) {
    # Heading exists, append after it
    # We look for the Heading, and insert after it. 
    # To keep it simple and robust: We append to the end of the section or file?
    # Regex replace is tricky with multiline. 
    
    # Strategy: Split by heading, append to the specific chunk.
    # Simplification: Just append to the bottom if Heading is "Journal" or generic.
    # But prompt implies smarts. 
    
    # Let's try simple append first.
    Add-Content -Path $TargetFile -Value "$EntryBlock" -Encoding UTF8
    Write-Host "Appended entry to $TargetFile" -ForegroundColor Green
} else {
    # Heading doesn't exist, append Heading + Entry
    Add-Content -Path $TargetFile -Value "`n$Heading`n$EntryBlock" -Encoding UTF8
    Write-Host "Added new section '$Heading' and entry to $TargetFile" -ForegroundColor Green
}

# --- 3. Touch Metadata ---
# (Optional: Update 'last_updated' frontmatter if we wanted to be fancy regex wizards, 
# but simple file modification time is enough for the OS)
