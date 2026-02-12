# Orthogonal Challenge Status

Check status of ongoing or completed orthogonal challenges.

## Arguments
$ARGUMENTS

## Instructions

The user wants to check the status of orthogonal challenges. Parse their request:

### List All Challenges

If no arguments provided or `--list`:

```bash
python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --status
```

This will show all challenges with their status:
- `round1_in_progress` - Originator is creating v1
- `round2_in_progress` - Challenger is reviewing
- `round3_in_progress` - Resolver is finalizing
- `complete` - All rounds finished
- `*_failed` - Error occurred at that round

### View Specific Challenge

If a challenge ID is provided:

1. Load challenge state:
   ```bash
   cat $PM_OS_USER/brain/Reasoning/Orthogonal/$ARGUMENTS/state.json
   ```

2. Show key information:
   - Document type
   - Topic
   - Current status
   - Timestamps for each round
   - Output file paths

### Resume Failed Challenge

If `--resume <challenge_id>` is provided:

```bash
python3 "$PM_OS_COMMON/tools/quint/orthogonal_challenge.py" --resume $ARGUMENTS
```

This will:
- Detect which round failed
- Resume from that point
- Continue through remaining rounds

### View Challenge Artifacts

For a complete challenge, show paths to:
- **v1.md:** Original document from Round 1
- **v2.md:** Challenger's critique from Round 2
- **v3_final.md:** Final resolved document
- **challenge_faq.md:** FAQ from challenge process
- **drr.md:** Design Rationale Record

## Examples

- `/orthogonal-status` - List all challenges
- `/orthogonal-status prd-2026-01-05-push_notifications` - View specific challenge
- `/orthogonal-status --resume prd-2026-01-05-push_notifications` - Resume failed challenge

## Output Format

```
Orthogonal Challenges:

  [complete] prd-2026-01-05-push_notifications
    Topic: Push notifications for WB app
    Type: PRD
    Completed: 2026-01-05T14:30:00

  [round2_in_progress] adr-2026-01-05-microservices
    Topic: Migrate to microservices architecture
    Type: ADR
    Last Updated: 2026-01-05T15:00:00
```

## Notes

- Challenges are stored in `Brain/Reasoning/Orthogonal/`
- Each challenge has a unique ID based on type, date, and topic
- Failed challenges can be resumed from the last successful round
- Completed challenges include DRR in `Brain/Reasoning/Decisions/`
