# PRD Generator

Generate or update a PRD using Deep Research.

## Arguments
$ARGUMENTS

## Instructions

The user wants to generate or update a PRD. Parse their request:

### For New PRD Creation
If the user provides a topic (e.g., "Add dark mode to TPT", "OTP for Good Chop"):

1. Run the PRD generator:
   ```bash
   python3 AI_Guidance/Tools/deep_research/prd_generator.py --topic "$ARGUMENTS"
   ```

2. Wait for generation to complete (may take 2-5 minutes)

3. Report the output file location and offer to review the generated PRD

### For PRD Updates
If the user provides a file path and update instructions (e.g., "Products/TPT/PRD.md --update Add competitor analysis"):

1. Parse the file path and instructions from the arguments
2. Run:
   ```bash
   python3 AI_Guidance/Tools/deep_research/prd_generator.py --update <filepath> --instructions "<instructions>"
   ```

3. Report the updated file

### First-Time Setup
If this is the first time using the PRD generator, run setup first:
```bash
python3 AI_Guidance/Tools/deep_research/prd_generator.py --setup
```

This indexes your local documents for Deep Research.

## Examples

- `/prd Add push notifications to TPT mobile app`
- `/prd OTP checkout flow for Good Chop`
- `/prd Products/Good_Chop/OTP_PRD.md --update Add competitive analysis section`

## Notes

- Generation uses Google Deep Research API and may take 2-5 minutes
- PRDs are saved to Products/ directory by default
- The tool researches both internal docs and web sources
- If Deep Research fails, it falls back to standard Gemini generation
