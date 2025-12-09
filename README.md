# PM-OS: The AI-Native Product Operating System

**A Git-backed, CLI-managed framework for Product Management, designed for AI collaboration.**

This repository contains the installer for the PM-OS system. It separates the "Operating System" (Workflows, Agents, Templates) from the "Instance Data" (Your specific Products, Teams, and Plans).

## Prerequisites

*   **Python 3.8+**
*   **Git**
*   **PowerShell** (Windows) or ability to adapt scripts to Bash (Linux/Mac).
*   **Google Cloud Console Access** (For Drive Integration).

## Installation

1.  **Clone this repo** (or copy the folder) to your desired workspace.
2.  **Run the Installer:**
    ```bash
    python setup.py
    ```
3.  **Follow the prompts.** The wizard will ask for your Name, Role, and Team to customize the AI Persona.

## Post-Installation Setup

1.  **Google Drive Integration:**
    *   Go to Google Cloud Console.
    *   Create a project -> Enable Drive API.
    *   Create OAuth Desktop Credentials -> Download `credentials.json`.
    *   Place it in: `AI_Guidance/Tools/gdrive_mcp/credentials.json`.

2.  **Start the System:**
    ```powershell
    ./boot.ps1
    ```

## Architecture

*   **`AI_Guidance/`**: The Core. Rules, Brain, and Tools.
*   **`Products/`**: Your documentation.
*   **`Planning/`**: Meeting prep and OKRs.
*   **`Reporting/`**: Updates.

## AI Agent Integration

This system is optimized for use with **Claude Code** or **Gemini CLI**.
After installation, point your agent to `CLAUDE_INSTALL.md` or `AGENT.md` to bootstrap its understanding.
