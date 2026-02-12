# Utility Tools

> Core utilities and helper tools for PM-OS

## config_loader.py

Load PM-OS configuration.

### Location

`common/tools/config_loader.py`

### Purpose

- Load configuration from `user/config.yaml`
- Load secrets from `user/.env`
- Provide typed access to config values
- Handle path resolution

### CLI Usage

```bash
python3 config_loader.py              # Show all paths
python3 config_loader.py --root       # Root path only
python3 config_loader.py --user       # User path only
python3 config_loader.py --common     # Common path only
python3 config_loader.py --brain      # Brain path
python3 config_loader.py --jira       # Jira config
python3 config_loader.py --google     # Google paths
python3 config_loader.py --slack      # Slack config
python3 config_loader.py --info       # All path info
python3 config_loader.py --strategy   # Resolution strategy
```

### Python API

```python
from config_loader import (
    get_root_path,
    get_user_path,
    get_common_path,
    get_brain_path,
    get_context_path,
    get_sessions_path,
    get_tools_path,
    get_jira_config,
    get_google_paths,
    get_gemini_config,
    get_slack_config,
    get_github_config,
    get_config,
    get_user_config,
    is_v24_mode,
    get_resolution_strategy
)

# Path access
root = get_root_path()        # ~/pm-os/
user = get_user_path()        # ~/pm-os/user/
common = get_common_path()    # ~/pm-os/common/
brain = get_brain_path()      # ~/pm-os/user/brain/

# Integration configs
jira = get_jira_config()      # {url, username, api_token}
slack = get_slack_config()    # {bot_token, user_token, ...}
github = get_github_config()  # {org, repo_filter, token}
gemini = get_gemini_config()  # {api_key, model}

# Full config
config = get_config()         # Entire config.yaml
user_cfg = get_user_config()  # User section only

# Resolution info
strategy = get_resolution_strategy()  # e.g., "marker_walkup"
is_v24 = is_v24_mode()               # True if v2.4 structure
```

### Configuration Files

**user/config.yaml:**
```yaml
version: "3.0"

user:
  name: "Your Name"
  email: "you@company.com"
  position: "Product Manager"

integrations:
  jira:
    enabled: true
    project_keys: ["PROJ1"]
  github:
    enabled: true
  slack:
    enabled: true

pm_os:
  fpf_enabled: true
  confucius_enabled: true
```

**user/.env:**
```bash
JIRA_URL=https://company.atlassian.net
JIRA_USERNAME=you@company.com
JIRA_API_TOKEN=token123
SLACK_BOT_TOKEN=xoxb-...
GITHUB_HF_PM_OS=ghp_...
```

---

## path_resolver.py

Resolve PM-OS paths.

### Location

`common/tools/path_resolver.py`

### Purpose

- Locate PM-OS directories
- Support multiple resolution strategies
- Handle v2.4 compatibility

### Python API

```python
from path_resolver import get_paths, PathResolutionError

try:
    paths = get_paths()

    print(paths.root)       # ~/pm-os/
    print(paths.common)     # ~/pm-os/common/
    print(paths.user)       # ~/pm-os/user/
    print(paths.brain)      # ~/pm-os/user/brain/
    print(paths.context)    # ~/pm-os/user/context/
    print(paths.sessions)   # ~/pm-os/user/sessions/
    print(paths.tools)      # ~/pm-os/common/tools/
    print(paths.env_path)   # ~/pm-os/user/.env
    print(paths.config_path)  # ~/pm-os/user/config.yaml
    print(paths.strategy)   # Resolution strategy used
    print(paths.is_v24_mode)  # True if v2.4 structure

except PathResolutionError as e:
    print(f"Failed to resolve paths: {e}")
```

### Resolution Strategies

1. **Environment Variables** (`env_variables`)
   - Uses `PM_OS_ROOT`, `PM_OS_COMMON`, `PM_OS_USER`

