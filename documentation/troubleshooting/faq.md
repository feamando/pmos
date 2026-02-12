# Frequently Asked Questions

> Common questions about PM-OS

## General

### What is PM-OS?

PM-OS (Product Management Operating System) is an AI-powered productivity system for Product Managers. It integrates with your existing tools (Jira, Slack, Google, GitHub) and provides intelligent assistance through Claude Code.

### How is PM-OS different from other AI tools?

PM-OS provides:
- **Persistent context** - Maintains knowledge across sessions
- **Integration** - Connects to your actual work tools
- **Structured output** - Generates real PM documents
- **Reasoning framework** - Auditable decision support

### Is my data secure?

Yes:
- All data stays in your `user/` directory
- Secrets are stored in `.env` (not committed)
- OAuth tokens are in `.secrets/`
- PM-OS never sends data to third parties beyond the integrations you configure

---

## Setup

### What's the fastest way to get started?

Use the CLI quick-start:

```bash
pip install pm-os
pm-os init --quick    # ~5 minutes
pm-os doctor          # Verify installation
```

This auto-detects your profile from git and skips optional steps. Add integrations later with `pm-os setup integrations`.

### What are the minimum requirements?

- Python 3.10 or higher
- Claude Code CLI
- Git
- ~500MB disk space

### Do I need all integrations configured?

No. PM-OS works with any combination of integrations. You can start with none and add them later:

```bash
pm-os setup integrations jira
pm-os setup integrations slack
pm-os brain sync
```

### Can I use PM-OS without Jira/Slack?

Yes. Each integration is optional. Context can be manually created or pulled from only the services you use.

### How do I update PM-OS?

```bash
cd ~/pm-os/common
git pull origin main
```

Your `user/` data is never affected by updates.

---

## Daily Usage

### What commands should I run every day?

1. `/boot` - Initialize session
2. `/update-context` - Sync latest info
3. (Work with AI assistance)
4. `/session-save` - Save before ending

### How often should I run /update-context?

At least once in the morning. Run again if:
- You've had important meetings
- Significant Slack discussions occurred
- Jira status changed substantially

### Can I use PM-OS in multiple projects?

Yes. The Brain can track entities across projects. Use tags and project entities to organize.

### What happens if I forget to /session-save?

The session continues where it left off when you next use Claude Code. However, you lose the structured session tracking. `/boot` will detect the interrupted session.

---

## Brain

### What should I put in the Brain?

- **People** - Colleagues, stakeholders, contacts
- **Teams** - Your squad and related teams
- **Projects** - Active features and initiatives
- **Experiments** - A/B tests and feature flags
- **Decisions** - Key decisions with rationale

### How do I add new Brain entities?

1. Use Brain tools:
   ```bash
   python3 unified_brain_writer.py --type person --data '...'
   ```

2. Or create YAML files directly in `user/brain/entities/`

3. Or let Confucius capture during sessions

### How big can my Brain get?

There's no hard limit. The Brain loader indexes entities and loads only what's relevant. Large Brains (1000+ entities) work fine.

### Should I update the Brain manually?

Use automation where possible:
- `/jira-sync` updates squad/project status
- Confucius captures session knowledge
- Integration tools update entities

Manual updates are good for:
- New relationships
- Personal notes
- Context not in other tools

---

## FPF Reasoning

### When should I use FPF?

Use FPF for:
- Important architectural decisions
- Strategy choices
- Reversible but significant decisions
- Decisions needing audit trail

Skip FPF for:
- Quick operational decisions
- Clear-cut choices
- Time-sensitive responses

### What's the difference between FPF and just asking Claude?

FPF provides:
- Structured hypothesis generation
- Evidence tracking with provenance
- Bias detection
- Decision audit trail (DRR)
- Ability to revisit reasoning later

### Can I use FPF with PRDs?

Yes! Use:
```
/prd --fpf "Topic"
```

This runs FPF before generating the PRD.

---

## Sessions

### What's saved in a session?

- Session ID and title
- Start and update timestamps
- Files created/modified
- Decisions made
- Work log entries
- Open questions

### How long are sessions kept?

Indefinitely. Old sessions are archived but not deleted. You can search and load any past session.

### Can I share sessions with others?

Sessions are personal but you can:
- Export session files
- Share the generated documents
- Reference session IDs in handoffs

---

## Documents

### What document types can PM-OS generate?

- PRD (Product Requirements Document)
- RFC (Request for Comments)
- ADR (Architecture Decision Record)
- BC (Business Case)
- PRFAQ (Amazon-style PR/FAQ)
- Whitepaper
- Meeting Notes
- Sprint Reports

### Where are generated documents saved?

In `user/planning/Documents/<type>/` by default. PRDs go to `user/products/`.

### Can I customize document templates?

Yes. Templates are in `common/tools/documents/`. You can modify or add templates there.

---

## Integrations

### Which Jira fields are synced?

- Summary and description
- Status and priority
- Assignee
- Sprint info
- Epic links
- Blockers
- Comments (recent)

### Can I sync private Slack channels?

Yes, if your Slack app has access. Add the channel ID to config and ensure the bot is a member.

### Does PM-OS sync Google Calendar?

Yes, for meeting prep. It reads:
- Upcoming events
- Attendees
- Meeting descriptions

### Can I use PM-OS with GitHub Enterprise?

Yes. Set `GITHUB_API_URL` in `.env` if not using github.com.

---

## Troubleshooting

### How do I diagnose issues quickly?

Use the CLI doctor command:

```bash
pm-os doctor          # Check installation health
pm-os doctor --fix    # Auto-fix common issues
pm-os help troubleshoot  # View troubleshooting guide
```

### PM-OS commands not working

1. Run `pm-os doctor` to check installation
2. Run `/boot` first to initialize environment
3. Check if environment variables are set: `echo $PM_OS_ROOT`
4. See [Common Issues](common-issues.md)

### Integration not syncing

1. Check configuration: `pm-os config show`
2. Reconfigure: `pm-os setup integrations jira`
3. Verify credentials in `user/.env`
4. Test individually: `python3 jira_brain_sync.py`

### Context seems stale

1. Run `/update-context` for fresh sync
2. Check `state.json` isn't stuck
3. Try `--force` flag to bypass state

---

## Advanced

### Can I extend PM-OS with custom commands?

Yes. Add Markdown files to `common/.claude/commands/`. Follow existing patterns for structure.

### Can I add custom integrations?

Yes. Create tools in `common/tools/integrations/` following the sync pattern. Use the Brain writer for output.

### Is there an API?

PM-OS is designed for CLI use via Claude Code. Tools can be called programmatically via Python imports.

### Can PM-OS work with other AI models?

The Gemini bridge (`/gemini-fpf`) enables some cross-model functionality. The orthogonal challenge uses both Claude and Gemini.

---

## Support

### Where do I get help?

1. **CLI help system**:
   ```bash
   pm-os help                 # List all help topics
   pm-os help brain           # Brain knowledge graph
   pm-os help integrations    # Integration setup
   pm-os help troubleshoot    # Troubleshooting guide
   ```

2. **This documentation** - Browse the docs folder
3. **Slack**: `#pm-os-support` channel
4. **GitHub**: File issues at the repository

### How do I report bugs?

1. Run `pm-os doctor` and include output
2. Check [Common Issues](common-issues.md) first
3. File issue with:
   - PM-OS version
   - Output from `pm-os doctor`
   - Steps to reproduce
   - Error message
   - Expected vs actual behavior

### How do I request features?

Post in `#pm-os-support` or file a GitHub issue with the "enhancement" label.

---

*Last updated: 2026-02-09*
