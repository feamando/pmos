# Context Engine Installation

## Prerequisites

### Required Components

| Component | Purpose | Required |
|-----------|---------|----------|
| PM-OS Core | Base framework | Yes |
| Brain | Knowledge management | Yes |
| Python 3.10+ | Runtime | Yes |
| PyYAML | State file handling | Yes |

### Optional Integrations

| Integration | Purpose | Configuration |
|-------------|---------|---------------|
| Google Sheets | Master Sheet sync | Google OAuth |
| Jira | Ticket management | JIRA_API_TOKEN |
| Confluence | Document sync | CONFLUENCE_API_TOKEN |
| Slack | Notifications | SLACK_BOT_TOKEN |
| Figma | Design artifact validation | Manual |

## Installation

### 1. Verify PM-OS Installation

```bash
# Check PM-OS is installed
ls $PM_OS_COMMON/tools/context_engine/

# Expected output: feature_engine.py, feature_state.py, etc.
```

### 2. Install Python Dependencies

```bash
pip install pyyaml requests
```

### 3. Configure Products Directory

Create the products hierarchy:

```bash
mkdir -p user/products/{growth-division,consumer,operations}/{meal-kit,tpt,growth-platform}
```

Or let the engine create it automatically when you start your first feature.

### 4. Configure Master Sheet (Optional)

If using Master Sheet integration, set up Google OAuth:

```bash
# Set environment variables
export GOOGLE_CREDENTIALS_PATH=".secrets/credentials.json"
export GOOGLE_TOKEN_PATH=".secrets/token.json"
```

Or add to `user/.env`:

```env
GOOGLE_CREDENTIALS_PATH=.secrets/credentials.json
GOOGLE_TOKEN_PATH=.secrets/token.json
```

### 5. Configure Jira Integration (Optional)

```bash
export JIRA_URL="https://your-company.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_API_TOKEN="your-api-token"
```

## Configuration

### Product Configuration

Edit `user/config.yaml` to define your products:

```yaml
products:
  growth-division:
    meal-kit:
      name: "Meal Kit"
      slug_prefix: "goc"
      jira_project: "MK"
      default_approvers:
        - "Jack Approver"
        - "Dave Manager"
    tpt:
      name: "Brand B"
      slug_prefix: "tpt"
      jira_project: "BB"
    growth-platform:
      name: "Growth Platform"
      slug_prefix: "ff"
      jira_project: "FF"
```

### Quality Gate Thresholds

Customize thresholds per product in `user/config.yaml`:

```yaml
quality_gates:
  default:
    context_draft_threshold: 60
    context_review_threshold: 75
    context_approved_threshold: 85
    figma_required: true
    wireframes_required: false

  products:
    meal-kit:
      context_approved_threshold: 80  # Lower threshold for faster iteration
      required_bc_approvers:
        - "Dave Manager"
```

### Brain Integration

Ensure Brain paths are configured:

```yaml
brain:
  entities_path: "brain/Entities"
  features_prefix: "Feature"
  auto_create_entity: true
```

## Verification

### Test Installation

```bash
# Start a test feature
/start-feature "Test Feature" --product meal-kit

# Check it was created
ls user/products/growth-division/meal-kit/

# Check the status
/check-feature goc-test-feature

# Clean up
rm -rf user/products/growth-division/meal-kit/goc-test-feature/
```

### Verify Brain Integration

```bash
# Check Brain entity was created
ls brain/Entities/ | grep -i "test"
```

### Verify Master Sheet Connection

```bash
# Run a sync test
python3 common/tools/context_engine/master_sheet_reader.py --test
```

## Troubleshooting

### "Product not found"

```
Error: Could not identify product for feature
```

**Solution:** Specify product explicitly:
```bash
/start-feature "Feature Name" --product meal-kit
```

Or configure product detection in config.yaml.

### "Brain entity creation failed"

```
Error: Failed to create Brain entity
```

**Solution:** Verify Brain paths:
```bash
ls $PM_OS_USER/brain/Entities/
# Should exist and be writable
```

### "Google OAuth token expired"

```
Error: Google token expired or invalid
```

**Solution:** Re-authenticate:
```bash
python3 common/tools/google_auth.py
```

### "Missing required approvers"

```
Error: No required approvers configured for product
```

**Solution:** Add approvers to config:
```yaml
products:
  meal-kit:
    default_approvers:
      - "Approver Name"
```

## Upgrading

When upgrading PM-OS, the Context Engine may require migration:

```bash
# Check for migration scripts
ls common/tools/context_engine/migrations/

# Run any pending migrations
python3 common/tools/context_engine/migrations/run_migrations.py
```

## Uninstalling

To disable the Context Engine without removing it:

```yaml
# In user/config.yaml
context_engine:
  enabled: false
```

---

*Next: [Commands](04-commands.md)*
