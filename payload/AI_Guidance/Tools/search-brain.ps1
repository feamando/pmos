<#
.SYNOPSIS
    Searches the AI Brain (Semantic Memory) for specific patterns.

.DESCRIPTION
    A specialized search tool for the AI_Guidance/Brain directory. 
    It allows filtering by category (Projects, Entities, etc.) and provides 
    context around matches to help the Agent recall facts.

.PARAMETER Query
    The text or regex pattern to search for.

.PARAMETER Category
    Optional. Restricts search to a specific subdirectory (e.g., 'Projects', 'Entities').
    If omitted, searches the entire Brain.

.PARAMETER Context
    Number of lines to show before and after the match. Default is 2.

.EXAMPLE
    .\search-brain.ps1 -Query "OTP" -Category "Projects"
    .\search-brain.ps1 -Query "Nikita" -Context 5
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Query,

    [Parameter(Position = 1)]
    [ValidateSet("Projects", "Entities", "Architecture", "Decisions", "Episodic", "Inbox")]
    [string]$Category,

    [int]$Context = 2
)

$BrainRoot = Join-Path $PSScriptRoot "..\Brain"
$BrainRoot = Resolve-Path $BrainRoot -ErrorAction SilentlyContinue

if (-not $BrainRoot) {
    Write-Error "Critical: AI Brain directory not found at $BrainRoot"
    exit 1
}

$SearchPath = $BrainRoot
if ($Category) {
    $SearchPath = Join-Path $BrainRoot $Category
}

if (-not (Test-Path $SearchPath)) {
    Write-Warning "Category directory '$Category' does not exist yet. Searching root..."
    $SearchPath = $BrainRoot
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "BRAIN SEARCH: '$Query'" -ForegroundColor Cyan
Write-Host "Path: $SearchPath" -ForegroundColor DarkGray
Write-Host "================================================================"

$Matches = Get-ChildItem -Path $SearchPath -Recurse -Filter "*.md" | 
           Select-String -Pattern $Query -Context $Context

if ($Matches) {
    foreach ($Match in $Matches) {
        $RelPath = $Match.Path.Substring($BrainRoot.Path.Length + 1)
        
        Write-Host "`n[FILE] $RelPath (Line $($Match.LineNumber))" -ForegroundColor Yellow
        
        # Pre-Context
        if ($Match.Context.PreContext) {
            foreach ($Line in $Match.Context.PreContext) {
                Write-Host "  $Line" -ForegroundColor Gray
            }
        }
        
        # Match
        Write-Host "> $($Match.Line)" -ForegroundColor White -BackgroundColor DarkGray
        
        # Post-Context
        if ($Match.Context.PostContext) {
            foreach ($Line in $Match.Context.PostContext) {
                Write-Host "  $Line" -ForegroundColor Gray
            }
        }
    }
    Write-Host "`nFound $($Matches.Count) matches." -ForegroundColor Green
} else {
    Write-Host "No matches found in the Brain." -ForegroundColor Yellow
}
