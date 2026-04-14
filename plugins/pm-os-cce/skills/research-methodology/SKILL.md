---
description: When the user asks for research, analysis, or investigation on a topic, apply multi-angle research methodology with deep research swarm coordination
---

# Research Methodology

## When to Apply
- User asks to research a topic, market, competitor, or technology
- User needs evidence to support a decision or hypothesis
- User requests a deep dive or investigation
- Feature workflow enters Discovery phase and needs research

## What to Do

### 1. Frame the Research Question
- Clarify the core question and scope
- Identify what a good answer looks like (acceptance criteria)
- Determine time/depth constraints

### 2. Multi-Angle Approach
Attack the question from at least 3 orthogonal angles:

| Angle | Method | Example |
|-------|--------|---------|
| **Data-driven** | Quantitative analysis, metrics, benchmarks | Market size, conversion rates, usage data |
| **Stakeholder** | User research, interviews, feedback analysis | Pain points, feature requests, satisfaction |
| **Competitive** | Competitor analysis, market positioning | Feature comparison, pricing, differentiation |
| **Technical** | Architecture review, feasibility assessment | Performance, scalability, integration complexity |
| **Strategic** | Business model, market trends, positioning | TAM/SAM/SOM, growth vectors, moats |

### 3. Evidence Collection
For each finding:
- Assign confidence level (CL1-CL4)
- Record source and date
- Note any biases or limitations
- Tag as supporting, counter, or neutral

### 4. Synthesis
- Cross-reference findings across angles
- Identify convergence (multiple angles agree) and divergence (angles conflict)
- Produce a ranked findings list with confidence levels
- Highlight gaps and suggested follow-up research

### 5. Integration with FPF
Feed research findings into the FPF reasoning engine:
- Each finding becomes evidence via `/reason add`
- Conflicting findings generate hypotheses via `/reason hypothesize`
- Overall confidence informs decision readiness

## Tools Used
- `tools/research/deep_research_swarm.py` -- Multi-source research coordination
- `tools/reasoning/fpf_engine.py` -- Evidence registration and reasoning
- `tools/reasoning/orthogonal_challenge.py` -- Bias and gap detection
- Brain MCP `search_entities` -- Existing organizational knowledge

## Examples

<example>
User: "Research whether we should build or buy an analytics platform"
Assistant: [frames as build-vs-buy decision, researches from cost angle (TCO analysis), capability angle (feature gaps), strategic angle (core competency), and risk angle (vendor lock-in vs maintenance burden), synthesizes with CL levels]
</example>

<example>
User: "Deep dive into competitor X's pricing strategy"
Assistant: [researches from pricing model angle, customer segment angle, market positioning angle, and historical trend angle, produces competitive intelligence summary with evidence chain]
</example>
