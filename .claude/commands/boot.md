# Boot Agent Context

Load foundational context files and refresh daily context to initialize the agent with full operational knowledge.

## Arguments

The command accepts optional arguments:

- `full` - Full boot with git pull, context update, hot topics, FPF state **[default]**
- `quick` - Quick boot: core files + latest context only (skip git pull, external syncs, meeting prep)
- `no-pull` - Skip git pull (useful when working offline or avoiding merge conflicts)
- `context-only` - Load only the latest context file (fastest, minimal initialization)

**Examples:**
```
/boot           # Full boot sequence
/boot quick     # Fast startup - core files + context only
/boot no-pull   # Full boot but skip git pull
/boot context-only  # Just load today's context file
```

## Instructions

### Step 0: Sync from Git

**Skip if:** `quick`, `no-pull`, or `context-only` argument provided.

Pull the latest changes from the remote repository to ensure you're working with current context:

```bash
git pull origin main
```

This prevents stale context and ensures any work from previous sessions is available.

### Step 1: Load Core Context Files

**Skip if:** `context-only` argument provided.

Read the following files in order to establish context:

1. **AGENT.md** - Core agent entry point and mission
2. **AGENT_HOW_TO.md** - Operational procedures and workflows
3. **AI_Guidance/Rules/NGO.md** - Nikita Gorshkov style & ops guide
4. **AI_Guidance/Rules/AI_AGENTS_GUIDE.md** - Agent behavior guidelines

### Step 2: Update Daily Context

**Skip if:** `quick` or `context-only` argument provided. For quick/context-only, jump directly to Step 2a to find and read the latest context file.

Run the daily context updater to pull recent Google Docs:

```bash
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py
```

#### 2a. Find Latest Context File

Search for context files using pattern `YYYY-MM-[0-9]*-context.md` to match both:
- Simple dated: `2025-12-05-context.md`
- Versioned: `2025-12-05-03-context.md`

Files sort lexicographically (`-03` > `-02` > no suffix), so take the **last** file in sorted order to get the most recent.

#### 2b. If New Documents Fetched

1. Check for existing `YYYY-MM-DD-NN-context.md` files for today in `AI_Guidance/Core_Context/`
2. Create the next increment (e.g., `-02` exists → create `-03`)
3. Synthesize new content following NGO format:
   - Documents processed (table with links)
   - Key decisions (bulleted, by project/workstream)
   - Action items (checkbox format)
   - Blockers & risks
   - Key dates & milestones
4. Merge with previous context file, retaining unresolved blockers/decisions

#### 2c. If No New Documents

Read the latest context file (from 2a) to load existing context.

#### 2c.1. Check File Size Before Reading

Before reading any context or inbox file, check its size:

```bash
python3 AI_Guidance/Tools/file_chunker.py --check <FILE_PATH>
```

**If file needs chunking (exit code 1):**
1. Split the file first: `python3 AI_Guidance/Tools/file_chunker.py --split <FILE_PATH>`
2. Read chunks sequentially from the `chunks/` subdirectory
3. Each chunk is ~1500 lines (safe for context window)

**If file is OK (exit code 0):**
- Read normally with the Read tool

**Quick size check without chunking:**
```bash
wc -l <FILE_PATH>
```
If > 1500 lines, use chunked reading.

### Step 2d: Sync Jira Context (Optional)

**Skip if:** `quick` or `context-only` argument provided.

Run the Jira sync to fetch recent squad activity for New Ventures:

```bash
python3 AI_Guidance/Tools/jira_brain_sync.py
```

This will:
- Fetch epics, in-progress items, and blockers for New Ventures squads (GOC, TPT, RTEVMS, MIO)
- Write raw data to `Brain/Inbox/JIRA_YYYY-MM-DD.md`
- Update `Brain/Entities/Squad_*.md` with latest Jira status

**Options:**
- `--summarize` - Include Gemini-generated executive summary
- `--squad "Good Chop"` - Sync specific squad only
- `--github` - Include GitHub PR/commit links (Phase 2)

**Alternative:** Run with context updater using `--jira` flag:
```bash
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --jira
```

**Skip if:** Quick context refresh only, or Jira API unavailable.

### Step 2e: Sync GitHub Context (Optional)

**Skip if:** `quick` or `context-only` argument provided.

Run the GitHub sync to fetch PR activity and recent commits for New Ventures:

