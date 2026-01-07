# Coding Conventions

*Populate this file by running `/sync-tech-context` or manually documenting your team's patterns*

## File Organization

### Directory Structure
```
src/
├── features/         # Feature modules
├── components/       # Shared components
├── hooks/           # Custom hooks
├── stores/          # State stores
└── utils/           # Utility functions
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `UserProfile.tsx` |
| Hooks | camelCase, use prefix | `useUserData.ts` |
| Utils | camelCase | `formatDate.ts` |
| Types | PascalCase | `UserProfileProps` |
| Constants | UPPER_SNAKE | `MAX_RETRY_COUNT` |

## State Management

*Document your team's state management patterns here*

## API Patterns

*Document your API conventions (REST, GraphQL, etc.)*

## Testing

*Document your testing standards*

---

*Run `/sync-tech-context` to import patterns from spec-machine (if available)*
