# Preflight Check

Run pre-flight verification on developer tools.

## Instructions

### Step 1: Run Preflight

For quick check (imports only):

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/preflight/preflight_runner.py" --quick
```

For full check:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/preflight/preflight_runner.py"
```

### Step 2: List Tools

To see all available tools:

```bash
python3 "$PM_OS_DEVELOPER_ROOT/tools/preflight/preflight_runner.py" --list
```

### Step 3: Report Results

Report:
- Total tools checked
- Pass/fail count
- Any errors or warnings
- Overall status (READY / FAILED)

## Arguments

- `--quick`: Import tests only (faster)
- `--list`: List all tools without checking
- `--category NAME`: Check specific category only
- `--verbose`: Show progress during check

## Categories

- **core**: Path resolver, config loader
- **session**: Session manager, Confucius
- **ralph**: Ralph manager
- **quint**: Evidence decay monitor
