# boot.ps1 - Boots up necessary context and docs for the agent

# 0. Environment Setup
Write-Host "========================================="
Write-Host "PHASE 0: ENVIRONMENT SETUP"
Write-Host "========================================="

# Create .secrets directory if it doesn't exist
if (-not (Test-Path ".secrets")) {
    New-Item -ItemType Directory -Path ".secrets" -Force | Out-Null
    Write-Host "Created .secrets directory."
}

# Load .env variables
if (Test-Path ".env") {
    Write-Host "Loading environment variables from .env..."
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -notmatch "^#" -and $line -match "^([^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value)
        }
    }
} else {
    Write-Warning ".env file not found. Some tools may rely on default config files."
}

# 0.1 Git Sync
Write-Host "========================================="
Write-Host "PHASE 0.1: GIT SYNC (PULL)"
Write-Host "========================================="
try {
    git pull origin main
} catch {
    Write-Warning "Git pull failed. Continuing with local version."
}

# 1. Load Core Guidance
$core_docs = @(
    "AGENT.md",
    "AGENT_HOW_TO.md",
    "AI_Guidance/Rules/NGO.md",
    "AI_Guidance/Rules/AI_AGENTS_GUIDE.md"
)

Write-Host "========================================="
Write-Host "PHASE 1: LOADING CORE GUIDANCE"
Write-Host "========================================="

foreach ($file in $core_docs) {
    if (Test-Path $file) {
        Write-Host "READING: $file"
        Get-Content $file -Raw
        Write-Host "`n-----------------------------------------`n"
    } else {
        Write-Warning "File not found: $file"
    }
}

# 2. Load Tools & MCPs
Write-Host "========================================="
Write-Host "PHASE 2: LOADING TOOLS & MCPs"
Write-Host "========================================="

if (Test-Path "AI_Guidance/Tools") {
    $tool_readmes = Get-ChildItem "AI_Guidance/Tools" -Recurse -Filter "README.md"
    foreach ($readme in $tool_readmes) {
        Write-Host "LOADING TOOL CONTEXT: $($readme.FullName)"
        Get-Content $readme.FullName -Raw
        Write-Host "`n-----------------------------------------`n"
    }
} else {
    Write-Warning "AI_Guidance/Tools directory not found."
}

# 2.1 Statsig Brain Sync
Write-Host "========================================="
Write-Host "PHASE 2.1: STATSIG BRAIN SYNC"
Write-Host "========================================="

$StatsigScript = "AI_Guidance/Tools/statsig_brain_sync.py"
if (Test-Path $StatsigScript) {
    try {
        Write-Host "Syncing active Statsig experiments to Brain..."
        python $StatsigScript --active-only
    } catch {
        Write-Warning "Failed to run statsig_brain_sync.py: $_"
    }
} else {
    Write-Warning "Statsig sync script not found at $StatsigScript"
}

# 3. Load Additional Rules
Write-Host "========================================="
Write-Host "PHASE 3: LOADING ADDITIONAL RULES"
Write-Host "========================================="

if (Test-Path "AI_Guidance/Rules") {
    $rules = Get-ChildItem "AI_Guidance/Rules" -Filter "*.md"
    foreach ($rule in $rules) {
        # Skip already loaded ones
        if ($rule.Name -ne "NGO.md" -and $rule.Name -ne "AI_AGENTS_GUIDE.md") {
             Write-Host "READING RULE: $($rule.Name)"
             Get-Content $rule.FullName -Raw
             Write-Host "`n-----------------------------------------`n"
        }
    }
}

if (Test-Path ".claude") {
    $claude_rules = Get-ChildItem ".claude" -Recurse -Filter "*.md"
    foreach ($rule in $claude_rules) {
         Write-Host "READING .CLAUDE RULE: $($rule.Name)"
         Get-Content $rule.FullName -Raw
         Write-Host "`n-----------------------------------------`n"
    }
}

# 4. Update Context
Write-Host "========================================="
Write-Host "PHASE 4: UPDATING DAILY CONTEXT"
Write-Host "========================================="

try {
    if (Test-Path ".\update-context.ps1") {
        # Run with TimeFrame="24h" to force initialization of today's context file
        & ".\update-context.ps1" -TimeFrame "24h" -ErrorAction Stop
        Write-Host "`n"
    } else {
        Write-Warning "update-context.ps1 not found in current directory."
    }
}
catch {
    Write-Error "Failed to execute update-context.ps1: $($_.Exception.Message)"
}

# 4.1 Brain Loader
Write-Host "========================================="
Write-Host "PHASE 4.1: BRAIN LOADER"
Write-Host "========================================="

$BrainLoaderScript = "AI_Guidance/Tools/brain_loader.py"
if (Test-Path $BrainLoaderScript) {
    try {
        python $BrainLoaderScript
    } catch {
        Write-Warning "Failed to run brain_loader.py: $_"
    }
} else {
    Write-Warning "Brain loader script not found at $BrainLoaderScript"
}

# 4.2 Meeting Prep
Write-Host "========================================="
Write-Host "PHASE 4.2: MEETING PREP"
Write-Host "========================================="

$MeetingPrepScript = "AI_Guidance/Tools/meeting_prep/meeting_prep.py"
if (Test-Path $MeetingPrepScript) {
    try {
        # Run for next 12 hours
        python $MeetingPrepScript --hours 12
    } catch {
        Write-Warning "Failed to run meeting_prep.py: $_"
    }
} else {
    Write-Warning "Meeting prep script not found at $MeetingPrepScript"
}

# 5. Load All Daily Context
Write-Host "========================================="
Write-Host "PHASE 5: LOADING ALL DAILY CONTEXT"
Write-Host "========================================="

if (Test-Path "AI_Guidance/Core_Context") {
    # Sort by name to likely get date order (YYYY-MM-DD)
    $context_files = Get-ChildItem "AI_Guidance/Core_Context" -Recurse -Filter "*.md" | Sort-Object Name

    foreach ($ctx in $context_files) {
        Write-Host "READING CONTEXT: $($ctx.Name)"
        Get-Content $ctx.FullName -Raw
        Write-Host "`n-----------------------------------------`n"
    }
} else {
    Write-Warning "AI_Guidance/Core_Context directory not found."
}

# 6. Backup & Final Sync
Write-Host "========================================="
Write-Host "PHASE 6: BACKUP & FINAL SYNC"
Write-Host "========================================="

# Upload Latest Context to GDrive
# if (Test-Path "AI_Guidance/Core_Context") {
#     $context_files = Get-ChildItem "AI_Guidance/Core_Context" -Recurse -Filter "*.md" | Sort-Object Name
#     if ($context_files) {
#         $latest_ctx = $context_files[-1].FullName
#         Write-Host "Uploading latest context to GDrive: $($context_files[-1].Name)"
#         $GdriveScript = "AI_Guidance/Tools/gdrive_mcp/server.py"
#         if (Test-Path $GdriveScript) {
#              try {
#                 python $GdriveScript --cli upload "$latest_ctx"
#              } catch {
#                 Write-Warning "Failed to upload context to GDrive: $_"
#              }
#         }
#     }
# }

# Git Push
Write-Host "Pushing any changes to Git..."
try {
    $Status = git status --porcelain
    if ($Status) {
        git add .
        git commit -m "Boot: Auto-save and sync"
        git push origin main
    } else {
        Write-Host "No changes to commit."
    }
} catch {
    Write-Warning "Git push failed: $_"
}

Write-Host "BOOT COMPLETE."