---
description: Enforce pre-flight discipline checks on every response — verify dates, facts, doc state, and analysis freshness
---

# Pre-Flight Discipline

Mandatory pause-and-check before generating any substantive response. Enforced by the `preflight_checklist.py` hook.

## When to Apply

- Every response (hook injects the checklist automatically)
- This skill documents the reasoning and full protocol behind each check

## The Four Checks

### 1. Date Verification

**Trigger:** Response names a day of the week.

**Rule:** Verify programmatically. Never compute mentally. If user stated a day, trust them — verify silently without contradicting.

### 2. Factual Accuracy

**Trigger:** About to state a number, metric, or factual claim.

**Rule:**
- Verify before stating
- If unverified: explicitly say "I haven't verified this"
- Never state hypotheses as facts
- Retract immediately when wrong — don't re-derive the wrong claim differently

### 3. Document Work Protocol

**Trigger:** Any document writing or editing requested (even "just fix the phrasing").

**Rule:**
1. Read the FULL document first
2. State the document's job (who reads it, what decision it supports)
3. Assess the structure
4. Present thinking BEFORE editing
5. Never go straight to edits

### 4. Fresh Re-Analysis

**Trigger:** Re-analyzing something previously analyzed.

**Rule:**
1. Pull fresh raw data
2. Derive conclusion from scratch
3. Compare to old conclusion AFTER, not before

Starting from the old conclusion and adjusting is anchoring bias. Start fresh every time.

## Why Hooks, Not Rules

These checks fail as passive AGENT.md rules because they require pausing mid-thought — the AI has already started generating before it remembers to check. The hook solves this by injecting the checklist into context at the start of every turn, creating a mandatory pause point.
