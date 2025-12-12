# AI Agent Installation Guide

**Role:** You are an autonomous software engineer assisting the user in setting up the PM-OS environment.

## Objective
Your goal is to hydrate this directory into a fully functional Product Management Operating System.

## Instruction Sequence

1.  **Environment Check:**
    *   Verify Python is installed (`python --version`).
    *   Verify Git is installed (`git --version`).

2.  **Execution:**
    *   Run the installation script: `python setup.py`.
    *   **INTERACTIVE MODE:** The script will ask for user details. If you are running non-interactively, you cannot complete this step. Ask the user to run it.

3.  **Validation:**
    *   After setup, check for the existence of `AI_Guidance/Rules/<INITIALS>.md` (The Persona File).
    *   Check for `AI_Guidance/Brain/registry.yaml`.

4.  **Credentialing:**
    *   Remind the user to place `credentials.json` in `AI_Guidance/Tools/gdrive_mcp/`.

5.  **Boot:**
    *   Run `./boot.ps1` to initialize the first session context.

## Core Knowledge
Once installed, your primary directive is located in: `AI_Guidance/Rules/AGENT.md`.
Read that file immediately upon completion of setup.
