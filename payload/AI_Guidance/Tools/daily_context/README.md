# Daily Context Updater

This tool fetches recent Google Docs and Gmail messages (excluding promotional emails) to generate a daily context summary for AI agents.

## Prerequisites

- Python 3.8+
- A Google Cloud Project with Drive API and Gmail API enabled.
- `credentials.json` placed in this directory (or configured path).

## Installation

1.  Run the installation script to set up the Python virtual environment and install dependencies:

    ```powershell
    .\install.ps1
    ```

    Or manually:

    ```bash
    python -m venv venv
    .\venv\Scripts\Activate
    pip install -r requirements.txt
    ```

2.  Place your `credentials.json` file in this directory.

## Usage

**Basic Run (Updates since last run):**

```powershell
python daily_context_updater.py
```

**First Run (Fetches last 10 days):**

```powershell
python daily_context_updater.py
```

**Force specific days lookback:**

```powershell
python daily_context_updater.py --force --days 5
```

**Dry Run (List items without fetching content):**

```powershell
python daily_context_updater.py --dry-run
```

**Output to file:**

```powershell
python daily_context_updater.py --output context.md
```

## Output

The script generates a raw text report containing:
- Index of modified Documents and Emails.
- Full content of documents.
- Full text content of emails (promotional emails are filtered out).
- Instructions for an AI agent to synthesize the raw data.
