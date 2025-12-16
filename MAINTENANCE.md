# PM-OS Maintenance Guide

## Routine Tasks

### Weekly
- **Audit Brain Relationships:** Run `python AI_Guidance/Tools/synapse_builder.py` to ensure all bi-directional links are consistent.
- **Archive Old Context:** Move old `YYYY-MM-DD-context.md` files to `AI_Guidance/Core_Context/Archive/` if the folder gets cluttered.
- **Update Registry:** Check `AI_Guidance/Brain/registry.yaml` against new hires or project launches.

### Monthly
- **Refresh Technical Context:** Run `python AI_Guidance/Tools/github_brain_sync.py --update-projects` to pull fresh READMEs from GitHub into Brain Project files.
- **Deep Clean Inbox:** Delete processed files in `AI_Guidance/Brain/Inbox/Archive/` older than 30 days.
- **Token Rotation:** Rotate Google/Jira/GitHub tokens if expiring.

## Troubleshooting

### Context Update Fails
- Check `.gemini/tmp/` for raw data dumps.
- Verify `GEMINI_API_KEY` in `.env`.
- Ensure `credentials.json` (Google OAuth) is valid in `.secrets/`.

### Brain Links Broken
- Run `synapse_builder.py`.
- Check for typo in `registry.yaml` or filename mismatches.

### GitHub Sync Errors
- Verify `GITHUB_TOKEN` has repo read permissions.
- Ensure `gh` CLI is installed and authenticated if running locally without token.

## Adding New Features
1. Create tool in `AI_Guidance/Tools/`.
2. Add configuration to `.env`.
3. Update `update-context.ps1` to include the tool in the daily loop.
4. Document in `README.md`.