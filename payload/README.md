# PM-OS: The AI-Native Product Operating System

**A Git-backed, CLI-managed, AI-integrated replacement for Google Drive, Notion, and Jira UIs.**

This system treats Product Management as a codebase. It leverages text-based files (Markdown/YAML), version control (Git), and autonomous agents to manage context, documentation, planning, and execution workflows.

---

## 1. System Architecture

The OS is composed of four distinct layers that flow data from external chaos into structured knowledge and action.

```mermaid
graph TD
    External[External World: GDrive, Jira, Calendar, Email] --> Ingestion[Ingestion Layer: MCPs & Scripts]
    Ingestion --> Raw[Raw Data / Temp Storage]
    Raw --> Synthesis[Synthesis Layer: Agents & Logic]
    
    subgraph "Knowledge Core (The Brain)"
        Daily[Daily Context (Short-Term)]
        Brain[The Brain (Long-Term Semantic Graph)]
        Registry[Entity Registry]
    end
    
    Synthesis --> Daily
    Daily --> Brain
    
    subgraph "Execution Layer"
        Prep[Meeting Prep System]
        Docs[Documentation Engine]
        Ops[Operations & Planning]
    end
    
    Brain --> Prep
    Daily --> Prep
    Brain --> Docs
    
    Prep --> Output[Artifacts: Pre-reads, Specs, Plans]
    Output --> Sync[Sync Layer: Git Push, GDrive Upload]
```

---

## 2. Core Operational Documentation

The system relies on a set of foundational Markdown files that define the agent's identity, capabilities, and operating rules. These are the first files loaded into context during the boot process.

| File | Purpose | Key Content |
| :--- | :--- | :--- |
| **`AGENT.md`** | **Mission Control** | High-level goals, prioritized mandates, directory map, and "first step" instructions. The entry point for any agent. |
| **`AGENT_HOW_TO.md`** | **Operator's Manual** | Technical documentation on using the CLI tools (`read_docx.py`, `gdrive_mcp`), repository architecture, and detailed workflows for document creation/ingestion. |
| **`AI_Guidance/Rules/YOURNAME.md`** | **Persona & Style** | Defines the "First Name, Last Name" persona: tone (Direct, Functional), decision-making frameworks, writing style (bullets > prose), and anti-patterns. |
| **`AI_Guidance/Rules/AI_AGENTS_GUIDE.md`** | **Behavioral Safety** | Meta-rules for agent reasoning: planning principles, safety checks, and loop prevention. |

---

## 3. Core Subsystems

### A. The Brain (Long-Term Memory)
**Location:** `AI_Guidance/Brain/`
**Intent:** To maintain a persistent, semantic graph of the organization (People, Projects, Architecture) that AI agents can traverse.

