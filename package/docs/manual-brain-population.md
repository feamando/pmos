# Manual Brain Population Guide

This guide explains how to manually populate your PM-OS brain when automated sync isn't available or you want custom entities.

## Overview

The brain is a knowledge graph stored as Markdown files with YAML frontmatter. You can create and edit entities manually, and PM-OS will recognize them alongside synced entities.

## Creating Entities Manually

### Step 1: Choose Entity Type and Location

```
~/pm-os/brain/Entities/
├── People/       # Team members, stakeholders
├── Projects/     # Projects, initiatives
├── Issues/       # Tickets, tasks, bugs
├── Documents/    # PRDs, specs, docs
├── Meetings/     # Meeting notes
└── ...
```

### Step 2: Create the File

Use the naming convention: `Entity_Name.md`

```bash
touch ~/pm-os/brain/Entities/People/John_Smith.md
```

### Step 3: Add Frontmatter

Every entity needs YAML frontmatter with at least `type` and `name`:

```yaml
---
type: person
name: John Smith
---
```

### Step 4: Add Content

Add Markdown content below the frontmatter:

```markdown
---
type: person
name: John Smith
email: john@example.com
role: Engineering Lead
team: Platform
---

# John Smith

## Profile

- **Email**: john@example.com
- **Role**: Engineering Lead
- **Team**: Platform

## Notes

John leads the platform engineering team. Key contact for infrastructure decisions.

## Related

- [[Authentication Service]] - Technical owner
- [[Platform Roadmap]] - Primary stakeholder
```

## Entity Templates

### Person

```markdown
---
type: person
name: [Full Name]
email: [email@example.com]
role: [Job Title]
team: [Team Name]
source: manual
created: [YYYY-MM-DD]
---

# [Full Name]

## Profile

- **Email**: [email@example.com]
- **Role**: [Job Title]
- **Team**: [Team Name]

## Notes

[Context about this person, their responsibilities, communication preferences]

## Related

- [[Project Name]] - Role on project
```

### Project

```markdown
---
type: project
name: [Project Name]
status: [planning|active|completed|on-hold]
owner: [Owner Name]
source: manual
created: [YYYY-MM-DD]
---

# [Project Name]

## Overview

[Brief description of the project]

## Goals

1. [Goal 1]
2. [Goal 2]

## Key Stakeholders

- [Name] - [Role]
- [Name] - [Role]

## Timeline

- **Start**: [YYYY-MM-DD]
- **Target**: [YYYY-MM-DD]

## Notes

[Additional context, decisions, risks]
```

### Document (PRD, Spec, etc.)

```markdown
---
type: document
name: [Document Title]
author: [Author Name]
status: [draft|review|approved]
source: manual
created: [YYYY-MM-DD]
---

# [Document Title]

## Summary

[Executive summary]

## Problem Statement

[What problem does this solve?]

## Solution

[Proposed solution]

## Success Metrics

1. [Metric 1]
2. [Metric 2]
```

### Meeting

```markdown
---
type: meeting
name: [Meeting Title]
date: [YYYY-MM-DD]
attendees:
  - [Name 1]
  - [Name 2]
source: manual
created: [YYYY-MM-DD]
---

# [Meeting Title]

**Date**: [YYYY-MM-DD]
**Attendees**: [Names]

## Agenda

1. [Topic 1]
2. [Topic 2]

## Notes

[Discussion points, decisions made]

## Action Items

- [ ] [Action item] - @[Owner]
- [ ] [Action item] - @[Owner]
```

## Linking Entities

Use wiki-style links to connect entities:

```markdown
This project is owned by [[John Smith]] and relates to [[Authentication Service]].
```

Or use the relationships frontmatter:

```yaml
relationships:
  owner: [John Smith]
  project: [Authentication Service]
  stakeholders: [Jane Doe, Bob Wilson]
```

## Importing from Other Sources

### From CSV

Create a script to convert CSV to entities:

```python
import csv
from pathlib import Path
from datetime import datetime

def create_entity(name, data, entity_type, output_dir):
    filename = name.replace(' ', '_') + '.md'
    content = f"""---
type: {entity_type}
name: {name}
source: import
created: {datetime.now().strftime('%Y-%m-%d')}
"""
    for key, value in data.items():
        content += f"{key}: {value}\n"
    content += "---\n\n"
    content += f"# {name}\n"

    (output_dir / filename).write_text(content)

# Usage
with open('people.csv') as f:
    reader = csv.DictReader(f)
    output = Path('~/pm-os/brain/Entities/People').expanduser()
    for row in reader:
        create_entity(row['name'], row, 'person', output)
```

### From Notion

Export Notion pages as Markdown and add frontmatter.

### From Google Docs

Export as .docx, convert to Markdown, add frontmatter.

## Best Practices

1. **Consistent Naming**: Use the same name format across entities
2. **Rich Metadata**: Include frontmatter for better searchability
3. **Link Generously**: Connect related entities with `[[links]]`
4. **Regular Updates**: Keep entities current
5. **Source Attribution**: Use `source: manual` for hand-created entities

## Validation

Check your entities are valid:

```bash
# Count entities
pm-os brain status

# Check for issues
find ~/pm-os/brain/Entities -name "*.md" -exec grep -L "^type:" {} \;
```

## Syncing Manual with Automated

Manual entities coexist with synced entities. The sync process:
- Creates new entities from external sources
- Updates existing synced entities
- Never overwrites `source: manual` entities

To prevent a manually created entity from being overwritten:
1. Ensure it has `source: manual` in frontmatter
2. Use a unique filename that won't conflict with sync
