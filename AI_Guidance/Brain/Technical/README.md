# Technical Brain

Technical knowledge about HelloFresh codebases, patterns, and conventions. This enables PM-OS to generate more accurate PRDs, ADRs, and technical documentation.

## Purpose

| Knowledge Type | Location | Use Case |
|----------------|----------|----------|
| Tech Stack | `tech-stack.md` | Understand frameworks, libraries in use |
| Conventions | `conventions.md` | Know coding standards and patterns |
| Patterns | `patterns/` | Reference specific implementation patterns |
| Repositories | `repositories/` | Per-repo technical overview |
| Components | `components/` | Available UI components (Zest) |

## Commands

| Command | Description |
|---------|-------------|
| `/analyze-codebase <repo>` | Analyze a repo and create/update Technical Brain entry |
| `/sync-tech-context` | Sync standards from spec-machine |

## Integration with Documents

When generating documents, these files are referenced:

- **PRDs** → Technical constraints from relevant repo
- **ADRs** → Architecture patterns for consistency
- **RFCs** → Technical feasibility assessment

## Data Sources

1. **GitHub Repos** - Direct analysis via `gh api`
2. **spec-machine** - Standards from `hellofresh/spec-machine`
3. **Manual** - Team knowledge additions

## Structure

```
Technical/
├── README.md           # This file
├── tech-stack.md       # Overall tech stack summary
├── conventions.md      # Coding conventions
├── patterns/
│   ├── state-management.md
│   ├── api-patterns.md
│   └── component-patterns.md
├── repositories/
│   ├── web.md
│   ├── mobile.md
│   └── backend.md
└── components/
    └── zest-summary.md
```

## Maintenance

- Run `/sync-tech-context` periodically to update from spec-machine
- Run `/analyze-codebase <repo>` when a new repo becomes relevant
- Manual updates welcome for team-specific knowledge

---

*Last Updated: Auto-synced via tech_context_sync.py*
