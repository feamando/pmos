# PM-OS Setup Wizard

Interactive setup wizard to configure PM-OS for a new user. Collects profile information, configures integrations, and initializes the Brain.

## Overview

This command guides you through initial PM-OS configuration:
1. **Profile Setup** - Name, role, team, stakeholders
2. **Integration Config** - Jira, Slack, GitHub settings
3. **API Key Verification** - Test configured connections
4. **Brain Initialization** - Create initial entities and run first context pull

## Instructions

### Step 1: Collect User Profile

Ask the user the following questions to build their persona. Use the AskUserQuestion tool or conversational prompts:

```yaml
# Required Information
name: "What is your full name?"
role: "What is your job title? (e.g., Product Manager, Senior PM, Director of Product)"
company: "What company do you work for?"
team: "What team or squad do you lead/belong to?"

# Optional but Recommended
manager: "Who is your manager? (Name and title)"
direct_reports: "Do you have direct reports? If so, list their names and roles."
key_stakeholders: "Who are your key stakeholders? (Engineering lead, Design lead, etc.)"
```

### Step 2: Create Persona File

After collecting profile information, create a personalized persona file:

1. Read `AI_Guidance/Rules/PERSONA_TEMPLATE.md`
2. Create `AI_Guidance/Rules/[USERNAME].md` (e.g., `JOHN_DOE.md`)
3. Replace all `[PLACEHOLDER]` sections with collected information
4. Guide user to fill in additional sections (tone, vocabulary, etc.)

**Minimum Required Sections to Populate:**
- Section 1: Professional Identity (name, role, team, manager)
- Section 5: Vocabulary (company-specific acronyms)
- Section 8: Team Member Profiles (if has reports)
- Section 10: Key Projects (initial project list)

### Step 3: Configure Integration Settings

Collect integration preferences:

```yaml
# Jira Configuration
jira_server: "What is your Jira server URL? (e.g., https://company.atlassian.net)"
jira_projects: "Which Jira project keys should PM-OS track? (comma-separated, e.g., PROJ, TEAM, SQUAD)"

# Slack Configuration
slack_channels: "Which Slack channels are most important for your work? (comma-separated)"
slack_tier: "How much Slack history should we pull? (tier1=critical, tier2=important, tier3=all)"

# GitHub Configuration
github_repos: "Which GitHub repos should PM-OS monitor? (format: org/repo, comma-separated)"

# Calendar Configuration
calendar_lookahead: "How many hours ahead should meeting prep look? (default: 12)"
```

### Step 4: Create Configuration Files

Based on collected information, create/update configuration files:

#### 4a. Environment Variables (.env)

Guide user to copy `.env.example` to `.env` and fill in:

```bash
# Required for full functionality
JIRA_SERVER=[collected jira_server]
JIRA_PROJECTS=[collected jira_projects]
SLACK_CHANNELS=[collected slack_channels]
GITHUB_REPOS=[collected github_repos]
```

#### 4b. Update AGENT.md

Modify `AGENT.md` to reference the new persona file:

```markdown
## Persona
See `AI_Guidance/Rules/[USERNAME].md` for communication style and preferences.
```

### Step 5: Verify API Connections

Test each configured integration:

```bash
# Test Jira connection
python3 AI_Guidance/Tools/jira_brain_sync.py --test

# Test GitHub connection
python3 AI_Guidance/Tools/github_brain_sync.py --test

# Test Google connection (if configured)
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --dry-run
```

Report which connections succeeded and which need attention.

### Step 6: Initialize Brain

Create initial Brain structure for the user:

#### 6a. Create User Entity

Create `AI_Guidance/Brain/Entities/[UserName].md`:

```markdown
---
type: person
name: [Full Name]
role: [Role]
team: [Team]
created: [YYYY-MM-DD]
---

# [Full Name]

## Profile
- **Role:** [Role] at [Company]
- **Team:** [Team]
- **Manager:** [Manager]
- **Reports:** [Reports list]

## Key Projects
- [Project 1]
- [Project 2]

## Stakeholders
- [Stakeholder 1]: [Role/Context]
- [Stakeholder 2]: [Role/Context]

## Notes
[Space for ongoing notes about this person's context]
```

#### 6b. Create Initial Project Files

For each project mentioned, create stub files in `AI_Guidance/Brain/Projects/`:

```markdown
---
type: project
name: [Project Name]
owner: [User Name]
status: Active
created: [YYYY-MM-DD]
---

# [Project Name]

## Overview
[To be filled during first /create-context run]

## Current Status
- Status: Active
- Phase: [TBD]

## Key Stakeholders
- [TBD]

## Related
- [[Entities/[UserName].md]]
```

### Step 7: Run First Context Pull

Execute the context pipeline to populate the Brain:

```bash
pwsh create-context.ps1 -Mode full -Days 7
```

Or guide user through:
```
/create-context full
```

### Step 8: Confirm Setup Complete

Provide setup summary:

```markdown
## PM-OS Setup Complete!

### Profile Created
- Persona: AI_Guidance/Rules/[USERNAME].md
- Entity: AI_Guidance/Brain/Entities/[UserName].md

### Integrations Configured
- [x] Jira: [Status]
- [x] GitHub: [Status]
- [x] Slack: [Status]
- [x] Google: [Status]

### Brain Initialized
- Projects created: [N]
- Entities created: [N]
- Context files: [N]

### Next Steps
1. Run `/boot` to start your first session
2. Review and enhance your persona file
3. Add team members as Brain entities
4. Run `/create-context` daily to keep context fresh

### Quick Commands
- `/boot` - Start daily session
- `/pm` - Enter PM Assistant mode
- `/meeting-prep` - Prepare for meetings
- `/create-context` - Pull fresh context
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Jira connection fails | Check JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN in .env |
| GitHub auth error | Verify GITHUB_TOKEN has repo read permissions |
| Google OAuth fails | Re-run OAuth flow: `python3 AI_Guidance/Tools/gdrive_mcp/setup.ps1` |
| Slack rate limited | Reduce SLACK_CHANNELS or use tier1 only |

### Re-running Setup

To reconfigure PM-OS:
```
/setup
```

This will preserve existing Brain data but allow reconfiguration of integrations and profile.

## Execute

Begin the interactive setup process. Ask profile questions first, then proceed through each step.
