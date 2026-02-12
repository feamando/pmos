# Sprint Learnings Generator

Generate structured key learnings from delivered sprint items using Claude's analysis, then save back to the CSV.

## Arguments
$ARGUMENTS

## Instructions

### Step 1: Find the Latest Sprint Report

```bash
ls -t "$PM_OS_USER/planning/Reporting/Sprint_Reports/Sprint_Report_"*.csv 2>/dev/null | head -1
```

If no report found, tell the user to run `/sprint-report` first.

### Step 2: Extract Delivered Items for Squad

Parse the CSV and extract the "Delivered" column for the specified squad.

If no squad argument provided, list available squads from the CSV and ask which one to analyze.

If argument is "all", process all squads in the CSV sequentially.

### Step 3: Generate Key Learnings

Analyze the delivered tickets and generate learnings using this EXACT format:

```
**Key Learnings ([Squad Name])**

**Learning:** [Short, specific title - identify the pattern or insight]
**Evidence:** [Ticket references and what specifically happened - be concrete]
**Action:** [Specific, actionable recommendation]

---

**Learning:** [Next insight]
**Evidence:** [Evidence]
**Action:** [Action]

---

[Repeat for 3-6 learnings depending on ticket volume]

**Sprint Health Signals:**
- **Positive:** [What went well - reference specific tickets]
- **Watch:** [Areas needing attention]
```

### Analysis Guidelines

When analyzing tickets, look for these patterns:

**Security & Access Control:**
- Auth guards, permissions, access control issues
- Investigation tickets that led to fixes

**Data Quality & Hygiene:**
- Cleanup tasks, stale data, data consistency issues
- Multiple bugs from same data source

**Technical Debt:**
- Refactoring work, 429 errors, rate limiting
- Performance issues surfaced in UAT

**Process Gaps:**
- Experiment health issues caught reactively
- Missing documentation created mid-sprint
- Edge cases missed in testing (cancelled users, etc.)

**Operational Load:**
- Firefighter rotations, KTLO work
- Runbook updates, incident post-mortems

**Feature Patterns:**
- Skeleton-first approaches
- Platform migrations, redirects
- New capabilities enabling future work

### Output Rules

1. Be SPECIFIC - reference actual ticket numbers
2. Be ACTIONABLE - actions should be concrete, not vague
3. Be CONCISE - each learning should be 2-3 sentences max
4. IDENTIFY PATTERNS - group related tickets under single learnings
5. Use the EXACT format above (not markdown tables)

### Example Output

**Key Learnings (Meal Kit)**

**Learning:** OTP security needed proactive hardening
**Evidence:** MK-3442 investigation revealed missing auth guards; MK-3443 added LoggedInUserGuard. Dashboard was accessible without proper authentication checks.
**Action:** Add auth guard review to new module checklist before launch.

---

**Learning:** Data hygiene debt accumulates fast
**Evidence:** MK-3445 required cleanup of stale address data created during OTP checkout testing. Technical debt from rapid iteration.
**Action:** Build data cleanup scripts alongside feature development, not after.

---

**Learning:** Experiment monitoring gaps
**Evidence:** MK-3440 flagged "mr_charge_at_checkout" as unhealthy - caught reactively, not proactively.
**Action:** Establish weekly experiment health review cadence.

---

**Sprint Health Signals:**
- **Positive:** OTP navigation in place (MK-3449), experimentation capability advancing (MK-3341 POC)
- **Watch:** Firefighting load, experiment hygiene, security-by-default practices

### Step 4: Save Learnings to CSV

After generating the learnings, update the CSV file using this Python script:

```python
import csv
import sys

def update_learnings(csv_path: str, squad_name: str, learnings_text: str):
    """Update the Key Learnings column for a specific squad."""
    rows = []
    fieldnames = None

    # Read existing CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['Squad'] == squad_name:
                row['Key Learnings'] = learnings_text
            rows.append(row)

    # Write back
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {csv_path} - {squad_name} learnings saved")

# Usage: update_learnings(csv_path, squad_name, learnings_text)
```

Run this script with:
- `csv_path`: The path to the sprint report CSV
- `squad_name`: The squad name (e.g., "Meal Kit")
- `learnings_text`: The full learnings text you generated (everything from "**Learning:**" to the end of "**Sprint Health Signals:**")

### Step 5: Confirm Update

After updating the CSV, confirm to the user:

```
Updated [CSV filename] - [Squad Name] learnings saved.
```

If processing "all" squads, show:

```
Updated [CSV filename]:
- Meal Kit: 5 learnings
- Growth Platform: 4 learnings
- Wellness Brand: 5 learnings
- Product Innovation: 2 learnings
```