```bash
python3 AI_Guidance/Tools/github_brain_sync.py
```

This will:
- Fetch open PRs and recent commits for New Ventures squads
- Write raw data to `Brain/Inbox/GITHUB_YYYY-MM-DD.md`
- Create/update `Brain/GitHub/PR_Activity.md` and `Brain/GitHub/Recent_Commits.md`
- Update `Brain/Entities/Squad_*.md` with GitHub status

**Options:**
- `--summarize` - Include Gemini-generated summary
- `--squad "Good Chop"` - Sync specific squad only
- `--analyze-files` - Include file change analysis (slower)

**Skip if:** Quick context refresh only, or GitHub CLI unavailable.

### Step 3: Upload Context to GDrive

**Skip if:** `quick` or `context-only` argument provided.

After creating/updating the context file, upload it to Google Drive for backup and sharing:

```bash
python3 AI_Guidance/Tools/daily_context/daily_context_updater.py --upload AI_Guidance/Core_Context/YYYY-MM-DD-NN-context.md
```

Replace `YYYY-MM-DD-NN` with the actual filename created in Step 2b.

### Step 4: Load Hot Topics from Brain

**Skip if:** `context-only` argument provided.

Run the brain loader to identify entities mentioned in today's context and load relevant semantic knowledge:

```bash
python3 AI_Guidance/Tools/brain_loader.py
```

This will output:
- **Hot projects** mentioned today (with file paths)
- **Hot entities** (people, teams) mentioned
- **Architecture/systems** referenced
- Which Brain files exist vs need creation

**For each existing Brain file listed**, read it to gain deeper context:
- `Brain/Projects/OTP.md` - Full project background, roadmap, blockers
- `Brain/Projects/Influencer_Marketplace.md` - Strategy, stakeholders, decisions

**Note:** Missing Brain files are flagged for future creation during the session if significant new information emerges.

### Step 4b: Load FPF Reasoning State

**Skip if:** `quick` or `context-only` argument provided.

Check for active reasoning cycles and pending decisions:

```bash
python3 AI_Guidance/Tools/brain_loader.py --reasoning
```

This will output:
- **Active FPF cycles** - In-progress reasoning sessions requiring continuation
- **Pending DRRs** - Design Rationale Records awaiting decision
- **Expiring evidence** - Evidence approaching expiry date (needs re-validation)
- **Open hypotheses** - L0/L1 claims needing verification or corroboration

**If active cycles exist:**
1. Review `Brain/Reasoning/Active/` for cycle state
2. Consider resuming with `/q2-verify` or `/q3-validate`
3. Check if decisions are blocked on external input

**Sync reasoning state with Quint (optional):**
```bash
python3 AI_Guidance/Tools/quint_brain_sync.py --status
```

**Skip if:** No FPF reasoning work in progress.

### Step 5: Generate Meeting Pre-Reads (Optional)

**Skip if:** `quick` or `context-only` argument provided.

Run the meeting prep tool to generate pre-reads for today's upcoming meetings:

```bash
python3 AI_Guidance/Tools/meeting_prep/meeting_prep.py --hours 12
```

This will:
- **Auto-archive** past meeting pre-reads to `Planning/Meeting_Prep/Archive/`
- Fetch calendar events for the next 12 hours
- **Update existing** pre-reads or create new ones (no duplicates)
- Classify meeting types (1:1, standup, review, external, etc.)
- Gather context from Brain entities, projects, and action items
- Generate per-meeting pre-read files in `Planning/Meeting_Prep/`

**Output:** List of generated/updated files for quick access during meetings.

**Additional options:**
- `--archive` - Archive past meetings only (no new pre-reads)
- `--link-notes` - Search for meeting notes and link to Brain entities

**Skip if:** No meetings scheduled or running a quick context refresh.

### Step 6: Confirm Ready State

After completing steps 1-5 (including synthesis, upload, hot topics, and optional meeting prep), confirm:
- Active projects/priorities identified
- Key operational rules understood
- Daily context status (synthesized new file or current)
- Hot topics loaded (semantic depth)
- **FPF reasoning state** (active cycles, pending DRRs, expiring evidence)
- Meeting pre-reads generated (if applicable)
- Ready state for PM Assistant mode

**Reasoning State Summary Format:**
```
FPF: [N] active cycles | [M] DRRs | [K] evidence items expiring
```

## Execute

Read the core files and run the context updater now. Report back when context is loaded.
