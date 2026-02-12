# Context Creation Engine Documentation

The Context Creation Engine is PM-OS's complete workflow for managing features from inception to launch. It tracks progress across four parallel tracks—Context, Design, Business Case, and Engineering—with quality gates at each phase.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Overview](01-overview.md) | What the Context Engine is and why it matters |
| [Architecture](02-architecture.md) | Technical architecture and component design |
| [Installation](03-installation.md) | Setup, configuration, and prerequisites |
| [Commands](04-commands.md) | All Feature Lifecycle commands reference |
| [Quality Gates](05-quality-gates.md) | Quality gate thresholds and validation rules |
| [Parallel Tracks](06-tracks.md) | Context, Design, Business Case, Engineering tracks |
| [Workflow Guide](07-workflow.md) | Step-by-step workflow from feature start to launch |

## Quick Start

```bash
# 1. Start a new feature
/start-feature "OTP Checkout Recovery" --product meal-kit

# 2. Check progress anytime
/check-feature mk-feature-recovery

# 3. Attach artifacts as they're ready
/attach-artifact figma https://figma.com/file/abc123

# 4. Validate before decision gate
/validate-feature

# 5. Request go/no-go decision
/decision-gate --approve

# 6. Generate deliverables
/generate-outputs
```

## Key Concepts

### Four Parallel Tracks

Work progresses independently across four tracks:

1. **Context Track** - Problem definition, stakeholders, success metrics
2. **Design Track** - Wireframes, Figma designs, UX specifications
3. **Business Case Track** - ROI analysis, metrics, stakeholder approvals
4. **Engineering Track** - ADRs, estimates, dependencies, risks

### Quality Gates

Each track has quality gates that must pass before advancing:

- **Context**: Document exists → Orthogonal challenge → 85%+ score
- **Design**: Spec present → Wireframes → Figma attached
- **Business Case**: Metrics defined → ROI analysis → Approvals obtained
- **Engineering**: Components identified → ADRs decided → Estimate provided

### Feature Lifecycle Phases

```
INITIALIZATION → SIGNAL_ANALYSIS → CONTEXT_DOC → PARALLEL_TRACKS → DECISION_GATE → OUTPUT_GENERATION → COMPLETE
```

## Integration Points

The Context Engine integrates with:

- **Brain** - Entities created and updated automatically
- **Master Sheet** - Priority and deadline tracking
- **Jira** - Ticket creation and linking
- **Confluence** - Document sync
- **Spec Machine** - Export for implementation
- **Orthogonal Challenge** - Context document validation

---

*Part of PM-OS v3.2.1*
