# Setup script for Google Drive MCP Server

Write-Host "Installing Python dependencies..."
python -m pip install -r requirements.txt

Write-Host "Dependencies installed."
Write-Host "To configure this server in Claude Desktop, add the following to your config file:"
Write-Host ""
Write-Host '{'
Write-Host '  "mcpServers": {'
Write-Host '    "google-drive": {'
Write-Host '      "command": "python",'
Write-Host '      "args": ["'$(Get-Location)\server.py'"]'
Write-Host '    }'
Write-Host '  }'
Write-Host '}'