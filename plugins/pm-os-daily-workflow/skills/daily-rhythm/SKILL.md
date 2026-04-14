---
description: Guide the user's daily PM workflow — morning boot, meeting prep, end-of-day save
---

# Daily Rhythm

## When to Apply
- When the user starts a new conversation (suggest boot if not already done)
- When the user mentions an upcoming meeting (offer prep)
- When the user appears to be wrapping up work (suggest session save or logout)
- When the user asks "what should I focus on" or "what's on my plate"

## What to Do
- **Morning:** If no context file exists for today, suggest running `/session boot`
- **Before meetings:** If user mentions a meeting soon, offer to run meeting prep or check if prep already exists
- **End of day:** If user mentions wrapping up, suggest `/session save` to persist context, then `/session logout`
- **Focus questions:** Read today's context file (`user/personal/context/YYYY-MM-DD-context.md`) for priorities, blockers, and action items

## Examples
<example>
User: "Good morning, let's get started"
Assistant: [checks if today's context exists, suggests /session boot if not]
</example>

<example>
User: "I have a meeting with the team in 30 minutes"
Assistant: [checks for existing meeting prep, offers to generate one if missing]
</example>

<example>
User: "I think I'm done for today"
Assistant: [suggests /session save to capture decisions and progress, then /session logout]
</example>
