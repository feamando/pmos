# Analyze Codebase

Analyze a GitHub repository and create/update its Technical Brain entry.

## Arguments

- `<repo>` - GitHub repository in format `owner/repo` (e.g., `acme-corp/web`)
- `--all` - Analyze all priority repositories

## Usage

```
/analyze-codebase acme-corp/web
/analyze-codebase --all
```

## Instructions

### Step 1: Run Analysis

```bash
python3 "$PM_OS_COMMON/tools/integrations/tech_context_sync.py" --analyze $ARGUMENTS
```

If `--all` is passed:
```bash
python3 "$PM_OS_COMMON/tools/integrations/tech_context_sync.py" --all
```

### Step 2: Verify Output

The tool will create/update:
- `Brain/Technical/repositories/<owner>_<repo>.md`

Read the generated file to verify the analysis:

```bash
cat $PM_OS_USER/brain/Technical/repositories/*.md | head -50
```

### Step 3: Report Results

Report to user:
- Repository analyzed
- Tech stack detected (framework, language, state management)
- Key directories found
- Path to generated file

### Step 4: Suggest Next Steps

If this is a Growth Division relevant repo, suggest:
- Link to relevant Project in Brain (e.g., `Brain/Projects/Meal_Kit.md`)
- Consider updating the Project's Technical Context section

## Priority Repos

| Repo | Type |
|------|------|
| `acme-corp/web` | Consumer frontend |
| `acme-corp/whitelabel-mobile` | Mobile apps |
| `acme-corp/engagement-dau` | Backend services |
| `acme-corp/consumer-bff` | BFF layer |

## Output

```
Technical Brain Updated
=======================
Repository: acme-corp/web
Tech Stack: Next.js, TypeScript, Zustand
Testing: Jest, RTL, Playwright
File: Brain/Technical/repositories/acme-corp_web.md
```
