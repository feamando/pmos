# PM-OS Installation Guide

This guide walks you through installing and configuring PM-OS, the AI-powered Product Management Operating System.

## Prerequisites

Before installing PM-OS, ensure you have:

### Required
- **Python 3.10+** - PM-OS requires Python 3.10 or later
- **pip** - Python package manager
- **Git** - For version control and some integrations

### Recommended
- **Claude Code CLI** - For AI-powered assistance ([install from claude.ai/code](https://claude.ai/code))
- **AWS CLI** - If using AWS Bedrock as your LLM provider

### Optional (for integrations)
- **GitHub CLI (gh)** - For GitHub integration
- **Jira access** - API token for Jira integration
- **Slack app** - Bot token for Slack integration

## Installation

### Quick Install

```bash
pip install pm-os
```

### Development Install

For development or to get the latest features:

```bash
git clone https://github.com/feamando/pmos.git
cd pmos/common/package
pip install -e .
```

## Initial Setup

After installation, run the setup wizard:

```bash
pm-os init
```

The wizard will guide you through:

1. **Prerequisites Check** - Verifies system requirements
2. **User Profile** - Collects your name, email, and role
3. **LLM Provider** - Configures AI backend (Bedrock, Anthropic, OpenAI, or Ollama)
4. **Integrations** - Optional setup for Jira, Slack, GitHub, Google, Confluence
5. **Directory Setup** - Creates the PM-OS folder structure
6. **Brain Population** - Initial sync from configured integrations

### Installation Options

```bash
# Resume an interrupted installation
pm-os init --resume

# Install to a custom path (default: ~/pm-os)
pm-os init --path /path/to/pm-os

# Use a configuration template for silent install
pm-os init --template config-template.yaml
```

## Verify Installation

After setup, verify your installation:

```bash
pm-os doctor
```

This checks:
- System requirements (Python, pip, Git)
- PM-OS directory structure
- Configuration files
- Brain initialization

## Directory Structure

After installation, your PM-OS directory will contain:

```
~/pm-os/
├── .env                    # Environment variables
├── .config/
│   └── config.yaml         # Main configuration
├── USER.md                 # Your persona file
├── brain/
│   ├── Entities/           # Knowledge graph
│   │   ├── People/
│   │   ├── Projects/
│   │   ├── Decisions/
│   │   └── ...
│   ├── Glossary/
│   ├── Index/
│   └── Templates/
├── sessions/               # Session files
├── personal/               # Personal notes, calendar, emails
├── team/                   # Team information
├── products/               # Product documentation
└── planning/               # Sprints, roadmaps, reports
```

## Post-Installation

### Load Environment

Add to your shell profile (~/.bashrc, ~/.zshrc):

```bash
export PM_OS_USER="$HOME/pm-os"
source "$PM_OS_USER/.env"
```

### Start Using PM-OS

1. **Sync your brain** (if integrations configured):
   ```bash
   pm-os brain sync
   ```

2. **Start Claude Code** with PM-OS context:
   ```bash
   cd ~/pm-os
   claude
   ```

3. **Boot a session**:
   ```
   /boot
   ```

## CLI Commands

| Command | Description |
|---------|-------------|
| `pm-os init` | Run setup wizard |
| `pm-os init --resume` | Resume interrupted installation |
| `pm-os init --template FILE` | Silent install from template |
| `pm-os doctor` | Check installation health |
| `pm-os doctor --fix` | Attempt to fix common issues |
| `pm-os status` | Show PM-OS status dashboard |
| `pm-os update` | Update to latest version |
| `pm-os brain sync` | Sync from integrations |
| `pm-os brain sync -i NAME` | Sync specific integration |
| `pm-os brain status` | Show entity counts |
| `pm-os config show` | Display configuration |
| `pm-os config edit` | Edit configuration |
| `pm-os config set KEY VALUE` | Set a configuration value |
| `pm-os config validate` | Validate configuration file |
| `pm-os uninstall` | Remove PM-OS installation |

### Command Options

Most commands support these flags:
- `--verbose`, `-v` - Show detailed output
- `--json` - Output as JSON (where applicable)
- `--help` - Show command help

## Debug Mode

Enable debug mode for verbose logging:

```bash
export PM_OS_DEBUG=1
pm-os init
```

This shows detailed API calls, step-by-step execution, and full error messages.

## Documentation

Additional documentation:
- [Configuration Schema](config-schema.md) - Full config.yaml reference
- [Entity Schema](entity-schema.md) - Brain entity format
- [Troubleshooting Guide](troubleshooting.md) - Common issues and fixes
- [Manual Brain Population](manual-brain-population.md) - Creating entities manually

## Troubleshooting

### Common Issues

**"pm-os: command not found"**
- Ensure pip installed to a PATH directory
- Try: `python -m pm_os.cli --help`

**Prerequisites check fails**
- Install missing dependencies
- For Claude Code: visit claude.ai/code
- For AWS CLI: `pip install awscli`

**LLM provider connection fails**
- Verify credentials in .env
- For Bedrock: ensure AWS credentials configured
- For Anthropic/OpenAI: check API key is valid

**Brain sync errors**
- Check integration credentials
- Verify API access/permissions
- Try syncing one integration at a time: `pm-os brain sync -i jira`

### Getting Help

- Run `pm-os --help` for command reference
- Check installation: `pm-os doctor --verbose`
- Report issues: https://github.com/feamando/pmos/issues

## Updating PM-OS

Check for updates:
```bash
pm-os update --check
```

Install updates:
```bash
pm-os update
```

## Uninstalling

To remove PM-OS:

```bash
# Uninstall (removes config, keeps brain)
pm-os uninstall

# Uninstall everything including brain
pm-os uninstall --yes

# Keep brain but remove everything else
pm-os uninstall --keep-brain

# Uninstall the Python package
pip uninstall pm-os
```

To completely reset and reinstall:

```bash
pm-os uninstall --yes
pm-os init
```
