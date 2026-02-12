# Career Planning System

Create and maintain career planning documents for team members, tracking projects and feedback over review cycles.

## Arguments
$ARGUMENTS

## Instructions

Parse the user's request to determine the mode:

### Mode Selection

| Flag | Command Example | Purpose |
|------|----------------|---------|
| `-create` | `/career-planning -create Daniel` | Initialize career plan for a person |
| `-WHAT` | `/career-planning -WHAT Daniel S2026` | Generate "What" (projects/body of work) section |
| `-HOW` | `/career-planning -HOW Daniel S2026` | Generate "How" (behavioral/DNA) section |
| `-status` | `/career-planning -status Daniel` | Show current tracking status |
| `-sync` | `/career-planning -sync Daniel` | Force sync projects and feedback |
| `-upload` | `/career-planning -upload Daniel` | Upload career plan to GDrive |
| `-download` | `/career-planning -download Daniel` | Download latest from GDrive and merge |

**Cycle Format:**
- Main cycles: `S2025`, `S2026`, `S2027` (Summer/May-to-May)
- Off-cycles: `W2025`, `W2026`, `W2027` (Winter check-ins)

---

### Mode: -create {NAME}

Initialize a new career plan and enable tracking for a team member.

1. **Find or create person entity**

   Check if Brain entity exists:
   ```bash
   ls $PM_OS_USER/brain/Entities/People/ | grep -i "{NAME}"
   ```

   If not found, create a basic entity file.

2. **Determine current cycle**

   Based on current date:
   - January-April: Still in previous Summer cycle (e.g., Jan 2026 = S2026, data from May 2025)
   - May-December: Current Summer cycle (e.g., Aug 2026 = S2026)

3. **Create career plan directory**

   ```bash
   mkdir -p $PM_OS_USER/Planning/Career/{NAME}
   ```

4. **Generate initial career plan from template**

   Read the template:
   - `$PM_OS_USER/context/Frameworks/Career_Plan_Template.md`

   Create the career plan file:
   - `$PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md`

   Auto-populate SECTION 1 (Background Information) from:
   - Brain entity: Role, manager, team, hire date
   - Leave ratings/tenure as placeholders for manual entry

5. **Create running log files**

   Create empty log files:
   - `$PM_OS_USER/Planning/Career/{NAME}/project_log.md`
   - `$PM_OS_USER/Planning/Career/{NAME}/feedback_log.md`

6. **Scan for existing data**

   Search for projects and feedback from:
   - 1:1 meeting series: `$PM_OS_USER/Planning/Meeting_Prep/Series/*{NAME}*`
   - Context documents: `$PM_OS_USER/context/` (mentions of {NAME})
   - Jira: `$PM_OS_USER/brain/Inbox/JIRA_*.md`
   - GitHub: `$PM_OS_USER/brain/Inbox/GITHUB_*.md`

   Populate initial entries in running logs.

7. **Upload to GDrive**

   After creation, automatically upload to GDrive:
   ```bash
   python3 $PM_OS_COMMON/tools/daily_context/daily_context_updater.py --upload $PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md
   ```

   Store the GDrive link in `$PM_OS_USER/Planning/Career/{NAME}/gdrive_link.txt`.

8. **Report completion**

   Output:
   - Career plan file path
   - GDrive link for sharing
   - Number of projects found
   - Number of feedback entries found
   - Instructions for next steps

---

### Mode: -WHAT {NAME} {CYCLE}

Generate the "WHAT" (Body of Work) section from tracked projects.

1. **Auto-download from GDrive (if linked)**

   Check for `$PM_OS_USER/Planning/Career/{NAME}/gdrive_link.txt`. If exists:
   - Download latest from GDrive
   - Merge user-edited sections (Background, Future Role, Business Need, Peer Feedback)
   - Preserve local auto-generated sections

   This ensures user edits are captured before regenerating.

2. **Load career plan**

   Read: `$PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md`

   If not found, prompt user to run `-create` first.

3. **Determine date range for cycle**

   - `S2026`: May 1, 2025 to April 30, 2026 (or current date if within cycle)
   - `W2026`: November 1, 2025 to January 31, 2026