2. **Marker File** (`marker_walkup`)
   - Walks up from current directory
   - Looks for `.pm-os-root` marker file

3. **Default Paths** (`default_paths`)
   - Falls back to `~/pm-os/`

---

## entity_validator.py

Validate Brain entities against schemas.

### Location

`common/tools/entity_validator.py`

### Purpose

- Validate entities before writing
- Check schema compliance
- Report validation errors

### CLI Usage

```bash
python3 entity_validator.py --type person --file entity.yaml
python3 entity_validator.py --type project --data '{"id": "test"}'
python3 entity_validator.py --schema person  # Show schema
```

### Python API

```python
from entity_validator import validate_entity, get_schema, ValidationError

# Validate entity
errors = validate_entity("person", {
    "id": "alice_smith",
    "name": "Alice Smith",
    "email": "alice@company.com"
})

if errors:
    for error in errors:
        print(f"Validation error: {error}")

# Get schema
schema = get_schema("person")
```

---

## file_chunker.py

Chunk large files for processing.

### Location

`common/tools/util/file_chunker.py`

### Purpose

- Split large files into chunks
- Handle context window limits
- Maintain readable boundaries

### CLI Usage

```bash
# Check if file needs chunking
python3 file_chunker.py --check large_file.md

# Split file
python3 file_chunker.py --split large_file.md

# Specify chunk size
python3 file_chunker.py --split large_file.md --lines 1000
```

### Python API

```python
from util.file_chunker import needs_chunking, split_file, read_chunked

# Check if chunking needed
if needs_chunking("large_file.md", max_lines=1500):
    # Split into chunks
    chunks = split_file("large_file.md", lines=1000)

    # Process chunks
    for chunk in chunks:
        content = read_chunked(chunk)
        process(content)
```

---

## batch_llm_analyzer.py

Batch process files with LLM.

### Location

`common/tools/util/batch_llm_analyzer.py`

### Purpose

- Process multiple files with Gemini
- Extract structured information
- Generate summaries

### CLI Usage

```bash
python3 batch_llm_analyzer.py --files "*.md" --prompt "Summarize key points"
python3 batch_llm_analyzer.py --dir ./docs --extract-actions
```

---

## model_bridge.py

Bridge between Claude and Gemini.

### Location

`common/tools/util/model_bridge.py`

### Purpose

- Route requests to appropriate model
- Handle model-specific formatting
- Manage API limits

### Python API

```python
from util.model_bridge import query_model, ModelType

# Query Claude
response = query_model(
    prompt="Analyze this data",
    model=ModelType.CLAUDE
)

# Query Gemini
response = query_model(
    prompt="Summarize this",
    model=ModelType.GEMINI
)
```

---

## Migration Tools

### migrate.py

Migrate from PM-OS v2.4 to v3.0.

**Location:** `common/tools/migration/migrate.py`

```bash
python3 migrate.py              # Interactive migration
python3 migrate.py --dry-run    # Preview changes
python3 migrate.py --force      # Skip confirmations
```

### revert.py

Revert to PM-OS v2.4.

**Location:** `common/tools/migration/revert.py`

```bash
python3 revert.py               # Revert migration
python3 revert.py --backup      # Backup first
```

### validate.py

Validate PM-OS structure.

**Location:** `common/tools/migration/validate.py`

```bash
python3 validate.py             # Validate current structure
python3 validate.py --fix       # Auto-fix issues
```

---

## Common Import Pattern

All tools should use this pattern for imports:

```python
#!/usr/bin/env python3
import sys
import os

# Add tools directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config_loader import get_root_path, get_jira_config
from path_resolver import get_paths
```

---

## Related Documentation

- [Architecture](../02-architecture.md) - Tool architecture
- [Installation](../03-installation.md) - Configuration setup
- [Brain Tools](brain-tools.md) - Brain-specific tools

---

*Last updated: 2026-01-13*
