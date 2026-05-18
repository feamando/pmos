---
description: Performance review evidence gathering and writing
---

# Review

Generate structured performance reviews by gathering evidence from multiple sources and producing a review draft calibrated to tone.

## Arguments
$ARGUMENTS

## Instructions

**Syntax:**
```
/review --<type> --<timeframe> --<tone> "Name, email"
```

**Parameters:**

| Parameter | Values | Required |
|-----------|--------|----------|
| Type | `--peer`, `--manager`, `--report`, `--self` | Yes (exactly one) |
| Timeframe | `--6m`, `--12m` | Yes (defaults to config `review.default_timeframe` or 6m) |
| Tone | `--1` through `--5` | Yes (defaults to config `review.default_tone` or 3) |
| Person | `"Name, email"` | Yes (except `--self`) |

**Tone/Direction Guide:**

| Tone | Label | Effect |
|------|-------|--------|
| 1 | Critical: Immediate Action | Lead with gaps, risks. Achievements brief. |
| 2 | Below Expectations | Focus on improvement areas. Acknowledge positives. |
| 3 | Meets Expectations | Balanced strengths and growth areas. |
| 4 | Exceeds Expectations | Lead with achievements. Growth as opportunities. |
| 5 | Outstanding | Emphasize outsized impact. Gaps as stretch goals. |

If no arguments provided, display usage:
```
Review - Performance review evidence gathering and writing

  /review --peer --6m --4 "Name, email"      - Peer review
  /review --report --12m --3 "Name, email"    - Direct report review
  /review --manager --6m --4 "Name, email"    - Upward review
  /review --self --6m --3                     - Self-review

Usage: /review --<type> --<timeframe> --<tone> "Name, email"
```

**Examples:**
```
/review --peer --6m --4 "Alex Partner, alex.partner@example.com"
/review --report --12m --3 "Sam Report, sam.report@example.com"
/review --manager --6m --4 "Jordan Manager, jordan.manager@example.com"
/review --self --6m --3
```

---

### Two-Phase Process

**Phase 1: Gather Evidence** (Python tool + MCP calls)
Collects raw evidence from Brain, GDocs, Slack, Jira, and local files. Saves a RAW.md file.

**Phase 2: Write Review** (Claude synthesis)
Loads RAW.md + frameworks + review questions + tone guidance. Claude writes the structured review. Saves final .md file.

---

### Step 1: Parse and Validate Parameters

```python
from review_generator import ReviewGenerator
gen = ReviewGenerator()
params = gen.parse_params("$ARGUMENTS")
```

If parsing fails, display the error and usage help. Stop.

Report to user: Review type, timeframe, tone, person name.

---

### Step 2: Resolve Person

```python
person = gen.resolve_person(params)
```

Report: Person name, email, role, squad, category (report/manager/stakeholder/self).

If the person was not found in config and fell back to using the provided name/email as-is, warn the user that evidence gathering may be limited.

---

### Step 3: Load Frameworks

```python
frameworks = gen.load_frameworks()
```

Confirm values framework and career framework loaded (character counts). If either is missing, warn but continue.

---

### Step 4: Phase 1, Gather Evidence

Gather evidence sequentially from each source. Each source degrades gracefully: if unavailable, skip and continue.

**4a: Local Evidence (always available)**

```python
from datetime import datetime, timedelta
since = gen.get_timeframe_start(params)
local_data = gen.gather_local_evidence(person, since)
```

This scans `user/team/{category}/{slug}/1on1s/` and `user/team/{category}/{slug}/career/` for notes and career logs within the timeframe.

**4b: Brain Evidence**

Use Brain MCP tools to find the person entity and related projects:

```
mcp__brain__search_entities(query=person.name, entity_type="person", limit=5)
```

If found, get relationships:
```
mcp__brain__get_relationships(entity_id="{person_entity_id}")
```

For each related project, get entity details:
```
mcp__brain__get_entity(entity_id="{project_id}")
```

Collect: role, squad, project associations, relationship descriptions.

If Brain MCP is unavailable, log and skip.

**4c: GDocs Evidence**

