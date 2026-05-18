---
description: Generate a standalone interactive HTML wireframe for early concept exploration of a product feature
---

# Wireframe

Generate a standalone interactive HTML wireframe for a product feature or concept. Use for early-stage concept exploration before or independent of the spec pipeline.

## When to Apply

- User wants a quick visual of a feature idea or concept
- User says "wireframe this", "show me what this looks like", or "mock this up"
- User wants to explore a concept visually before committing to a full spec
- User wants to compare current vs proposed UX side by side

## Input Types

- **Feature description:** "Show pre-search suggestions on the search screen"
- **Concept for a brief:** "Rough visual of personalized widget placement"
- **Comparison:** "Current vs proposed search experience"
- **Solution path:** "Path A: client-side trending recipes"

If no specific input is provided, ask: "What should this wireframe show? Describe the feature, screen, or concept."

## What to Do

### Design System

Use **Zest design tokens** (HelloFresh design system):

```
/* Colors */
--zest-green: #6B9E1F;
--zest-green-dark: #4A7A0B;
--zest-orange: #F47B20;
--zest-white: #FFFFFF;
--zest-grey-100: #F5F5F5;
--zest-grey-200: #E8E8E8;
--zest-grey-400: #BDBDBD;
--zest-grey-600: #757575;
--zest-grey-900: #212121;
--zest-red: #D32F2F;
--zest-blue: #1976D2;

/* Typography */
font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
/* Heading: 600 weight, Body: 400 weight */

/* Spacing */
--space-xs: 4px;
--space-sm: 8px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;

/* Border radius */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 16px;
--radius-full: 9999px;
```

### Layout Rules

- **App features (default):** Mobile-first. Render inside a 393x812 phone frame centered on page with device chrome (status bar, home indicator).
- **Web features:** If explicitly stated as web, use responsive desktop layout (max-width 1200px centered).
- **Backend/ML features:** Show outcome comparisons — current UX vs proposed UX side by side. Do NOT show architecture diagrams. Show what the USER sees differently.

### User Scenario Coverage

**MANDATORY:** Every wireframe must address all quadrants of the user scenario matrix:

| | Profile filled | No profile (0%) |
|---|---|---|
| **Warm-start** (returning user, has history) | Best case — full personalization | History-based only |
| **Cold-start** (new user, no history) | Profile-based only | Worst case — generic fallback |

Implementation options:
- **Tabs/toggle** at the top to switch between scenarios
- **Swipeable cards** showing each quadrant
- **Side-by-side** if space allows

The wireframe must make it clear what the user sees in EACH scenario. Don't just show the happy path.

### Interactivity

Make the wireframe interactive where it adds understanding:
- Tap/click states on buttons and cards
- Search input that filters/shows results
- Toggle between states (before/after, scenarios)
- Scroll behavior if relevant
- Transitions/animations where they clarify the UX (subtle, not decorative)

Use vanilla JS only. No external dependencies. Everything in one HTML file.

### Content

- Use realistic HelloFresh content (recipe names, meal images as colored placeholders with meal names, realistic prices)
- Include realistic UI elements (navigation bars, tab bars, status bars)
- If showing search: use real search terms a HelloFresh customer would use ("quick chicken", "vegetarian", "under 30 min")

### Output

1. Generate the HTML file
2. Report: what scenarios are covered, what interactions are available, any limitations
3. Save to current directory as `wireframe-<feature-name>.html`

### Quality Checks

Before delivering:
- [ ] All 4 user scenario quadrants addressed (or explicitly justified why fewer apply)
- [ ] Phone frame renders correctly at 393x812
- [ ] No external dependencies (fonts, images, scripts)
- [ ] Interactive elements work (test mentally: tap, scroll, toggle)
- [ ] Realistic content, not lorem ipsum
- [ ] Zest design tokens used consistently

## Rules

- Mobile-first unless explicitly told otherwise
- Show outcomes, not architecture
- Cover all user scenarios — the cold-start empty state is as important as the happy path
- Keep it simple enough to open in any browser with zero setup
- If the wireframe is for a backend/ML feature, think: "What changes on screen for the customer?" That's what you show.
- This is a standalone exploration tool — it does not require running /spec-brief first