4. **Gather project data from all sources**

   **Source 1: Project Log**
   Read: `$PM_OS_USER/Planning/Career/{NAME}/project_log.md`

   **Source 2: 1:1 Meeting Notes**
   Search for project mentions in:
   ```bash
   grep -r "{NAME}" $PM_OS_USER/Planning/Meeting_Prep/Series/ --include="*.md"
   ```
   Look for: project names, deliverables, milestones, outcomes

   **Source 3: Context Documents**
   Search `$PM_OS_USER/context/` files within date range for {NAME} mentions with project context.

   **Source 4: Jira Data**
   Search `$PM_OS_USER/brain/Inbox/JIRA_*.md` for epics/projects owned by {NAME}.

   **Source 5: GitHub Data**
   Search `$PM_OS_USER/brain/Inbox/GITHUB_*.md` for PRs by {NAME}.

5. **Rank projects by impact**

   Scoring criteria:
   - Frequency of mention (more = higher impact)
   - Explicit ownership statements ("led", "owned", "drove")
   - Business outcomes mentioned (revenue, metrics, launches)
   - Cross-team dependencies (indicates scope)
   - Technical complexity mentioned

   Select top 3-5 projects for inclusion.

6. **Generate WHAT narrative**

   For each top project, generate structured content:

   ```markdown
   **{Project Name}**

   **[Scope & Influence]** {Who was involved, what teams, what dependencies}

   **[Impact]** {Quantifiable outcomes, metrics, business value}

   **[Ambiguity / Technical Complexity]** {Challenges navigated, new domains, innovations}
   ```

   Use the HF DNA lens:
   - Speed & Agility: Fast delivery, bias for action
   - Data-Drivenness: Metrics-driven decisions
   - Ownership: End-to-end responsibility

7. **Update career plan**

   Replace the "#### WHAT (Body of Work)" section in the career plan with the generated content.

   Add timestamp: `> *Last updated: {DATE}*`

8. **Report**

   Output:
   - Projects included
   - Projects excluded (and why)
   - Gaps to investigate

---

### Mode: -HOW {NAME} {CYCLE}

Generate the "HOW" (Behavioral Evidence) section from feedback data.

1. **Auto-download from GDrive (if linked)**

   Check for `$PM_OS_USER/Planning/Career/{NAME}/gdrive_link.txt`. If exists:
   - Download latest from GDrive
   - Merge user-edited sections (Background, Future Role, Business Need, Peer Feedback)
   - Preserve local auto-generated sections

   This ensures user edits are captured before regenerating.

2. **Load career plan and feedback log**

   Read:
   - `$PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md`
   - `$PM_OS_USER/Planning/Career/{NAME}/feedback_log.md`

3. **Gather feedback data**

   **Source 1: Feedback Log**
   Parse existing feedback entries with DNA value mappings.

   **Source 2: 1:1 Meeting Notes**
   Search for feedback patterns:
   - "Feedback for {NAME}..."
   - "{NAME} did well on..."
   - "{NAME} needs to improve..."
   - "Coaching point for {NAME}..."
   - Recognition statements
   - Concerns or risks about {NAME}

   **Source 3: Peer Feedback (if available)**
   Check for any stored peer feedback in career plan or related docs.

4. **Map feedback to HF DNA values**

   | DNA Value | Keywords/Patterns |
   |-----------|-------------------|
   | Speed & Agility | fast, quick, proactive, bias for action, shipped, delivered |
   | Data-Drivenness | metrics, data, analysis, evidence, measured, A/B test |
   | Egolessness | team, collaboration, learning, mentor, humble, feedback |
   | Customer Centricity | customer, user, experience, value, impact |
   | Ownership | owned, responsible, initiative, accountable, long-term |

   Classify each feedback entry to a DNA value.

5. **Generate HOW narrative**

   For each DNA value, synthesize evidence:

   ```markdown
   **[Speed & Agility - Proactivity & Drive]**
   {Synthesized evidence with specific examples}

   **[Data-Drivenness - Business Focus]**
   {Evidence of metrics-driven approach}

   **[Egolessness - Learning Never Stops]**
   {Evidence of continuous learning, mentoring others}

   **[Customer Centricity]**
   {Evidence of customer-first thinking}

   **[Ownership]**
   {Evidence of taking responsibility, long-term thinking}
   ```

6. **Update career plan**

   Replace the "#### HOW (Behavioral Evidence)" section with generated content.

   Add timestamp.

7. **Report**

   Output:
   - Feedback entries used
   - DNA values with strong evidence
   - DNA values needing more evidence

---

### Mode: -status {NAME}

Show current tracking status for a team member.

1. **Check if career plan exists**

   Look for: `$PM_OS_USER/Planning/Career/{NAME}/Career_Plan_*.md`

2. **Report status**

   - Current cycle
   - Last update date
   - Project count in log
   - Feedback count in log
   - WHAT section: populated/empty
   - HOW section: populated/empty
   - Next recommended action

