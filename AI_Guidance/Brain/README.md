# The Brain - PM-OS Knowledge Graph

The Brain is PM-OS's semantic knowledge base - a structured collection of markdown files that represent your professional context.

## Directory Structure

```
Brain/
├── Entities/           # People, teams, external partners
├── Projects/           # Active initiatives and features
├── Architecture/       # Technical systems and services
├── Decisions/          # Decision records
├── Reasoning/          # FPF reasoning artifacts
│   ├── Decisions/      # Design Rationale Records (DRRs)
│   ├── Hypotheses/     # Active hypotheses being tested
│   └── Evidence/       # Supporting evidence for decisions
├── Synapses/           # Auto-generated cross-references
├── Inbox/              # Raw ingested data (from integrations)
├── GitHub/             # GitHub activity tracking
└── Strategy/           # Strategic documents and plans
```

## Entity Types

### Entities/ - People and Teams

Who you work with. Includes:
- Direct reports
- Stakeholders
- Key partners
- Teams and squads

**Template:**
```markdown
---
type: person
name: Full Name
role: Job Title
team: Team Name
created: YYYY-MM-DD
related:
  - "[[path/to/related.md]]"
---

# Full Name

## Profile
- **Role:** [Title] at [Company]
- **Team:** [Team]

## Working Style
[How they prefer to communicate, work patterns]

## Interaction Notes
- **YYYY-MM-DD**: [Note from interaction]
```

### Projects/ - Active Initiatives

What you're working on. Includes:
- Product features
- Technical initiatives
- Process improvements
- Strategic programs

**Template:**
```markdown
---
type: project
name: Project Name
owner: Your Name
status: Active | Planning | On Hold | Complete
created: YYYY-MM-DD
jira_project: PROJECT_KEY
---

# Project Name

## Executive Summary
[2-3 sentences on what and why]

## Current Status
- **Phase:** [Phase]
- **Health:** [Green/Yellow/Red]
- **Next Milestone:** [Description] (YYYY-MM-DD)

## Team
- **PM:** [Name]
- **Eng:** [Name]
- **Design:** [Name]

## Decisions
- **YYYY-MM-DD**: [Decision]. Rationale: [Why].
```

### Architecture/ - Technical Systems

Systems and services you need to understand. Includes:
- Internal services
- External integrations
- Infrastructure components
- Data systems

**Template:**
```markdown
---
type: system
name: System Name
status: Active | Deprecated | Planned
owner: Team Name
---

# System Name

## Overview
[What it does]

## Architecture
[Diagram or description]

## Endpoints/Interfaces
[How to interact with it]

## Owner & Contacts
[Who to ask for help]
```

### Reasoning/ - FPF Artifacts

First Principles Framework reasoning materials:

- **Decisions/**: Design Rationale Records documenting major decisions
- **Hypotheses/**: Active hypotheses being tested
- **Evidence/**: Supporting data and research

## How the Brain Gets Populated

### Automatic Population

The `/create-context` command automatically populates the Brain:

1. **Ingestion**: Raw data pulled to `Inbox/`
2. **Analysis**: LLM extracts entities and relationships
3. **Writing**: `unified_brain_writer.py` creates/updates files

### Manual Creation

Create entities manually when:
- Meeting someone new important
- Starting a new project
- Learning about a new system

### Synapse Building

Run periodically to build cross-references:

```
/synapse
```

This creates links between related entities based on:
- Explicit `related:` frontmatter
- Mentioned names in content
- Shared projects/teams

## Best Practices

### 1. Use Frontmatter

Always include YAML frontmatter for machine readability:

```yaml
---
type: project
name: My Project
status: Active
created: 2025-01-05
---
```

### 2. Link Entities

Reference other Brain entities with double-bracket syntax:

```markdown
Working with [[Entities/John_Smith.md]] on this.
```

### 3. Keep Changelogs

Add dated entries when things change:

```markdown
## Changelog
- **2025-01-05**: Updated status to Active
- **2025-01-03**: Initial creation
```

### 4. Capture Decisions

Every significant decision should be recorded:

```markdown
## Decisions
- **2025-01-05**: Chose PostgreSQL over MongoDB. Rationale: Team expertise, ACID compliance needed.
```

### 5. Regular Maintenance

- **Weekly**: Run `/synapse` to update relationships
- **Monthly**: Archive completed projects
- **Quarterly**: Review and clean stale entities

## Querying the Brain

Use `/q-query` to search across the Brain:

```
/q-query "payment processing"
```

Or use `/brain-load` to identify hot topics:

```
/brain-load
```

## Integration with FPF

The Brain integrates with First Principles Framework:

1. **q0-init**: Creates reasoning cycle, references Brain entities
2. **q3-validate**: Pulls evidence from Brain
3. **q5-decide**: Creates DRR in `Reasoning/Decisions/`

## Troubleshooting

### "Entity not found"

Create a new entity file in the appropriate directory.

### "Stale relationships"

Run `/synapse` to rebuild cross-references.

### "Brain too large"

Archive old projects to `Brain/Archive/` (create if needed).

### "Missing context"

Run `/create-context full` to repopulate from sources.
