Run the daily context updater to pull recent Google Docs and synthesize into a context file.

## Steps:
1. Execute the daily context updater script:
   ```bash
   python3 AI_Guidance/Tools/daily_context/daily_context_updater.py
   ```

2. Analyze the raw document output

3. Synthesize key information into `AI_Guidance/Core_Context/YYYY-MM-DD-context.md` following NGO format:
   - Documents processed (table with links)
   - Key decisions (bulleted, by project/workstream)
   - Action items (checkbox format)
   - Blockers & risks
   - Key dates & milestones
   - Metrics to track
   - Brief document summaries

## Options:
- Use `--dry-run` to preview which docs would be fetched
- Use `--force --days N` to override last-run and pull last N days