---

### Mode: -sync {NAME}

Force a full sync of projects and feedback for a team member.

1. **Run project detection**

   Scan all sources for new projects since last sync.
   Append new entries to project_log.md.

2. **Run feedback detection**

   Scan 1:1 notes for new feedback since last sync.
   Append new entries to feedback_log.md with DNA mapping.

3. **Update running log sections**

   Update the "Projects (Running Log)" and "Feedback (Running Log)" tables in the career plan.

4. **Report**

   - New projects found
   - New feedback entries found
   - Last sync timestamp

---

### Mode: -upload {NAME}

Upload the career plan to Google Drive for sharing and collaboration.

1. **Find the career plan**

   ```bash
   ls $PM_OS_USER/Planning/Career/{NAME}/Career_Plan_*.md
   ```

2. **Upload to GDrive**

   ```bash
   python3 $PM_OS_COMMON/tools/daily_context/daily_context_updater.py --upload $PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md --upload-folder "CAREER_PLANS_FOLDER_ID"
   ```

   **Note:** If no folder ID is configured, upload to root and note the file ID.

3. **Store GDrive link**

   Save the returned file ID and link in `$PM_OS_USER/Planning/Career/{NAME}/gdrive_link.txt`:
   ```
   File ID: {FILE_ID}
   Link: {GDRIVE_LINK}
   Last Upload: {TIMESTAMP}
   ```

4. **Report**

   Output the GDrive link for sharing.

---

### Mode: -download {NAME}

Download the latest version from GDrive and merge with local changes.

1. **Check for GDrive link**

   Read `$PM_OS_USER/Planning/Career/{NAME}/gdrive_link.txt` to get the file ID.

   If not found, warn user and suggest `-upload` first.

2. **Download from GDrive**

   ```bash
   python3 $PM_OS_COMMON/tools/download_gdrive_file.py --file-id {FILE_ID} --output /tmp/career_plan_remote.md
   ```

3. **Compare and merge**

   - Read local: `$PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md`
   - Read remote: `/tmp/career_plan_remote.md`
   - Identify sections updated by user (Background, Future Role, Business Need, Peer Feedback)
   - Preserve user-edited sections from remote
   - Keep auto-generated sections (WHAT, HOW, Running Logs) from local if newer

4. **Update local file**

   Write merged content back to local career plan.

5. **Report**

   - Sections merged from GDrive
   - Sections kept from local
   - Conflicts (if any)

---

## Auto-Sync Integration

When `/update-context` runs:

1. Check for tracked career plans in `$PM_OS_USER/Planning/Career/`
2. For each tracked person, check if new 1:1 notes exist
3. If found, extract feedback and update feedback_log.md
4. Log the update

---

## Examples

**Initialize career tracking:**
```
/career-planning -create Daniel
/career-planning -create Bea
```

**Generate promotion sections:**
```
/career-planning -WHAT Daniel S2026
/career-planning -HOW Daniel S2026
```

**Check status:**
```
/career-planning -status Daniel
```

**Force sync:**
```
/career-planning -sync Daniel
```

---

## Output Locations

| Output | Path |
|--------|------|
| Career Plan | `$PM_OS_USER/Planning/Career/{NAME}/Career_Plan_{CYCLE}.md` |
| Project Log | `$PM_OS_USER/Planning/Career/{NAME}/project_log.md` |
| Feedback Log | `$PM_OS_USER/Planning/Career/{NAME}/feedback_log.md` |

---

## Notes

- Main review cycles run May-to-May (S2025, S2026, etc.)
- Winter cycles (W2026) are off-cycle check-ins
- Projects span cycles - attribute to cycle where majority of work occurred
- Feedback accumulates over time - run `-HOW` before review deadline
- Template follows HF FOODIE promotion case format

## GDrive Sync

- Career plans are automatically uploaded to GDrive on creation
- Users can edit the GDrive version directly (Background, Future Role, Business Need, Peer Feedback)
- `-WHAT` and `-HOW` automatically download from GDrive first to capture user edits
- Auto-generated sections (WHAT, HOW, Running Logs) are preserved from local
- GDrive link stored in `$PM_OS_USER/Planning/Career/{NAME}/gdrive_link.txt`
- Use `-download` manually if you need to pull edits without regenerating sections

## 1:1 Meeting Integration

- Career plans are automatically included in 1:1 meeting pre-reads
- Shows: current cycle status, recent projects, feedback summary, DNA gaps
- Helps ensure career development is discussed regularly
- Use `--skip-career` flag in meeting-prep to exclude
