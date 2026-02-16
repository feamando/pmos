# Meeting Tools

> Tools for meeting preparation and series intelligence

## meeting_prep.py

Generate personalized meeting pre-reads for upcoming calendar events.

### Location

`common/tools/meeting/meeting_prep.py`

### Purpose

- Fetch calendar events from Google Calendar
- Classify meetings by type (1:1, standup, interview, etc.)
- Gather context from Brain, GDrive, Jira
- Synthesize pre-reads using LLM
- Maintain series history for recurring meetings

### CLI Usage

```bash
# Generate pre-reads for next 24 hours
python3 meeting_prep.py --hours 24

# Specific meeting only
python3 meeting_prep.py --meeting "1:1 Alice"

# List upcoming without generating
python3 meeting_prep.py --list

# Include Jira context
python3 meeting_prep.py --with-jira

# Upload to GDrive and link to Calendar
python3 meeting_prep.py --upload

# Quick mode for recurring meetings
python3 meeting_prep.py --quick

# Cleanup cancelled meetings
python3 meeting_prep.py --cleanup
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--hours` | int | Lookahead period (default: 24) |
| `--meeting` | str | Generate for specific meeting title |
| `--list` | flag | List meetings without generating |
| `--upload` | flag | Upload to GDrive and link to event |
| `--with-jira` | flag | Include participant Jira issues |
| `--quick` | flag | Minimal prep for recurring meetings |
| `--cleanup` | flag | Archive orphaned/cancelled preps |
| `--dry-run` | flag | Preview without generating |
| `--compare` | flag | Generate comparison report |

### Meeting Types & Templates

| Type | Max Words | Focus |
|------|-----------|-------|
| 1:1 | 300 | Action items first, quick context |
| Standup | 150 | Minimal, team status focus |
| Interview | 1000 | Detailed assessment criteria |
| External | 500 | Company context, talking points |
| Large Meeting | 200 | "Why am I here?" focus |
| Review/Retro | 400 | Your prep, discussion points |
| Planning | 400 | Sprint context, items to discuss |
| Other | 400 | General meeting prep |

### Output Structure

```
user/planning/Meeting_Prep/
├── Series/                    # Recurring meetings
│   ├── Series-alice-jane-1-1.md
│   └── Series-growth-division-standup.md
├── AdHoc/                     # One-time meetings
│   └── Meeting-2026-02-02-kickoff.md
└── Archive/                   # Past/cancelled
    └── Meeting-2026-01-15-cancelled.md
```

### Context Sources

1. **Brain entities** - Participant profiles, roles, topics
2. **Daily context** - Action items, decisions, blockers
3. **GDrive** - Past meeting notes (auto-searched)
4. **Series history** - Previous entries for recurring meetings
5. **Jira** - Recent participant tickets (with `--with-jira`)
6. **Task inference** - Completed tasks from Slack, Jira, GitHub

---

## series_intelligence.py

Maintain intelligent context for recurring meetings.

### Location

`common/tools/meeting/series_intelligence.py`

### Purpose

- Track meeting series over time
- Synthesize patterns and themes
- Carry forward open items
- Detect topic evolution

### Python API

```python
from meeting.series_intelligence import SeriesIntelligence

si = SeriesIntelligence(series_slug="alice-jane-1-1")

# Get series context
context = si.get_context()

# Add new entry
si.add_entry(meeting_date, content)

# Synthesize themes
themes = si.synthesize_themes(last_n=5)
```

### Series File Structure

```markdown
# Series: Alice <> Jane 1:1

## Series Intelligence
- Meeting frequency: Weekly (Thursdays)
- Common themes: OTP launch, Meal Kit metrics
- Open action items: 3

## 2026-02-02 Entry
### Context
- OTP at 20%, expanding to 100% next week
### Action Items
- [ ] Pull early OTP results
```

---

## llm_synthesizer.py

Generate meeting pre-reads using LLM.

### Location

`common/tools/meeting/llm_synthesizer.py`

### Purpose

- Format context for LLM processing
- Apply meeting type templates
- Generate structured pre-reads
- Handle token limits

### Python API

```python
from meeting.llm_synthesizer import MeetingLLMSynthesizer

synthesizer = MeetingLLMSynthesizer(model="gemini")

# Generate pre-read
preread = synthesizer.generate(
    meeting_type="1:1",
    participants=["Alice"],
    context=context_dict
)
```

### Template Variables

| Variable | Description |
|----------|-------------|
| `{{meeting_type}}` | Classification (1:1, standup, etc.) |
| `{{participants}}` | List of attendees |
| `{{context}}` | Gathered context |
| `{{past_notes}}` | Previous meeting notes |
| `{{action_items}}` | Open action items |
| `{{max_words}}` | Word limit for type |

---

## task_inference.py

Automatically detect completed tasks from multiple sources.

### Location

`common/tools/meeting/task_inference.py`

### Purpose

- Scan for task completion signals
- Match against open action items
- Suggest items to mark complete
- Cross-reference multiple sources

### Sources Scanned

| Source | Signal |
|--------|--------|
| Jira | Ticket status changes |
| GitHub | PR merges, commit messages |
| Slack | "Done", "Completed", "Shipped" mentions |
| Brain | Updated entity timestamps |

### Python API

```python
from meeting.task_inference import TaskInferrer

inferrer = TaskInferrer()

# Find completed tasks
completed = inferrer.scan_completions(
    action_items=open_items,
    since="2026-01-25"
)

# Returns matches with confidence
# [{"item": "Review PRD", "confidence": 0.9, "source": "jira", "evidence": "..."}]
```

---

## relevance_comparison.py

Compare old vs new meeting prep quality.

### Location

`common/tools/meeting/relevance_comparison.py`

### Purpose

- A/B test meeting prep systems
- Measure context relevance
- Track pre-read quality metrics
- Generate comparison reports

### CLI Usage

```bash
python3 relevance_comparison.py --meeting "1:1 Alice" --compare
```

---

## Common Dependencies

All meeting tools use:

```python
from config_loader import get_user_path, get_google_config
from brain.brain_loader import load_entity
```

## Best Practices

1. **Run before meetings** - Generate preps 1-2 hours ahead
2. **Use series files** - Don't recreate context for recurring meetings
3. **Review and edit** - AI-generated, human-refined
4. **Mark tasks complete** - Keep action items current
5. **Archive regularly** - Run `--cleanup` weekly

---

## Related Documentation

- [Integration Commands](../commands/integration-commands.md) - `/meeting-prep`
- [Workflows](../04-workflows.md) - Meeting Preparation workflow
- [Brain Tools](brain-tools.md) - Entity loading

---

*Last updated: 2026-02-02*
