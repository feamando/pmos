# Tribe Quarterly Update Generator

Generate the Tribe-Level Update document for the Global Central Functions Q1-2026 Planning Offsite.

## Arguments
$ARGUMENTS

## Instructions

Generate the 2-pager Tribe Quarterly Update document required for the Planning Offsite.

### Mode Selection

Parse the arguments:
- **Standard mode:** `/tribe-update` or `/tribe-update Growth Division` - Fast generation
- **Orthogonal mode:** `/tribe-update --orthogonal` - 3-round Claude vs Gemini challenge
- **Status:** `/tribe-update --status` - Check existing updates

### Default Configuration

- **Tribe:** Growth Division (default)
- **Quarter:** Q1-2026 (target/future quarter for roadmap)
- **Previous Quarter:** Q4-2025 (review quarter for blockers/learnings)
- **Squads:** Meal Kit, Brand B, Growth Platform, Product Innovation
- **Deadline:** Friday, January 9, 2026 (EOD)

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--tribe` | Tribe name | Growth Division |
| `--quarter` | Target quarter for roadmap/goals | Q1-2026 |
| `--prev-quarter` | Previous quarter for review/blockers | Q4-2025 |
| `--squad` | Generate for specific squad only | All squads |
| `--orthogonal` | Enable Claude<>Gemini challenge | Off |
| `--output` | Custom output path | Auto-generated |
| `--status` | Show existing updates | - |
| `--json` | Output as JSON | - |

---

### Standard Mode: Fast Generation

1. Run the tribe update generator:
   ```bash
   python3 "$PM_OS_COMMON/tools/reporting/tribe_quarterly_update.py" --tribe "Growth Division"
   ```

2. Wait for generation (1-2 minutes)

3. The script will:
   - Gather context from recent daily context files
   - Extract blockers and initiatives from Brain
   - Pull Jira data if available
   - Generate the 2-pager template

4. Report output location:
   - Output: `Planning/Quarterly_Updates/growth_division_Q1-2026_YYYY-MM-DD.md`

5. **CRITICAL:** Inform user they must:
   - Fill in [bracketed] sections with actual Q4 metrics
   - Review systemic blockers for accuracy
   - Add specific KPIs and dependencies
   - Keep document to 2 pages maximum

---

### Orthogonal Mode: Rigorous 3-Round Challenge

For high-stakes planning documents requiring multi-perspective validation:

1. Run the orthogonal challenge:
   ```bash
   python3 "$PM_OS_COMMON/tools/reporting/tribe_quarterly_update.py" --tribe "Growth Division" --orthogonal
   ```

2. This will execute:
   - **Round 1 (Claude):** Create initial document with research + FPF reasoning
   - **Round 2 (Gemini):** Challenge blockers, question learnings, propose alternatives
   - **Round 3 (Claude):** Resolve challenges, produce final document

3. Wait for completion (10-15 minutes)

4. Report outputs:
   - Final document: `Brain/Reasoning/Orthogonal/<id>/v3_final.md`
   - Challenge FAQ: Shows all challenges and resolutions
   - DRR: Stored in `Brain/Reasoning/Decisions/`

---

### Data Sources

The generator pulls from:

1. **Brain/Projects/**: OTP, VMS, Meal_Kit, Brand_B, Growth_Platform related files
2. **Brain/Entities/**: Squad files for each Growth Division squad
3. **Core_Context/**: Last 30 days of daily context files
4. **Brain/Inbox/**: JIRA files for blocker extraction
5. **Planning/**: Yearly plans and roadmaps

---

### Document Sections (Required)

| Section | Description | Data Source |
|---------|-------------|-------------|
| I. Executive Summary | Q4-2025 metrics, mission, strategic relevance | Context files, Brain |
| II. Systemic Blockers | Top 3 cross-functional blockers + root cause | Context blockers, Jira |
| III. Key Learnings | Top 3 learnings + mitigation plan | Context, retrospectives |
| IV. Q1-2026 Roadmap | 5-row table with projects, KPIs, DoD | Brain projects, roadmaps |
| V. Dependencies | Cross-functional dependencies | Context, Jira |
| VI. Hot Debates | Open questions needing resolution | Context, recent discussions |

---

### Deliverable Requirements

From the Planning Offsite guidelines:

1. **Length:** Maximum 2 pages (no appendices)
2. **Owner:** Tribe Lead (Jane Smith)
3. **Deadline:** Friday before Offsite (Jan 9, 2026 EOD)
4. **Submission:** Email to Planning Coordinator
5. **Companion:** 2-slide deck also required

---

### Post-Generation Steps

After generating:

1. **Read the output file** - Show key sections to user
2. **Identify gaps** - Highlight [bracketed] sections needing input
3. **Offer to help fill** - Use context to suggest metrics/blockers
4. **Remind about slides** - 2-slide deck also due

---

## Examples

**Quick generation (current defaults Q1-2026):**
```
/tribe-update
```

**With specific quarters:**
```
/tribe-update --quarter Q2-2026 --prev-quarter Q1-2026
```

**With orthogonal challenge:**
```
/tribe-update --orthogonal
```

**Check status:**
```
/tribe-update --status
```

**Specific squad focus:**
```
/tribe-update --squad "Meal Kit"
```

**Full example with all parameters:**
```
python3 "$PM_OS_COMMON/tools/reporting/tribe_quarterly_update.py" --tribe "Growth Division" --quarter Q1-2026 --prev-quarter Q4-2025
```

## Notes

- Standard mode: 1-2 minutes
- Orthogonal mode: 10-15 minutes
- Document must be ≤2 pages for offsite
- Submit to Planning Coordinator by Jan 9 EOD
- Template based on Tech Platform Tribe Quarterly Planning Update Template
