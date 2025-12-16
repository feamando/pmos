# Architecture

Technical systems, data flows, and platform documentation.

## File Naming
- Systems: `System_Name.md` (e.g., `Wallet.md`, `OWL.md`)
- Flows: `Flow_Name.md` (e.g., `Billing_Flow.md`)

## Template

```markdown
---
id: arch-system-name
type: system | flow | integration
status: active | deprecated | planned
last_updated: YYYY-MM-DD
---

# System Name

## Overview
Brief description of what this system does.

## Key Components
*   Component 1
*   Component 2

## Dependencies
*   Upstream: [Systems that feed into this]
*   Downstream: [Systems that depend on this]

## API / Integration Points
*   Endpoint or integration description

## Diagram
\`\`\`mermaid
graph LR
    A[Input] --> B[System] --> C[Output]
\`\`\`

## Known Issues / Tech Debt
*   Issue 1

## Changelog
- **YYYY-MM-DD:** Entry
```

## Current Systems

*None yet. Files will be created as systems are referenced in context.*
