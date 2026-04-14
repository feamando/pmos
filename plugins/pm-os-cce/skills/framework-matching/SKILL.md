---
description: When the user faces a strategic or analytical question, match and apply the most appropriate PM framework from the framework library
---

# Framework Matching

## When to Apply
- User asks how to approach a problem or decision
- User mentions a framework by name (RICE, MoSCoW, SWOT, etc.)
- User needs to prioritize, evaluate, or structure thinking
- Feature workflow requires structured analysis (e.g., opportunity sizing, prioritization)

## What to Do

### 1. Identify the Problem Type

| Problem Type | Example Frameworks |
|-------------|-------------------|
| **Prioritization** | RICE, MoSCoW, Weighted Scoring, ICE, Value vs Effort |
| **Strategy** | SWOT, Porter's Five Forces, Blue Ocean, Jobs-to-be-Done |
| **Decision** | Decision Matrix, Pros/Cons, Reversibility Test, Cost of Delay |
| **Analysis** | 5 Whys, Fishbone, Pareto, Root Cause Analysis |
| **Planning** | OKRs, SMART Goals, Story Mapping, Impact Mapping |
| **Communication** | Pyramid Principle, STAR, SCQA, Minto |
| **Product** | Kano Model, Product-Market Fit, Value Proposition Canvas |
| **Risk** | Risk Matrix, Pre-mortem, Failure Mode Analysis |

### 2. Match Framework to Context
Consider:
- **Problem complexity** -- Simple problems need simple frameworks
- **Audience** -- Engineering (technical frameworks), leadership (strategic frameworks)
- **Data availability** -- Some frameworks need quantitative data, others work with qualitative
- **Time constraint** -- Quick frameworks for fast decisions, thorough ones for big bets

### 3. Apply the Framework
- Fill in the framework with available data
- Call out assumptions and gaps
- Show the framework output (matrix, score, ranking)
- Explain the recommendation in plain language

### 4. Cross-validate
- Apply a second framework as a sanity check
- Note where frameworks agree (high confidence) and disagree (investigate further)
- Feed framework outputs into FPF reasoning if a decision is needed

## Tools Used
- `tools/reasoning/framework_matcher.py` -- Framework selection and application
- `tools/reasoning/fpf_engine.py` -- Decision integration
- Brain MCP `search_entities` -- Historical decisions and precedents

## Examples

<example>
User: "Help me prioritize these 5 features"
Assistant: [identifies as prioritization problem, suggests RICE for data-driven team, applies RICE scoring with available data, cross-validates with Value vs Effort matrix, presents ranked list with confidence notes]
</example>

<example>
User: "Should we enter the enterprise market?"
Assistant: [identifies as strategy problem, applies Porter's Five Forces for market analysis, supplements with SWOT for internal readiness, produces strategic recommendation with evidence chain]
</example>

<example>
User: "Why are users dropping off at checkout?"
Assistant: [identifies as analysis problem, applies 5 Whys to drill to root cause, uses Fishbone for systematic categorization, produces prioritized list of causes with suggested experiments]
</example>
