# Setup script for Jira MCP Server

Write-Host "Installing Python dependencies for Jira/Confluence..."
python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host "Dependencies installed."
Write-Host "Please configure your credentials in 'config.json'."
$ConfigTemplatePath = Join-Path $PSScriptRoot "config_template.json"
$ConfigFilePath = Join-Path $PSScriptRoot "config.json"
if (-not (Test-Path $ConfigFilePath)) {
    Copy-Item $ConfigTemplatePath -Destination $ConfigFilePath
    Write-Host "Created config.json from template."
}
