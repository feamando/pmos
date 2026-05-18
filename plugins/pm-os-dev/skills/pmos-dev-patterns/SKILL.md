---
description: When working on PM-OS platform code — plugins, tools, commands, pipelines — apply PM-OS development patterns for consistency and correctness
---

## When to Apply

- User is editing or creating files under `v5/plugins/`
- User is working on PM-OS tools, commands, or pipelines
- User mentions PM-OS architecture, plugin structure, or porting from v4.x
- Code review of PM-OS contributions

## Development Patterns

### Architecture
- **LOGIC in v5/plugins/**, CONTENT in user/ — never mix
- **Config-driven**: Zero hardcoded values — no usernames, org names, repo paths, channel IDs
- **Plugin isolation**: Each plugin owns its tools, commands, skills, and preflight checks
- **Cross-plugin imports**: NEVER import directly between plugins. Use `plugin_deps` + MCP

### Import Pattern
All cross-package imports use try/except fallback:
```python
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths
```

### Auth Pattern
Three-tier connector_bridge:
```python
try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    from core.connector_bridge import get_auth
# Always handle auth failure gracefully
```

### Namespace Rules
- `core/` reserved for Base plugin only
- `util/` used by Base and CCE — other plugins use `{domain}_util/` or `dev_util/`
- Every `__init__.py` uses try/except imports

### Testing
- Test files: `tests/test_{module}.py`
- Patch module objects, not package paths
- Include template/rule-based fallbacks for LLM-dependent features
- Always test with PYTHONPATH pointing to plugin's `tools/` directory

### Pipeline Extensions
- Boot steps: `pipelines/boot-extension.yaml`
- Logout steps: `pipelines/logout-extension.yaml`
- Always use `on_error: skip` for extension steps
