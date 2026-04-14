---
description: Provide meeting preparation context and post-meeting note capture assistance
---

# Meeting Intelligence

## When to Apply
- When the user mentions an upcoming meeting or calendar event
- When the user asks about a person who is a meeting participant
- When the user shares meeting notes or asks to capture decisions from a meeting
- When the user asks "what should I prepare for" or references a specific meeting

## What to Do
- **Pre-meeting:** Check if meeting prep exists in `user/planning/Meeting_Prep/`. If Brain plugin is installed, enrich participant context with entity data (roles, projects, relationships).
- **Participant context:** When a meeting participant is mentioned, check Brain for their entity — surface relevant projects, recent decisions, and relationship to the user's work.
- **Post-meeting:** After a meeting discussion, offer to capture key decisions, action items, and blockers via Confucius notes.
- **Series intelligence:** For recurring meetings, reference previous meeting outcomes, open commitments, and recurring topics.

## Examples
<example>
User: "I have a 1:1 with my report Alice tomorrow"
Assistant: [checks Brain for Alice entity, surfaces her current projects and any open action items from previous 1:1s]
</example>

<example>
User: "We just finished the sprint review, here are the notes..."
Assistant: [offers to capture decisions and action items, suggests Confucius note session]
</example>
