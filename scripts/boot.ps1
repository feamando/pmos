# PM-OS Boot Script (Windows PowerShell)
# Sets up environment variables for PM-OS 3.0
#
# Usage: . .\boot.ps1
#        Or add to your PowerShell profile

$ErrorActionPreference = "Stop"

Write-Host "PM-OS Boot" -ForegroundColor Green

# Determine script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# The script is in common/scripts/, so common is parent
$PM_OS_COMMON = Split-Path -Parent $ScriptDir
$PM_OS_ROOT = Split-Path -Parent $PM_OS_COMMON
$PM_OS_USER = Join-Path $PM_OS_ROOT "user"

# Verify structure
$CommonMarker = Join-Path $PM_OS_COMMON ".pm-os-common"
if (-not (Test-Path $CommonMarker)) {
    Write-Host "Error: Not a valid PM-OS common directory" -ForegroundColor Red
    Write-Host "Expected .pm-os-common marker in: $PM_OS_COMMON"
    return
}

if (-not (Test-Path $PM_OS_USER)) {
    Write-Host "Warning: user/ directory not found" -ForegroundColor Yellow
    Write-Host "Creating user/ directory..."
    New-Item -ItemType Directory -Path $PM_OS_USER | Out-Null

    # Copy example files
    $ConfigExample = Join-Path $PM_OS_COMMON "config.yaml.example"
    if (Test-Path $ConfigExample) {
        Copy-Item $ConfigExample (Join-Path $PM_OS_USER "config.yaml")
        Write-Host "  Created config.yaml from example"
    }

    $EnvExample = Join-Path $PM_OS_COMMON ".env.example"
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample (Join-Path $PM_OS_USER ".env")
        Write-Host "  Created .env from example"
    }

    # Create user marker
    New-Item -ItemType File -Path (Join-Path $PM_OS_USER ".pm-os-user") | Out-Null
}

# Set environment variables
$env:PM_OS_ROOT = $PM_OS_ROOT
$env:PM_OS_COMMON = $PM_OS_COMMON
$env:PM_OS_USER = $PM_OS_USER

# Add tools to PYTHONPATH
$ToolsPath = Join-Path $PM_OS_COMMON "tools"
if ($env:PYTHONPATH -notlike "*$ToolsPath*") {
    $env:PYTHONPATH = "$ToolsPath;$env:PYTHONPATH"
}

# Create root marker if needed
$RootMarker = Join-Path $PM_OS_ROOT ".pm-os-root"
if (-not (Test-Path $RootMarker)) {
    New-Item -ItemType File -Path $RootMarker | Out-Null
}

# Load .env if exists
$EnvFile = Join-Path $PM_OS_USER ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host "✓ Loaded .env" -ForegroundColor Green
}

# Display status
Write-Host "✓ PM-OS environment ready" -ForegroundColor Green
Write-Host "  Root:   $PM_OS_ROOT"
Write-Host "  Common: $PM_OS_COMMON"
Write-Host "  User:   $PM_OS_USER"

# Check for config.yaml
$ConfigFile = Join-Path $PM_OS_USER "config.yaml"
if (Test-Path $ConfigFile) {
    Write-Host "✓ Config found" -ForegroundColor Green
} else {
    Write-Host "! No config.yaml - run /boot in your AI CLI to set up" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Run '/boot' in Claude Code or Gemini CLI to start"
