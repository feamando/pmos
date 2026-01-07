# Analyze Codebase

Analyze a GitHub repository and create/update its Technical Brain entry.

## Arguments

- `<repo>` - GitHub repository in format `owner/repo` (e.g., `hellofresh/web`)
- `--all` - Analyze all priority repositories

## Usage

```
/analyze-codebase hellofresh/web
/analyze-codebase --all
```

## Instructions

### Step 1: Run Analysis

```bash
python3 AI_Guidance/Tools/tech_context_sync.py --analyze $ARGUMENTS
```

If `--all` is passed:
```bash
python3 AI_Guidance/Tools/tech_context_sync.py --all
```

### Step 2: Verify Output

The tool will create/update:
- `Brain/Technical/repositories/<owner>_<repo>.md`

Read the generated file to verify the analysis:

```bash
cat AI_Guidance/Brain/Technical/repositories/*.md | head -50
```

### Step 3: Report Results

Report to user:
- Repository analyzed
- Tech stack detected (framework, language, state management)
- Key directories found
- Path to generated file

### Step 4: Suggest Next Steps

If this is a New Ventures relevant repo, suggest:
- Link to relevant Project in Brain (e.g., `Brain/Projects/Good_Chop.md`)
- Consider updating the Project's Technical Context section

## Priority Repos

| Repo | Type |
|------|------|
| `hellofresh/web` | Consumer frontend |
| `hellofresh/whitelabel-mobile` | Mobile apps |
| `hellofresh/engagement-dau` | Backend services |
| `hellofresh/consumer-bff` | BFF layer |

## Output

```
Technical Brain Updated
=======================
Repository: hellofresh/web
Tech Stack: Next.js, TypeScript, Zustand
Testing: Jest, RTL, Playwright
File: Brain/Technical/repositories/hellofresh_web.md
```