Search for documents mentioning the person:

```python
queries = gen.get_gdocs_search_queries(person)
```

For each query:
```
mcp__gdrive__gdrive_search(query="{search_term}")
```

For each relevant result (1:1 notes, meeting notes, shared docs), read the content:
```
mcp__gdrive__gdrive_read(file_id="{file_id}")
```

Filter results to the timeframe. Keep document title, date, and relevant excerpts (first 3000 chars).

If GDrive MCP is unavailable, log and skip.

**4d: Slack Evidence**

Search for interactions between the reviewer and the person. Use Brain inbox or Slack MCP if available:

```
mcp__brain__query_knowledge(question="Recent interactions with {person.name}")
```

If Slack MCP is directly available, search for DMs and channel mentions.

If unavailable, log and skip.

**4e: Jira Evidence**

Build JQL queries for the person:

```python
jql_queries = gen.get_jira_queries(person, params)
```

If the connector bridge is available, execute each query. Otherwise log and skip.

Collect: ticket keys, summaries, statuses, story points, epics.

---

### Step 5: Save RAW Evidence File

Assemble all gathered data into a RawGatherResult and save:

```python
from review_generator import RawGatherResult, DataSourceResult
from datetime import datetime

result = RawGatherResult(
    params=params,
    person=person,
    sources=[local_data, brain_data, gdocs_data, slack_data, jira_data],
    gathered_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
)

raw_path = gen.save_raw(result)
```

Report to user:
- RAW file saved at `{raw_path}`
- Summary table: Source | Status | Entries count
- Total evidence entries
- Ask: "Review the raw evidence file and proceed to Phase 2 (write review), or stop here?"

If user wants to stop, end here. They can resume later by reading the RAW file.

---

### Step 6: Phase 2, Write Review

Build the review prompt:

```python
prompt = gen.build_review_prompt(result)
```

Read the RAW evidence file to have full context:
```
Read: {raw_path}
```

Load the review-writing skill for tone calibration guidance (the skill at `skills/review-writing/SKILL.md` provides anti-patterns and evidence standards).

Using the prompt, frameworks, questions, and tone guidance, write the review following this structure:

**For --report reviews:**
1. **[WHAT] Performance Impact** - Impact relative to level expectations, achievements, gaps
2. **[HOW] Behavioral Impact** - DNA exemplification, skills, competencies
3. **[WHAT & HOW] Development Focus** - 1-2 development areas
4. **[PEOPLE MANAGERS ONLY] Leadership & Development** - Team leadership behaviors (include only if the person manages people)

**For --self reviews:**
1. **[WHAT] Goals & Achievements** - Goals met, 1-2 impact examples
2. **[HOW] Skills & Behaviors** - Skills and DNA values demonstrated
3. **[WHAT & HOW] Development Focus** - What wasn't achieved, roadblocks, 1-2 focus areas
4. **[DEVELOPMENT] Support** - How manager/org can help
5. **[OPTIONAL] Other Highlights** - Non-regular work highlights

**For --peer reviews:**
1. **Interaction Description** - How you worked together
2. **Strengths** - Examples with impact (WHAT) and DNA (HOW)
3. **Areas of Opportunity** - Examples with specific actions

**For --manager reviews:**
1. **Impact & DNA** - Examples of impact (WHAT) and DNA (HOW)
2. **Areas for Improvement** - Specific examples and actions
3. **Specific Actions** - 1-2 behaviors to change

**Writing rules:**
- Ground every statement in specific evidence from the RAW file
- Cite dates, ticket numbers, project names
- Calibrate language and evidence emphasis to the tone parameter
- Reference the career framework for level-appropriate expectations
- Reference DNA values for behavioral assessment
- Follow anti-patterns guidance from the review-writing skill

---

### Step 7: Save Final Review

Save the completed review:

```python
output_path = gen.get_output_path(params, person)
```

Write the review content to `{output_path}`.

Report to user:
- Final review saved at `{output_path}`
- Review type, person, timeframe, tone
- Evidence sources used
- Remind: "This is a draft. Review and edit before submitting."
