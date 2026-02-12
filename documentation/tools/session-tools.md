# Session Tools

> Tools for session management and agent support

## session_manager.py

Manage PM-OS sessions.

### Location

`common/tools/session/session_manager.py`

### Purpose

- Create and track sessions
- Save session state
- Load previous sessions
- Search session history

### CLI Usage

```bash
# Check status
python3 session_manager.py --status

# Create new session
python3 session_manager.py --create "Session Title" --objectives "obj1,obj2" --tags "tag1"

# Save current session
python3 session_manager.py --save --files-created "file1.md" --files-modified "file2.md"

# Load session
python3 session_manager.py --load SESSION_ID

# List recent sessions
python3 session_manager.py --list 5

# Search sessions
python3 session_manager.py --search "payment"

# Add work log entry
python3 session_manager.py --log "Completed phase 1"

# Record decision
python3 session_manager.py --decision "Use microservices|Better scalability|Monolith"

# Add open question
python3 session_manager.py --question "Should we use Redis?"

# Archive session
python3 session_manager.py --archive SESSION_ID
```

### Python API

```python
from session.session_manager import SessionManager

sm = SessionManager()

# Check current session
status = sm.get_status()

# Create session
session_id = sm.create_session(
    title="Feature Development",
    objectives=["Complete auth", "Write tests"],
    tags=["auth", "backend"]
)

# Save session state
sm.save_session(
    files_created=["auth.py"],
    files_modified=["config.yaml"]
)

# Load session
session = sm.load_session(session_id)

# Add entries
sm.add_log_entry("Completed auth implementation")
sm.add_decision("JWT tokens", "Industry standard", ["Session cookies"])
sm.add_question("How to handle refresh tokens?")

# Search
results = sm.search("payment")

# List recent
recent = sm.list_sessions(limit=5)
```

### Session File Structure

Sessions are stored in `user/sessions/`:

```yaml
---
session_id: 2026-01-13-001
title: Feature Development
started: 2026-01-13T09:00:00Z
last_updated: 2026-01-13T14:30:00Z
status: active
tags: [auth, backend]
files_created: [auth.py, tests/test_auth.py]
files_modified: [config.yaml]
decisions:
  - decision: Use JWT tokens
    rationale: Industry standard
    alternatives: [Session cookies]
---

# Session: Feature Development

## Objectives
- [x] Complete auth
- [ ] Write tests

## Work Log
### 09:15
- Started auth implementation
- Created auth.py module

### 11:30
- Completed JWT integration
- Added token refresh logic

## Decisions Made
| Decision | Rationale | Alternatives |
|----------|-----------|--------------|
| Use JWT | Industry standard | Session cookies |

## Open Questions
- [ ] How to handle refresh tokens?

## Context for Next Session
- Auth module complete
- Need to add tests
- Consider rate limiting
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `--status` | Show current session |
| `--create` | Create new session |
| `--save` | Save current session |
| `--load` | Load session by ID |
| `--list N` | List N recent sessions |
| `--search` | Search sessions |
| `--log` | Add work log entry |
| `--decision` | Record decision |
| `--question` | Add open question |
| `--archive` | Archive session |

---

## confucius_agent.py

Confucius agent for session notes.

### Location

`common/tools/session/confucius_agent.py`

### Purpose

- Silently capture session knowledge
- Extract key decisions
- Identify Brain-worthy items
- Generate session summaries

### CLI Usage

```bash
# Check Confucius status
python3 confucius_agent.py --status

# Process session for notes
python3 confucius_agent.py --process SESSION_ID

# Sync to Brain
python3 confucius_agent.py --sync-brain

# Generate summary
python3 confucius_agent.py --summary SESSION_ID
```

### Python API

```python
from session.confucius_agent import ConfuciusAgent

agent = ConfuciusAgent()

# Get status
status = agent.get_status()

# Process session
notes = agent.process_session(session_id)

# Extract decisions
decisions = agent.extract_decisions(session_id)

# Identify Brain items
brain_items = agent.identify_brain_items(session_id)

# Sync to Brain
agent.sync_to_brain()

# Generate summary
summary = agent.generate_summary(session_id)
```

### How Confucius Works

1. **Observes** session conversation
2. **Identifies** key patterns:
   - Decisions made
   - Action items assigned
   - New entities mentioned
   - Knowledge worth preserving
3. **Extracts** structured information
4. **Syncs** to Brain on request

### Notes Structure

Confucius notes are stored alongside sessions:

```
user/sessions/
├── 2026-01-13-001.md           # Session file
└── 2026-01-13-001-notes.md     # Confucius notes
```

```markdown
# Confucius Notes: 2026-01-13-001

## Key Decisions
- Decided to use JWT tokens for authentication
- Chose PostgreSQL over MongoDB for user data

## Action Items
- [ ] @alice_smith: Complete auth tests by Friday
- [ ] @bob_jones: Review security implications

## Brain Candidates
- **New Entity**: Payment Provider X (partner)
- **Update**: alice_smith.last_interaction = 2026-01-13
- **New Project**: auth_refactor

## Knowledge Captured
- JWT refresh token best practice: 7 day expiry
- Rate limiting strategy: 100 req/min per user
```

---

## ralph_manager.py

Manage Ralph feature development.

### Location

`common/tools/ralph/ralph_manager.py`

### Purpose

- Initialize Ralph features
- Run development iterations
- Track progress
- Validate against acceptance criteria

### CLI Usage

```bash
# Initialize feature
python3 ralph_manager.py --init "User Auth" --from-prd ./prd.md

# Run iteration
python3 ralph_manager.py --loop --feature "User Auth"

# Show status
python3 ralph_manager.py --status

# Show all features
python3 ralph_manager.py --list

# Generate specs
python3 ralph_manager.py --specs "User Auth"
```

### Python API

```python
from ralph.ralph_manager import RalphManager

ralph = RalphManager()

# Initialize feature
ralph.init_feature(
    name="User Auth",
    from_prd="./prd.md"
)

# Run iteration
result = ralph.run_iteration(feature="User Auth")

# Get status
status = ralph.get_status()

# List features
features = ralph.list_features()

# Check acceptance
passed = ralph.check_acceptance("User Auth")
```

### Feature Structure

Ralph features live in `user/planning/`:

```
user/planning/user-auth/
├── PROMPT.md       # Requirements
├── PLAN.md         # Implementation plan
├── ACCEPTANCE.md   # Acceptance criteria
└── iterations/
    ├── 001.md      # First iteration
    ├── 002.md      # Second iteration
    └── ...
```

---

## Configuration

Session tools are configured in `user/config.yaml`:

```yaml
pm_os:
  confucius_enabled: true
  auto_save_sessions: true

agents:
  ralph:
    max_iterations: 20
    auto_validate: true
  confucius:
    capture_decisions: true
    auto_brain_sync: true
```

---

## Related Documentation

- [Core Commands](../commands/core-commands.md) - Session commands
- [Agent Commands](../commands/agent-commands.md) - Agent commands
- [Workflows](../04-workflows.md) - Session workflows

---

*Last updated: 2026-01-13*
