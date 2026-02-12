# Parse Roadmap Inbox

Process NEW items from the temp roadmap inbox through LLM enrichment.

## Arguments
$ARGUMENTS

## Instructions

This command parses raw Slack mentions from the temp inbox into structured roadmap items.

### Steps

1. **Load NEW items from temp inbox:**

```python
import sys
sys.path.insert(0, "$PM_OS_DEVELOPER_ROOT/tools")

from roadmap import RoadmapInboxManager, RoadmapParser

manager = RoadmapInboxManager()
parser = RoadmapParser(model="gemini")  # or "claude"

# Get NEW temp items
temp_items = manager.get_temp_items(status="NEW")
print(f"Found {len(temp_items)} NEW items to parse")
```

2. **Parse each item through LLM:**

The parser will:
- Extract a clear, actionable title
- Generate a comprehensive description
- Create 2-5 measurable acceptance criteria
- Assign priority (P0-P3) based on context
- Categorize as feature or bug
- Check for duplicates against existing items

3. **Run the parser:**

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/roadmap/roadmap_parser.py" --parse --model gemini
```

4. **Review results:**

After parsing:
- Temp items are marked as PARSED
- New items appear in pm-os-roadmap-inbox.md
- Slack thread replies are posted: "parsed, inbox item id ri-XXXX"

### Options

- `--model gemini` - Use Gemini for parsing (default, faster)
- `--model claude` - Use Claude for parsing (more detailed)
- `--no-duplicates` - Skip duplicate checking
- `--dry-run` - Preview without saving

### Output

For each parsed item, display:
- Roadmap ID (ri-XXXX)
- Title
- Priority
- Category (feature/bug)
- Acceptance criteria count

### After Parsing

Next steps for the user:
1. Review parsed items: `/list-roadmap-inbox`
2. Create Beads items: `/bd-create-task-roadmap-ri-XXXX`
3. Or post to Slack: `/list-roadmap-inbox --slack`

### Example Output

```
Parsing 5 NEW items...

ri-a1b2: Add OAuth2 login flow
  Priority: P1, Category: feature
  ACs: 3

ri-c3d4: Fix validation error on mobile
  Priority: P2, Category: bug
  ACs: 2

ri-e5f6: Improve dashboard loading performance
  Priority: P2, Category: feature
  ACs: 4

Parsed 3 items (2 duplicates merged)
```
