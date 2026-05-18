---
description: Compute or update a Total Customer Value Add (TCVA) business case with full derivation chain
---

# TCVA Computation

Structured financial computation: 6 input levers, 3 scenarios, full math chain with cross-checks.

## When to Apply

- User asks for a TCVA, business case, or value estimation for a feature/initiative
- User has experiment results and wants to project annual value
- Updating a previous TCVA with new data

## TCVA Model Overview

**TCVA = CCVA + ACVA** (Converted Customer Value Add + Active Customer Value Add)

- **CCVA** = f(Gross Conversions, AOR_conv, AOV_conv, PCII_conv)
- **ACVA** = f(Weekly Active Customers, AOR_actives, AOV_actives, Active Base change, PCII_actives)

## 6 Input Levers (3 Scenarios Each)

| Lever | What drives it |
|-------|---------------|
| AOR (actives) | How the feature changes order rate for active customers |
| AOR (conv) | How the feature changes order rate for converting customers |
| Conversions | Incremental conversion rate change |
| AOV (conv) | Average order value change for converting customers |
| AOV (actives) | Average order value change for active customers |
| Active base | Change in active customer base (from retention/churn reduction) |

## Protocol

### Step 1: Gather Inputs

Ask the user (or check Brain/context) for:
- Feature name and experiment data source
- Key metric deltas (OCR, OC, cancel, revenue, etc.)
- Mechanism split (what % of effect is direct vs indirect)
- Engagement rate (current measured, projected at scale)
- Which levers are grounded (backed by data) vs ungrounded (speculative)
- Baseline values (or use company template if available)

### Step 2: Derive Lever Values

For each lever, show the full derivation chain:
1. Start from the raw experimental signal
2. Apply mechanism split
3. Apply engagement scaling with diminishing returns
4. Show the per-lever delta for conservative / base / optimistic

Document every assumption. Number them. Flag grounded vs speculative.

### Step 3: Compute TCVA

For each scenario:
```
New AOR_conv = baseline * (1 + lever%)
New AOV_conv = baseline * (1 + lever%)
New CCVA = Conversions * (1 + conv_lever%) * New_AOR_conv * New_AOV_conv * PCII_conv
CCVA_delta = New_CCVA - Status_quo_CCVA

New Active = baseline * (1 + active_base_lever%)
New AOR_act = baseline * (1 + lever%)
New AOV_act = baseline * (1 + lever%)
New ACVA = New_Active * New_AOR_act * New_AOV_act * PCII_actives
ACVA_delta = New_ACVA - Status_quo_ACVA

TCVA = CCVA_delta + ACVA_delta
```

Show intermediate values at every step.

### Step 4: Cross-Check

- Verify TCVA = CCVA + ACVA
- Verify conservative < base < optimistic (monotonicity)
- Sensitivity: what if the key signal is half as strong? Still compelling?
- Compute range ratio (optimistic / conservative)

### Step 5: Output

**Input Levers Table:**
| Lever | Conservative | Base | Optimistic |
|-------|-------------|------|------------|

**Results Table:**
| Scenario | CCVA | ACVA | TCVA | vs Baseline |
|----------|------|------|------|-------------|

Plus: numbered assumptions (grounded/speculative), sensitivity note, what breaks the base case.

## Rules

- Show all math with intermediate values — every step visible
- Cross-check: does the total equal sum of parts?
- If updating a prior TCVA, derive from raw numbers — don't adjust from old output
- Never use a broken metric's rate to derive expected values
- Flag the age of all input data
