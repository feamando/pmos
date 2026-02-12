# PM-OS Architecture

> System architecture, integrations, and data flow

## System Overview

```mermaid
graph TB
    subgraph "External Services"
        JIRA[Jira]
        GH[GitHub]
        SLACK[Slack]
        GDOCS[Google Docs]
        CONF[Confluence]
        GCAL[Google Calendar]
    end

    subgraph "PM-OS"
        subgraph "common/ (LOGIC)"
            TOOLS[Tools]
            CMDS[Commands]
            SCHEMAS[Schemas]
        end

        subgraph "user/ (CONTENT)"
            BRAIN[Brain]
            SESSIONS[Sessions]
            CONTEXT[Context]
            CONFIG[Config]
        end
    end

    subgraph "Interface"
        CC[Claude Code CLI]
    end

    JIRA --> TOOLS
    GH --> TOOLS
    SLACK --> TOOLS
    GDOCS --> TOOLS
    CONF --> TOOLS
    GCAL --> TOOLS

    TOOLS --> BRAIN
    TOOLS --> CONTEXT
    CMDS --> CC

    CC --> SESSIONS
    BRAIN --> CC
    CONTEXT --> CC
```

## Three-Folder Architecture

PM-OS v3.3 uses strict separation between code, data, and development:

### common/ (LOGIC)

Contains all executable code and is version-controlled:

```
common/
├── .claude/
│   └── commands/          # 76 slash commands (*.md)
├── tools/                 # 88+ Python tools
│   ├── brain/            # Brain management & enrichment
│   ├── boot/             # Boot orchestration
│   ├── daily_context/    # Context updater
│   ├── documentation/    # Documentation tools
│   ├── integrations/     # Jira, GitHub, Confluence, etc.
│   ├── slack/            # Slack integration
│   ├── meeting/          # Meeting preparation
│   ├── session/          # Session management
│   ├── reasoning/        # FPF tools
│   ├── push/             # Multi-repo publication
│   ├── preflight/        # System verification
│   ├── workspace/        # Workspace management
│   └── *.py              # Core utilities
├── schemas/              # 7 YAML schemas
├── documentation/        # This documentation
├── AGENT.md             # Agent entry point
└── VERSION              # Current version (3.3.0)
```

### user/ (CONTENT)

Contains all user data and personal configurations:

```
user/
├── brain/
│   ├── entities/        # People, teams, partners
│   ├── projects/        # Active projects
│   ├── experiments/     # A/B tests, flags
│   ├── strategy/        # OKRs, roadmaps
│   ├── reasoning/       # FPF cycles
│   ├── inbox/           # Unprocessed items
│   └── registry.yaml    # Entity registry
├── sessions/            # Saved sessions
├── context/             # Daily context files
├── planning/            # Ralph feature plans
├── config.yaml          # User configuration
└── .env                 # Secrets (API keys)
```

### developer/ (DEV TOOLS) - Optional

Contains development tools for PM-OS itself:

```
developer/
├── .claude/
│   └── commands/          # Developer commands (synced to common)
├── tools/
│   ├── beads/            # Issue tracking wrapper
│   └── roadmap/          # Roadmap inbox management
├── docs/                 # Developer documentation
└── README.md             # Setup instructions
```

Developer commands auto-sync to `common/.claude/commands/` on boot.

## Path Resolution

PM-OS locates its directories using multiple strategies:

```mermaid
graph TD
    A[Start] --> B{PM_OS_ROOT env?}
    B -->|Yes| C[Use env paths]
    B -->|No| D{.pm-os-root marker?}
    D -->|Yes| E[Walk up to marker]
    D -->|No| F{Common patterns?}
    F -->|Yes| G[Use ~/pm-os/]
    F -->|No| H[Error: Cannot resolve]
```

**Resolution strategies** (in order):
1. `PM_OS_ROOT`, `PM_OS_COMMON`, `PM_OS_USER` environment variables
2. `.pm-os-root` marker file in ancestor directories
3. Default `~/pm-os/` with `common/` and `user/` subdirectories

## Integration Architecture

### Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant CC as Claude Code
    participant T as Tools
    participant E as External APIs
    participant B as Brain

    U->>CC: /update-context
    CC->>T: daily_context_updater.py
    T->>E: Fetch GDocs, Slack, Jira
    E-->>T: Raw data
    T->>T: Synthesize context
    T-->>CC: context.md created
    T->>B: Update entities
    CC-->>U: Context ready
