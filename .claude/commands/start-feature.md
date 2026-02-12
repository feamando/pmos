# Start Feature

Initialize a new feature for the Context Creation Engine workflow.

## Overview

This command is the entry point for the Context Creation Engine. It:
1. Identifies the target product
2. Checks for existing features (alias detection)
3. Creates the feature folder structure
4. Creates a Brain entity
5. Initializes the feature state

## Arguments

- `<title>` - Feature title (required)
- `--product <id>` - Product ID or name (optional, will prompt if ambiguous)
- `--from-insight <id>` - Link to an existing insight (optional)
- `--priority <level>` - P0, P1, P2 (default: P2)

**Examples:**
```
/start-feature "OTP Checkout Recovery"
/start-feature "Improve Login Flow" --product meal-kit
/start-feature "Push Notifications" --product tpt --priority P1
```

## Instructions

### Step 1: Parse Arguments

Extract the feature title and optional flags from the user's command.

```python
# Example parsing
title = "OTP Checkout Recovery"  # Required
product_id = None  # Optional, from --product flag
from_insight = None  # Optional
priority = "P2"  # Default
```

### Step 2: Product Identification

Use the ProductIdentifier to determine the target product.

```python
import sys
sys.path.insert(0, "$PM_OS_COMMON/tools")
from context_engine import ProductIdentifier, IdentificationSource

identifier = ProductIdentifier()
result = identifier.identify_product(
    explicit_product=product_id,  # From --product flag if provided
    feature_title=title,
    from_insight=from_insight
)

if result.needs_user_selection:
    # Show product selection to user
    print(identifier.format_product_selection(result.candidates))
    # Wait for user to select
```

**Priority Order (PRD C.6):**
1. Explicit `--product` flag
2. Master Sheet lookup (if feature title exists)
3. Recent daily context
4. Slack channel inference
5. User selection from config.yaml products

### Step 3: Alias Detection

Check if a similar feature already exists using fuzzy matching.

```python
from context_engine import AliasManager, MatchType

alias_mgr = AliasManager()
match = alias_mgr.find_existing_feature(title, result.product.id)

if match.match_type == MatchType.HIGH_CONFIDENCE:
    # Auto-consolidate (>90% similarity)
    print(f"Linked to existing feature: {match.existing_name}")
    print(f"Added '{title}' as alias")
    # Update existing feature with new alias

elif match.match_type == MatchType.NEEDS_CONFIRMATION:
    # Ask user (70-90% similarity)
    print(f"Potential duplicate detected:")
    print(f"  Existing: '{match.existing_name}' ({match.similarity:.0%} match)")
    print(f"  New: '{title}'")
    print()
    print("Is this the same feature?")
    print("  1. Yes, link to existing")
    print("  2. No, create as new feature")
    # Wait for user response

elif match.match_type == MatchType.NO_MATCH:
    # Proceed with new feature creation
    pass
```

### Step 4: Create Feature

If creating a new feature (not linked to existing):

```python
from context_engine import FeatureEngine

engine = FeatureEngine()
init_result = engine.start_feature(
    title=title,
    product_id=result.product.id,
    priority=priority,
    from_insight=from_insight
)

if init_result.success:
    print(f"Feature created successfully!")
    print(f"  Folder: {init_result.feature_path}")
    print(f"  Context: {init_result.context_file}")
    print(f"  Brain: {init_result.brain_entity}")
else:
    print(f"Error: {init_result.error}")
```

### Step 5: Master Sheet Guidance

Remind user to update Master Sheet (write integration pending):

```
Note: Please add this feature to the Master Sheet:
  Spreadsheet: https://docs.google.com/spreadsheets/d/DOC_ID_EXAMPLE
  Tab: topics
  Row: Feature="{title}", Product="{product_code}", Status="To Do", Priority="{priority}"
```

### Step 6: Report Results

Display initialization summary:

```
┌─────────────────────────────────────────────────────────────┐
│ FEATURE INITIALIZED                                          │
├─────────────────────────────────────────────────────────────┤
│ Title: OTP Checkout Recovery                                 │
│ Product: Meal Kit (MK)                                     │
│ Priority: P2                                                 │
│                                                              │
│ Created:                                                     │
│   Folder: user/products/growth-division/meal-kit/mk-feature-recovery/
│   Context: mk-feature-recovery-context.md                       │
│   State: feature-state.yaml                                  │
│   Brain: Entities/Goc_Otp_Recovery.md                        │
│                                                              │
│ Next Steps:                                                  │
│   1. Add to Master Sheet (see above)                         │
│   2. Run /analyze-signals to gather insights                 │
│   3. Or /create-context-doc to start context document        │
└─────────────────────────────────────────────────────────────┘
```

## Error Handling

| Error | Resolution |
|-------|------------|
| Product not found | Show available products, ask user to select |
| Folder already exists | Offer to resume existing or create with suffix |
| Permission denied | Check folder permissions |
| Config not loaded | Ensure user/config.yaml exists |

## Integration Points

- **ProductIdentifier**: `common/tools/context_engine/product_identifier.py`
- **AliasManager**: `common/tools/context_engine/alias_manager.py`
- **FeatureEngine**: `common/tools/context_engine/feature_engine.py`
- **Config**: `user/config.yaml` (products.items[], master_sheet)

## Execute

Parse the arguments, run product identification, check for aliases, create the feature folder and Brain entity, then report results with next steps.
