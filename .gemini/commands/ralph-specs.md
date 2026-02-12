# Ralph Specs

Create acceptance criteria and specifications for a Ralph feature.

## Arguments

- `<feature>` - Feature name (required)

**Examples:**
```
/ralph-specs user-authentication
/ralph-specs shopify-integration
```

## Instructions

### Step 1: Verify Feature Exists

Check that the feature was initialized:

```bash
python3 "$PM_OS_COMMON/tools/ralph/ralph_manager.py" status <feature>
```

If not found, suggest: `/ralph-init <feature>` first.

### Step 2: Gather Requirements

Read the feature's PROMPT.md to understand context:
- What is being built?
- What are the constraints?
- What Brain entities are relevant?

Ask the user clarifying questions:
1. What is the high-level goal?
2. What are the key deliverables?
3. Are there dependencies or blockers?
4. What does "done" look like?

### Step 3: Generate Acceptance Criteria

Create a comprehensive list of acceptance criteria that:
- Are specific and verifiable
- Can be completed in 1-2 context windows each
- Are ordered logically (dependencies first)
- Cover all aspects of the feature

**Format each criterion as:**
```markdown
- [ ] [Phase] Specific, verifiable acceptance criterion
```

**Organize into phases:**
1. **Foundation** - Setup, infrastructure, dependencies
2. **Implementation** - Core feature work
3. **Integration** - Connect with existing systems
4. **Verification** - Testing, documentation

### Step 4: Write PLAN.md

Update the feature's PLAN.md with the acceptance criteria:

```markdown
# Plan: <Title>

**Feature**: <feature>
**Created**: <date>
**Status**: In Progress

## Description

<Brief description of what we're building and why>

## Acceptance Criteria

### Phase 1: Foundation
- [ ] Criterion 1
- [ ] Criterion 2

### Phase 2: Implementation
- [ ] Criterion 3
- [ ] Criterion 4
- [ ] Criterion 5

### Phase 3: Integration
- [ ] Criterion 6

### Phase 4: Verification
- [ ] Criterion 7
- [ ] Criterion 8

---
*Progress: 0/8 (0%) | Iteration: 0*
```

### Step 5: Create specs/ Files (Optional)

For complex features, create detailed spec files:

```
specs/
├── features.json       # Machine-readable feature list
├── architecture.md     # Technical design
├── dependencies.md     # External dependencies
└── risks.md           # Known risks and mitigations
```

### Step 6: Confirm and Report

Show the user:
- Total number of acceptance criteria
- Estimated iterations (1-2 per criterion)
- Any criteria that seem too large (suggest splitting)

**Output format:**
```
Specs created for: <feature>
  Criteria: <N> items across <M> phases
  Estimated iterations: <N> to <2N>

Ready to start: /ralph-loop <feature>
```

## Guidelines for Good Criteria

**Good criteria:**
- "Create user model with email, password_hash, created_at fields"
- "Implement login endpoint with JWT token generation"
- "Add unit tests for authentication service"

**Bad criteria (too vague):**
- "Build authentication" (too broad)
- "Make it work" (not verifiable)
- "Fix bugs" (not specific)

**Bad criteria (too small):**
- "Add import statement" (combine with related work)
- "Fix typo" (not worth an iteration)

## Execute

Read the feature context and generate comprehensive acceptance criteria in PLAN.md.
