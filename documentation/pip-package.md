# PM-OS Pip Package

> The `pm-os` CLI: installation, extras, and package structure

## Overview

PM-OS is distributed as a Python pip package. The `pm-os` (or `pmos`) command provides the CLI for installation, configuration, brain management, and daily operations.

```bash
pip install pm-os
```

**Python requirement:** 3.10+

---

## Installation

```bash
pip install pm-os
```

This installs the full package with all integration dependencies:

| Category | Packages | Used For |
|----------|----------|----------|
| Core | `pyyaml`, `python-dotenv`, `requests`, `click`, `rich` | Config, CLI, HTTP |
| Google | `google-api-python-client`, `google-auth`, `google-auth-oauthlib` | Calendar, Drive, Gmail sync |
| Slack | `slack-sdk` | Mention capture, channel monitoring |
| Jira | `jira` | Issue sync, sprint data |
| GitHub | `PyGithub` | PR and issue tracking |
| Confluence | `atlassian-python-api` | Documentation sync |
| AI | `anthropic`, `google-generativeai` | LLM API access |
| Bedrock | `boto3` | AWS Bedrock LLM access |

### Development Extras

For testing and linting tools:

```bash
pip install "pm-os[dev]"
```

Adds: `pytest`, `pytest-cov`, `black`, `ruff`

---

## CLI Entry Points

The package registers two CLI commands:

| Command | Entry Point |
|---------|------------|
| `pm-os` | `pm_os.cli:main` |
| `pmos` | `pm_os.cli:main` (alias) |

Both point to the same function. Use whichever you prefer.

---

## Package Structure

```
src/pm_os/
├── __init__.py              # Package initialization, version
├── cli.py                   # CLI entry point (click commands)
├── google_auth.py           # Google OAuth helper (scopes, flow, tokens)
├── data/
│   ├── __init__.py
│   └── google_client_secret.json  # Bundled OAuth creds (HF only)
├── templates/               # Config file templates
├── wizard/
│   ├── __init__.py
│   ├── orchestrator.py      # Wizard state machine
│   ├── ui.py                # Terminal UI components
│   ├── steps/
│   │   ├── __init__.py      # WIZARD_STEPS definition (10 steps)
│   │   ├── welcome.py
│   │   ├── prerequisites.py
│   │   ├── profile.py
│   │   ├── llm_provider.py
│   │   ├── integrations.py  # Jira, Slack, Google, GitHub, Confluence
│   │   ├── common_download.py
│   │   ├── directories.py   # Creates dir structure, config, .env
│   │   ├── claude_code_setup.py
│   │   ├── brain_population.py
│   │   └── verification.py
│   └── brain_sync/
│       ├── __init__.py
│       ├── google_sync.py   # GoogleSyncer (6 scopes)
│       ├── jira_sync.py
│       ├── github_sync.py
│       └── slack_sync.py
└── utils/
    └── ...
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | Click-based CLI with `init`, `doctor`, `brain`, `config`, `help` commands. Also contains `run_silent_install()` for template-based installs. |
| `google_auth.py` | Centralized Google OAuth logic. Defines `GOOGLE_SCOPES` (6 scopes), handles bundled credential detection, OAuth browser flow, and token refresh. |
| `wizard/orchestrator.py` | State machine that runs the 10-step wizard. Manages step progression, data persistence, and resume capability. |
| `wizard/steps/integrations.py` | Handles all 5 integration configurations. Google has two paths: bundled (auto OAuth) and manual (Cloud Console instructions). |
| `wizard/steps/directories.py` | Creates the PM-OS directory tree, generates `.env`, `config.yaml`, `USER.md`, `.gitignore`, brain files, and marker files. |
| `wizard/brain_sync/google_sync.py` | `GoogleSyncer` class that syncs Calendar events and Drive files to brain entities using the full 6-scope set. |

---

## Bundled Data Files

The package includes data files in `src/pm_os/data/`:

| File | Included In | Purpose |
|------|------------|---------|
| `google_client_secret.json` | `pmos` (private) only | Google OAuth client secret for Acme Corp users |

The `pyproject.toml` sdist include rules ensure these files are packaged:

```toml
[tool.hatch.build.targets.sdist]
include = [
    "src/pm_os/**/*.py",
    "src/pm_os/**/*.yaml",
    "src/pm_os/**/*.json",
    "src/pm_os/**/*.md",
    "src/pm_os/templates/*",
    "src/pm_os/data/*",
    "VERSION",
    "README.md",
    "LICENSE",
]
```

When `google_client_secret.json` is absent (public release), the `has_bundled_credentials()` function returns `False` and all code paths fall back to manual configuration.

---

## Version

The package version is stored in the `VERSION` file at the package root:

```
3.4.0
```

This is read by `hatchling` during build via:

```toml
[tool.hatch.version]
path = "VERSION"
pattern = "(?P<version>.+)"
```

---

## Development

### Editable Install

For local development:

```bash
cd common/package
pip install -e ".[all,dev]"
```

### Running Tests

```bash
cd common/package
pytest
```

The test suite includes:
- `tests/test_cli.py` — CLI commands, silent install, step definitions
- `tests/test_google_auth.py` — Google OAuth module (23 tests)
- Additional integration and wizard tests

### Code Quality

```bash
# Format
black src/ tests/

# Lint
ruff check src/ tests/
```

---

## Build and Distribution

### Build the Package

```bash
pip install hatchling
python -m build
```

Produces:
- `dist/pm_os-3.4.0.tar.gz` (sdist)
- `dist/pm_os-3.4.0-py3-none-any.whl` (wheel)

### Private Distribution (Acme Corp)

The `pmos` private repository includes `google_client_secret.json` in the package. This file is excluded from the public `feamando/pmos` repository via `.gitignore`.

---

*Last updated: 2026-02-11*
*PM-OS Version: 3.4.0*
