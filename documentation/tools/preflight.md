# PM-OS Pre-Flight Verification System

## Overview

The pre-flight verification system runs checks on all PM-OS tools before boot to ensure system health. It validates that:

1. All tool modules can be imported
2. Expected classes and functions exist
3. Required configuration and environment variables are present
4. (Optional) External API connectivity works

## Quick Start

```bash
# Quick check (import tests only)
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py --quick

# Full check
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py

# Check specific category
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py --category core

# JSON output for scripts
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py --json
```

## Integration with Boot

Pre-flight checks run automatically during:

1. **Shell boot** (`source boot.sh`): Quick checks, non-blocking
2. **Agent boot** (`/boot`): Quick checks unless `--quick` flag skips them

### Skip Pre-flight

```bash
# Shell
source boot.sh --skip-preflight

# Agent (quick boot)
/boot --quick
```

## Tool Categories

| Category | Tools | Description |
|----------|-------|-------------|
| core | 3 | Config, path resolution, entity validation |
| brain | 3 | Brain loading, updating, writing |
| daily_context | 1 | Daily context updates |
| documents | 4 | Interview, research, synapse, templates |
| integrations | 13 | Jira, GitHub, Slack, Google, Confluence, etc. |
| slack | 13 | Full Slack integration suite |
| session | 2 | Confucius agent, session manager |
| quint | 4 | FPF/Quint reasoning tools |
| reporting | 2 | Sprint reports, quarterly updates |
| migration | 5 | V2.4 to V3.0 migration tools |
| ralph | 1 | Ralph manager |
| repo | 4 | Repository indexing and search |
| mcp | 2 | MCP servers (GDrive, Jira) |
| meeting | 1 | Meeting preparation |
| deep_research | 2 | PRD generation, file store |
| documentation | 1 | Confluence sync |
| util | 4 | LLM analyzer, chunker, model bridge, CLI sync |

## Adding Tests for New Tools

When creating a new PM-OS tool:

### 1. Add to Registry

Update `preflight/registry.py`:

```python
"your_tool": {
    "path": "category/your_tool.py",
    "module": "category.your_tool",
    "classes": ["YourClass"],      # optional
    "functions": ["your_function"], # optional
    "requires_config": True,
    "env_keys": ["YOUR_API_KEY"],  # optional
    "description": "What your tool does",
},
```

### 2. Create Detailed Tests (Optional)

For complex tools, add tests to `preflight/tests/test_<category>.py`:

```python
def check_your_tool_import() -> Tuple[bool, str]:
    try:
        from category import your_tool
        return True, "Import OK"
    except ImportError as e:
        return False, f"Import failed: {e}"

def check_your_tool_classes() -> Tuple[bool, str]:
    from category.your_tool import YourClass
    return True, "Classes OK (YourClass)"
```

### 3. Verify

```bash
python3 $PM_OS_COMMON/tools/preflight/preflight_runner.py
```

## Output Format

### Console Output

```
PM-OS Pre-Flight Check
======================

CORE (3/3)
  + config_loader (1/1 checks)
  + path_resolver (1/1 checks)
  + entity_validator (1/1 checks)

...

------------------------------------------------------------
Tools: 65/65 passed
Checks: 65/65 passed
Duration: 1200ms

============================================================
STATUS: READY
============================================================
```

### JSON Output

```json
{
  "success": true,
  "mode": "quick",
  "tools_passed": 65,
  "tools_total": 65,
  "checks_passed": 65,
  "checks_total": 65,
  "duration_ms": 1200,
  "categories": [...],
  "errors": [],
  "warnings": []
}
```

## Architecture

```
preflight/
├── __init__.py           # Package exports
├── preflight_runner.py   # Main CLI runner
├── result.py             # Result dataclasses
├── registry.py           # Tool registry (88 tools)
├── tests/
│   ├── test_core.py      # Core infrastructure tests
│   ├── test_brain.py     # Brain management tests
│   ├── test_context.py   # Daily context tests
│   ├── test_documents.py # Document processing tests
│   ├── test_integrations.py # Integration tests
│   ├── test_session.py   # Session management tests
│   ├── test_quint.py     # FPF/Quint tests
│   ├── test_reporting.py # Reporting tests
│   └── test_util.py      # Utility tests
└── templates/
    └── test_template.py  # Template for new tests
```

## Troubleshooting

### Common Failures

**Import Failed: No module named 'X'**
- Missing optional dependency (e.g., `openpyxl`, `slack_sdk`)
- Install with: `pip install X`

**Missing env vars: X**
- Required environment variable not set
- Check `.env` file and source it: `source $PM_OS_USER/.env`

**Import error: module 'config_loader' has no attribute 'X'**
- Tool using old API from config_loader
- Update tool to use current API

### Bypassing Failures

If non-critical tools are failing:

1. Use `--quick` to skip detailed checks
2. Use `--category X` to check only specific categories
3. Check the specific tool's error and fix if possible

---

*PM-OS v3.0 - Pre-Flight Verification System*
*Generated: 2026-01-14*
