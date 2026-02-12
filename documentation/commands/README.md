# PM-OS Commands Reference

> Complete reference for all 76 PM-OS slash commands

## Command Categories

| Category | Commands | Purpose |
|----------|----------|---------|
| [Core](core-commands.md) | 15 | Session management, boot, context, publishing |
| [Documents](document-commands.md) | 11 | PRD, RFC, ADR, BC, etc. |
| [Integrations](integration-commands.md) | 9 | Jira, GitHub, Slack, Confluence |
| [FPF](fpf-commands.md) | 14 | First Principles Framework reasoning |
| [Agents](agent-commands.md) | 11 | Ralph, Confucius, specialized agents |
| [Developer](developer-commands.md) | 21 | Beads, roadmap, dev utilities |

## Quick Reference

### Most Used Commands

| Command | Description |
|---------|-------------|
| `/boot` | Initialize PM-OS session |
| `/update-context` | Sync daily context from integrations |
| `/session-save` | Save current session |
| `/session-load` | Resume a previous session |
| `/prd` | Generate Product Requirements Document |
| `/meeting-prep` | Prepare for upcoming meetings |

### All Commands by Category

#### Core Commands
| Command | Description |
|---------|-------------|
| `/boot` | Initialize PM-OS environment |
| `/logout` | End PM-OS session |
| `/update-context` | Sync daily context |
| `/create-context` | Create context pipeline |
| `/session-save` | Save session state |
| `/session-load` | Load saved session |
| `/session-status` | Show session status |
| `/session-search` | Search sessions |
| `/brain-load` | Load Brain entities |
| `/update-3.0` | Migrate to PM-OS 3.0 |
| `/revert-2.4` | Rollback to PM-OS 2.4 |

#### Document Commands
| Command | Description |
|---------|-------------|
| `/prd` | Product Requirements Document |
| `/rfc` | Request for Comments |
| `/adr` | Architecture Decision Record |
| `/bc` | Business Case |
| `/prfaq` | Amazon-style PR/FAQ |
| `/whitepaper` | Strategic proposal |
| `/pupdate` | Performance update |
| `/4cq` | 4CQ project definition |
| `/meeting-notes` | Meeting notes (Deo format) |
| `/tribe-update` | Quarterly tribe update |

#### Integration Commands
| Command | Description |
|---------|-------------|
| `/jira-sync` | Sync Jira data |
| `/github-sync` | Sync GitHub activity |
| `/confluence-sync` | Sync Confluence pages |
| `/statsig-sync` | Sync Statsig experiments |
| `/slackbot` | Slack bot mention capture |
| `/meeting-prep` | Meeting preparation |
| `/sprint-report` | Generate sprint report |
| `/sync-tech-context` | Sync technical context |
| `/career-planning` | Career planning system |

#### FPF Commands
| Command | Description |
|---------|-------------|
| `/q0-init` | Initialize FPF context |
| `/q1-hypothesize` | Generate hypotheses (abduction) |
| `/q1-add` | Inject user hypothesis |
| `/q2-verify` | Verify logic (deduction) |
| `/q3-validate` | Validate (induction) |
| `/q4-audit` | Audit evidence (trust calculus) |
| `/q5-decide` | Finalize decision |
| `/q-status` | Show FPF status |
| `/q-reset` | Reset FPF cycle |
| `/q-query` | Search knowledge base |
| `/q-decay` | Evidence freshness management |
| `/q-actualize` | Reconcile FPF with repo changes |
| `/quint-review` | Review reasoning state |
| `/quint-prd` | FPF-enhanced PRD |

#### Agent Commands
| Command | Description |
|---------|-------------|
| `/ralph-init` | Initialize Ralph feature |
| `/ralph-loop` | Run Ralph iteration |
| `/ralph-specs` | Generate Ralph specs |
| `/ralph-status` | Show Ralph status |
| `/confucius-status` | Show Confucius status |
| `/orthogonal-status` | Orthogonal challenge status |
| `/quint-sync` | Quint-Brain sync |
| `/gemini-fpf` | Gemini FPF bridge |
| `/synapse` | Synapse builder |
| `/analyze-codebase` | Analyze codebase |
| `/pm` | PM Assistant mode |

#### Developer Commands (requires developer/ folder)
| Command | Description |
|---------|-------------|
| `/bd-create` | Create Beads issue |
| `/bd-list` | List Beads issues |
| `/bd-show` | Show issue details |
| `/bd-update` | Update issue fields |
| `/bd-close` | Close an issue |
| `/bd-ready` | List ready issues |
| `/bd-prime` | Prime context for issue |
| `/bd-create-epic-roadmap` | Create epic from roadmap |
| `/bd-create-story-roadmap` | Create story from roadmap |
| `/bd-create-task-roadmap` | Create task from roadmap |
| `/parse-roadmap-inbox` | Parse roadmap items |
| `/list-roadmap-inbox` | List roadmap inbox |
| `/delete-roadmap-inbox` | Delete roadmap item |
| `/boot-dev` | Boot developer environment |
| `/sync-commands` | Sync developer commands |
| `/preflight` | System verification checks |
| `/push` | Publish to repositories |
| `/brain-enrich` | Brain quality tools |
| `/export-to-spec` | Export PRD to spec-machine |
| `/documentation` | Manage documentation |
| `/sprint-learnings` | Sprint retrospective |

## Command Syntax

```
/command [arguments] [options]
```

### Arguments

Some commands accept positional arguments:

```
/session-load session-id
/meeting-prep "Meeting Title"
/prd "Feature Name"
```

### Options

Commands may support options:

```
/update-context quick      # Quick mode
/update-context --jira     # Include Jira
/jira-sync --project PROJ  # Specific project
```

## Getting Help

- Run `/help` to see available commands
- Read specific command documentation for details
- Check [Troubleshooting](../troubleshooting/common-issues.md) for issues

---

*Last updated: 2026-02-02*
