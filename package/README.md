# PM-OS

**AI-powered Product Management Operating System**

PM-OS is a comprehensive workflow system for Product Managers, integrating with Jira, Slack, GitHub, Google Workspace, and LLM providers to streamline daily work.

## Installation

```bash
# Basic installation
pip install pm-os

# With specific integrations
pip install pm-os[slack]       # Slack integration
pip install pm-os[jira]        # Jira integration
pip install pm-os[google]      # Google Workspace
pip install pm-os[github]      # GitHub integration
pip install pm-os[bedrock]     # AWS Bedrock LLM

# All integrations
pip install pm-os[all]
```

## Quick Start

```bash
# Initialize PM-OS (guided wizard)
pm-os init

# Check installation health
pm-os doctor

# Update to latest version
pm-os update
```

## Features

- **Guided Installation**: Interactive wizard configures everything
- **Daily Context Sync**: Aggregates Jira, Slack, Calendar, GitHub
- **Brain Knowledge Graph**: Entities, relationships, semantic search
- **Session Management**: Context preservation across sessions
- **Integration Hub**: Connects all your PM tools

## Documentation

See the [full documentation](https://pm-os.dev/docs) for detailed guides.

## License

MIT License - see [LICENSE](LICENSE) for details.
