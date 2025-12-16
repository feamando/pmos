# Plan: Entity Registry + Hot Topics Loader

> **Status:** Implemented (Core)
> **Created:** 2025-12-08
> **Owner:** Nikita Gorshkov / AI Agent

## Problem Statement

The Brain architecture separates Episodic memory (Core_Context) from Semantic memory (Brain/), but there's no feedback loop between them:

- Daily context mentions projects/people but Brain files stay stale
- Agents read "OTP launch W50" but don't know `Brain/Projects/OTP.md` exists
- No way to map colloquial names ("Sameer") to Brain files
- Boot process ignores the rich semantic knowledge in Brain/

## Solution: Entity Registry + Hot Topics Loader

### Component 1: Entity Registry (`registry.yaml`)

A central index mapping entities to their Brain files with aliases for flexible lookup.

```yaml
projects:
  otp:
    file: Projects/OTP.md
    aliases: ["OTP", "One-Time-Purchase", "one-time purchase", "one time purchase"]

  influencer_marketplace:
    file: Projects/Influencer_Marketplace.md
    aliases: ["Influencer Marketplace", "creator marketplace", "influencer platform"]

entities:
  sameer_doda:
    file: Entities/Sameer_Doda.md
    aliases: ["Sameer", "Sameer Doda"]
    type: person
```

**Benefits:**
- Single source of truth for entity locations
- Alias support enables fuzzy matching
- Machine-readable for tooling

### Component 2: Hot Topics Loader (Boot Enhancement)

During boot, after synthesizing daily context:

1. **Extract entities** mentioned in today's context
2. **Cross-reference** with registry.yaml
3. **Auto-load** matching Brain files for deeper context
4. **Report** which semantic files were loaded

**Implementation:** Python script `brain_loader.py` that:
- Reads latest context file
- Searches for registry aliases
- Returns list of relevant Brain files to load

### Component 3: Changelog Append (Future)

When synthesizing daily context, append dated entries to Brain files:

```markdown
## Changelog
- **2025-12-08:** W50 launch confirmed on track (from daily context)
- **2025-12-05:** Blocker identified - voucher limitations
```

## Implementation Checklist

- [x] Store this plan document
- [x] Create `Brain/registry.yaml` with existing projects + key people
- [x] Create missing directories: Entities/, Architecture/, Decisions/
- [x] Create `brain_loader.py` lookup script
- [x] Update `boot.md` to include Hot Topics loading step
- [x] Add `--validate` flag to brain_loader.py
- [x] Create stub Brain files for high-frequency entities
- [x] Implement changelog append during synthesis
- [x] Archive Inbox folder
- [x] Add cross-linking between Brain files

## Success Metrics

1. **Agent awareness:** Agents can answer "What are OTP's blockers?" without manual lookup
2. **Reduced staleness:** Brain files updated within 24h of relevant context
3. **Retrieval accuracy:** Partial mentions resolve to correct files 90%+ of time

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        BOOT PROCESS                         │
├─────────────────────────────────────────────────────────────┤
│  1. Load Core Rules (AGENT.md, NGO.md, AI_AGENTS_GUIDE.md) │
│  2. Run daily_context_updater.py → Fetch docs/emails        │
│  3. Synthesize → Create YYYY-MM-DD-NN-context.md            │
│  4. Upload context to GDrive                                │
│  5. [NEW] Run brain_loader.py → Identify hot topics         │
│  6. [NEW] Load relevant Brain files (Projects/, Entities/)  │
│  7. Confirm Ready State                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     BRAIN (Semantic Memory)                 │
├──────────────┬──────────────┬───────────────┬───────────────┤
│  Projects/   │  Entities/   │ Architecture/ │  Decisions/   │
│  - OTP.md    │  - People    │  - Systems    │  - ADRs       │
│  - Infl.Mkt  │  - Teams     │  - Data flows │               │
├──────────────┴──────────────┴───────────────┴───────────────┤
│                      registry.yaml                          │
│         (Central index with aliases for lookup)             │
└─────────────────────────────────────────────────────────────┘
```

---
*This plan implements the "Gardener" cycle described in Brain/README.md*
