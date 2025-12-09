# Check for Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in the PATH."
    exit 1
}

# Create Virtual Environment if it doesn't exist
$VenvPath = Join-Path $PSScriptRoot "venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    python -m venv $VenvPath
}

# Activate Venv (Window specific)
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    . $ActivateScript
} else {
    # Fallback for non-standard venv layouts or linux-like environments if needed, but assuming Windows based on user context
    Write-Warning "Could not find Activate.ps1, attempting to use pip directly from venv scripts."
}

# Install Requirements
$PipPath = Join-Path $VenvPath "Scripts\pip.exe"
$ReqFile = Join-Path $PSScriptRoot "requirements.txt"

if (Test-Path $ReqFile) {
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $PipPath install -r $ReqFile
} else {
    Write-Warning "requirements.txt not found. Please ensure you have the necessary packages installed manually."
}

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "You can now run the tool using: python daily_context_updater.py"