*   **Registry (`registry.yaml`):** The central nervous system. Maps semantic aliases (e.g., "Deo", "OTP") to specific Markdown files.
*   **Structure:**
    *   `Entities/`: People and Teams.
    *   `Projects/`: Initiatives and Features.
    *   **Architecture/**: Technical systems and domains.
*   **Workflow:**
    *   `brain_loader.py`: Scans daily context for "Hot Topics" defined in the registry and loads them into the agent's active context window.
    *   `brain_updater.py`: Appends new knowledge (changelogs) to Brain files based on daily activities.

### B. The Pulse (Daily Context Loop)
**Location:** `AI_Guidance/Core_Context/`
**Intent:** To capture the "now." It turns the firehose of emails, Slack, and Docs into a structured daily briefing.

*   **Ingestion:** `daily_context_updater.py` fetches changes from GDocs and Gmail (last 24h).
*   **Synthesis:** `update-context.ps1` uses the AI agent to summarize raw data into `YYYY-MM-DD-context.md`.
*   **Format:** The "NGO" style (Direct, Bulleted, Metric-heavy).
*   **Retention:** Acts as short-term memory. Critical items are promoted to **The Brain**.

### C. The Engine (Meeting Prep System)
**Location:** `Planning/Meeting_Prep/`
**Intent:** To ensure the PM is never unprepared. Automates the "pre-read" creation process.

*   **Logic:** `meeting_prep.py` (MeetingManager class).
*   **Workflow:**
    1.  **Fetch:** Grabs Calendar events (Next 24h).
    2.  **Classify:** Determines type (1:1, Team Sync, AdHoc).
    3.  **Context Loop:**
        *   Checks **The Brain** for participant/topic background.
        *   Checks **Daily Context** for recent updates.
        *   Checks **GDrive** for *past meeting notes* (via strict title search).
    4.  **Synthesize:** Generates a tailored Markdown pre-read.
    5.  **Distribute:**
        *   Saves locally (Series vs AdHoc folders).
        *   Uploads to GDrive ("Meeting Pre-Reads" folder).
        *   Links the GDrive doc back to the Calendar Event description.

### D. The Bridge (MCP Tools)
**Location:** `AI_Guidance/Tools/`
**Intent:** To provide programmatic access to external APIs.

*   **`gdrive_mcp`:** Read/Write/Search Google Drive.
*   **`jira_mcp`:** JQL Search, Ticket details.
*   **`web_fetch`:** (Native Agent Tool) Browsing.

---

## 4. Directory Structure (The Filesystem)

```text
/
├── AI_Guidance/            # The Operating System Kernel
│   ├── Rules/              # Behavioral Instructions (NGO.md, AGENT.md)
│   ├── Brain/              # Knowledge Graph (Entities, Projects)
│   ├── Core_Context/       # Daily Status Files (The Pulse)
│   ├── Tools/              # Python Scripts & MCP Servers
│   └── Frameworks/         # Templates (PRDs, Decision Logs)
├── Products/               # Product Documentation (Specs, Roadmaps)
├── Team/                   # People Management (1:1s, Feedback)
├── Planning/               # Strategic Planning
│   └── Meeting_Prep/       # Generated Pre-reads
│       ├── Series/         # Recurring Meeting History
│       └── AdHoc/          # Single-instance Meetings
└── Reporting/              # Outbound Comms (Weekly Updates)
```

---

## 5. Key Workflows

### The Boot Sequence (`boot.ps1`)
The boot script orchestrates the loading of the "Core Operational Documentation" to prime the agent before it begins any work.

*   **When:** Start of every session.
*   **Sequence:**
    1.  **Phase 0: Git Sync:** Pulls latest changes from `origin/main`.
    2.  **Phase 1: Load Core Guidance:** Reads `AGENT.md`, `AGENT_HOW_TO.md`, `NGO.md`, and `AI_AGENTS_GUIDE.md` into the agent's active context window. This establishes the persona, mission, and tool capability immediately.
    3.  **Phase 2: Load Tools:** Ingests documentation for `daily_context`, `gdrive_mcp`, etc.
    4.  **Phase 3: Load Rules:** Reads additional rule files from `AI_Guidance/Rules/`.
    5.  **Phase 4: Update Context:** Executes `update-context.ps1` to fetch/synthesize the last 24h of data.
    6.  **Phase 5: Load Daily Context:** Reads all `Core_Context` files for the day.
    7.  **Phase 6: Final Sync:** Commits any auto-generated files (like new context) and pushes to remote.

### The Work Cycle
1.  **Discovery:** Agent checks `Core_Context` and `Brain` before answering.
2.  **Execution:** Agent uses `Frameworks/` templates to create docs in `Products/`.
3.  **Expansion:** Agent creates new Brain entities if they don't exist.

### The Shutdown Sequence (`logout.ps1`)
*   **When:** End of session.
*   **Actions:**
    1.  Generates Session Summary.
    2.  Appends to today's Context file.
    3.  `git commit` & `git push` (Save state).

---

## 6. Development & Extension

*   **Language:** Python (Scripts/Tools), PowerShell (Orchestration).
*   **Conventions:**
    *   **Files:** `kebab-case.md` for living docs, `YYYY-MM-DD-name.md` for logs.
    *   **Code:** Modular classes (e.g., `MeetingManager`).
    *   **Context:** Front-load context via `boot.ps1` to reduce token usage on repetitive queries.

---

## 7. Setup & Configuration

### Prerequisites

* **Python 3.9+** (Required for MCP tools and scripts)
* **PowerShell 5.1+** (Required for orchestration scripts)
* **Git** (Required for version control operations)
* **Google Cloud Account** (Required for Google Drive and API access)
* **Jira Account** (Required for Jira integration)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-repo/pmos.git
   cd pmos
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### API Configuration (Required)

The system requires API keys for external service integration. **Never commit real API keys to version control.**

#### Google API Setup

1. **Create a Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project

2. **Enable required APIs:**
   - Google Drive API
   - Gmail API
   - Google Calendar API

3. **Create OAuth 2.0 credentials:**
   - Go to "APIs & Services" > "Credentials"
   - Create "OAuth client ID" with type "Desktop app"
   - Download the credentials JSON file

4. **Configure the Meeting Prep tool:**
   - Copy `payload/AI_Guidance/Tools/meeting_prep/config_template.json` to `payload/AI_Guidance/Tools/meeting_prep/config.json`
   - Replace `REPLACE_WITH_YOUR_GOOGLE_API_KEY` with your actual Google API key
   - Set your preferred Gemini model (e.g., `gemini-2.5-flash`)

#### Jira API Setup

1. **Generate a Jira API token:**
   - Go to [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
   - Create a new API token
   - Copy the token immediately (it won't be shown again)

2. **Configure the Jira MCP tool:**
   - Edit `payload/AI_Guidance/Tools/jira_mcp/config.json`
   - Replace `REPLACE_WITH_YOUR_JIRA_API_TOKEN` with your actual Jira API token
   - Update the URL if you're not using `https://hellofresh.atlassian.net/`
   - Update the username if needed

### Environment Variables (Recommended)

For enhanced security, you can use environment variables instead of config files:

```bash
# For Google API
set GOOGLE_API_KEY=your_google_api_key_here

# For Jira API
set JIRA_API_TOKEN=your_jira_api_token_here
```

Or in PowerShell:
```powershell
$env:GOOGLE_API_KEY="your_google_api_key_here"
$env:JIRA_API_TOKEN="your_jira_api_token_here"
```

### First Run Setup

1. **Initialize the system:**
   ```bash
   cd payload
   .\boot.ps1
   ```

2. **Authenticate Google Drive access:**
   - The first run will launch a browser for OAuth authentication
   - Approve the requested permissions
   - The system will save a `token.json` file for future access

3. **Test the tools:**
   ```bash
   # Test Google Drive access
   python AI_Guidance/Tools/gdrive_mcp/server.py --test
   
   # Test Jira access
   python AI_Guidance/Tools/jira_mcp/server.py --test
   ```

### Security Best Practices

1. **Never commit API keys:** The config files are in `.gitignore` for your protection
2. **Rotate compromised keys:** If you accidentally commit keys, rotate them immediately
3. **Use environment variables:** For production use, prefer environment variables over config files
4. **Limit API key permissions:** Grant only the minimum required permissions
5. **Monitor API usage:** Set up alerts for unusual activity

### Troubleshooting

**Common issues and solutions:**

- **"Module not found" errors:** Run `pip install -r requirements.txt`
- **Google OAuth errors:** Delete `token.json` and re-authenticate
- **Jira connection failures:** Verify your API token and URL are correct
- **Permission errors:** Ensure your API keys have the required scopes

---

*System maintained by the AI Product Agent. Refer to `AI_Guidance/Rules/NGO.md` for persona alignment.*