```

### Authentication

Each integration uses its own authentication method:

| Service | Auth Method | Config Location |
|---------|-------------|-----------------|
| Jira | API Token | `user/.env` (JIRA_API_TOKEN) |
| GitHub | Personal Token | `user/.env` (GITHUB_HF_PM_OS) |
| Slack | Bot Token | `user/.env` (SLACK_BOT_TOKEN) |
| Google | OAuth 2.0 | `user/.secrets/` |
| Confluence | API Token | `user/.env` (CONFLUENCE_*) |

## Command Architecture

Commands are Markdown files in `common/.claude/commands/`:

```
boot.md           # Initialize session
update-context.md # Sync daily context
prd.md            # Generate PRD
...
```

Each command file contains:
1. **Description** - What the command does
2. **Arguments** - Optional parameters
3. **Instructions** - Step-by-step execution guide

Claude Code parses these and executes the instructions.

## Tool Architecture

Python tools follow a consistent pattern:

```python
#!/usr/bin/env python3
"""
Tool Name

Description of what this tool does.

Usage:
    python3 tool_name.py [options]
"""

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config_loader import get_root_path, get_jira_config

def main():
    # Tool logic
    pass

if __name__ == "__main__":
    main()
```

Key utilities all tools can use:
- `config_loader.py` - Configuration access
- `path_resolver.py` - Path resolution
- `brain_loader.py` - Brain data access

## Brain Architecture

The Brain stores structured knowledge:

```mermaid
graph TB
    subgraph Brain
        REG[registry.yaml] --> ENT[entities/]
        REG --> PROJ[projects/]
        REG --> EXP[experiments/]
        REG --> STRAT[strategy/]
        REG --> REAS[reasoning/]

        ENT --> P[person/*.yaml]
        ENT --> T[team/*.yaml]
        ENT --> PART[partner/*.yaml]

        PROJ --> FEAT[feature/*.md]
        PROJ --> EPIC[epic/*.md]

        EXP --> AB[ab_test/*.yaml]
        EXP --> FLAG[flag/*.yaml]
    end
```

See [Brain Architecture](05-brain.md) for details.

## Session Architecture

Sessions enable conversation persistence:

```mermaid
sequenceDiagram
    participant U as User
    participant CC as Claude Code
    participant SM as Session Manager
    participant FS as File System

    U->>CC: /session-save
    CC->>SM: save_session()
    SM->>SM: Compress conversation
    SM->>FS: Write sessions/{id}.json
    SM-->>CC: Session ID
    CC-->>U: Session saved: {id}

    Note over U,FS: Later...

    U->>CC: /session-load {id}
    CC->>SM: load_session(id)
    SM->>FS: Read sessions/{id}.json
    FS-->>SM: Session data
    SM-->>CC: Context restored
    CC-->>U: Session resumed
```

## FPF Architecture

First Principles Framework for structured reasoning:

```mermaid
graph LR
    Q0[q0-init<br>Context] --> Q1[q1-hypothesize<br>Abduction]
    Q1 --> Q2[q2-verify<br>Deduction]
    Q2 --> Q3[q3-validate<br>Induction]
    Q3 --> Q4[q4-audit<br>Trust]
    Q4 --> Q5[q5-decide<br>Decision]

    Q5 -.->|New evidence| Q1
```

State is persisted in `user/brain/reasoning/`.

## Agent Architecture

PM-OS includes specialized AI agents:

| Agent | Purpose | State Location |
|-------|---------|----------------|
| Confucius | Session notes | `user/sessions/{id}-notes.md` |
| Ralph | Feature development | `user/planning/` |
| Orthogonal | Challenge assumptions | In-session |

## Security Considerations

- **Secrets**: All API keys in `user/.env`, never in `common/`
- **OAuth tokens**: Stored in `user/.secrets/`
- **.gitignore**: Secrets directories excluded from version control
- **Permissions**: Tools validate inputs before external calls

## Performance

- **Lazy loading**: Brain entities loaded on demand
- **Caching**: Config and paths cached after first resolution
- **Background tasks**: Long-running syncs run in background
- **State tracking**: Incremental updates based on `state.json`

---

*Last updated: 2026-02-02*
*Confluence: [PM-OS Architecture](https://your-company.atlassian.net/wiki/spaces/PMOS/pages/architecture)*
