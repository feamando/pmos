# Ralph Iteration Prompt: {{feature}}

## Context Training
Read these files to understand the codebase:
- {{brain_context_path}}
- AI_Guidance/Rules/NGO.md
- AI_Guidance/Core_Context/ (latest context file)

## Your Task
You are working on: **{{title}}**

Feature directory: `AI_Guidance/Sessions/Ralph/{{feature}}/`

## Instructions

1. **Orient yourself**
   - Run `pwd` to confirm working directory
   - Read `PLAN.md` in the feature directory to see progress
   - Find the FIRST unchecked `- [ ]` item

2. **Work on ONE item only**
   - Focus entirely on completing that single acceptance criterion
   - Do not skip ahead or work on multiple items
   - Take the time needed to do it properly

3. **After completing work**
   - Test/verify the work is actually complete
   - Commit to git with descriptive message
   - Mark the item as `- [x]` in PLAN.md
   - Update the progress line at the bottom of PLAN.md

4. **If ALL items complete**
   - Add `## COMPLETED` marker at the end of PLAN.md
   - Write final summary in the last iteration log

5. **Leave clean state**
   - No half-implemented features
   - No broken tests
   - Clear git history

## Constraints

- Do NOT remove or modify existing acceptance criteria text
- Do NOT mark items complete without actual verification
- Do NOT work on multiple items in one iteration
- Do NOT declare completion prematurely

## Iteration Logging

After each iteration, the loop will automatically log your work to:
`logs/iteration-NNN.md`

Include in your final message:
- Summary of what was completed
- Files created/modified
- Any blockers encountered
