---
id: arch-owl
title: OWL (Order/Refund Management)
type: system
status: Active
last_updated: 2025-12-08
related:
  - "[[Projects/Good_Chop.md]]"
  - "[[Projects/The_Pets_Table.md]]"
---

# OWL

## Overview

OWL is the order and refund management system. Currently experiencing issues with refund processing for Charge at Checkout (C@C) orders.

## Known Issues

### C@C Refund Bug
- **Status:** Active blocker
- **Symptom:** Refunds not triggering for C@C customers
- **Workaround:** Refunds work via Bob (alternative system)
- **Jira:** SE-22404
- **Impact:** Blocking Good Chop and TPT C@C allocation increases

## Integration Points

- Good Chop - Charge at Checkout
- The Pets Table - Charge at Checkout
- Bob (fallback refund system)

## Changelog
- **2025-12-16:** Context update: **Concept:** "Context-Driven Product Management" â€“ automating knowledge curation to feed AI tools.
- **2025-12-11:** Context update: **Good Chop "Charge at Checkout" Refunds:** Not processing via OWL. (Jira SE-22404).
- **2025-12-09:** Context update: **Good Chop "Charge at Checkout"**: Refunds not processing via OWL. (Jira SE-22404).
- **2025-12-08:** Context update: **New Recipes**: Multiple new recipes in pipeline (Greek Isle Caper Salmon, Greek-Style Market Chicken Bowl, Red Pepper Bruschetta Shredded Chicken, G

- **2025-12-08:** Stub created from daily context synthesis - C@C refund bug documented
