# PLAN: Domain Strategy Ingestion

**Objective:** Ingest high-level strategy (Domain Objectives, Yearly Plans, Leadership) from "DOs & YPs Configuration".

**Source:** `1DwsNzmbIYucZ65ehMZ74KDo_wMTX03yPfq4JNyZcrto`

## 1. Data Acquisition
- [x] **Fetch Sheet Content:** Use `gdrive_mcp` to read the specific sheet ID.
- [x] **Archive:** Save raw content to `AI_Guidance/Brain/Inbox/RAW_Strategy_Config.md`.

## 2. Ingestion Logic (Script)
- [x] **Parse Tab 2 (DOs & YPs):**
    - Columns: Domain, Alliance, Commercial Leader, Tech Leader, Approver, Domain Objective Doc (Link), Yearly Plan Doc (Link).
    - **Action:** Create `Brain/Entities/Domain_[Name].md`.
    - **Action:** Create `Brain/Strategy/[Alliance]_YP_2026.md` (stub/link).
    - **Action:** Create/Update Person entities for Leaders/Approvers.
- [x] **Parse Tab 5 (Projects):**
    - Map Projects to Domains/Alliances if possible.

## 3. Brain Updates
- [x] **Register Domains:** Add to `registry.yaml`.
- [x] **Linkage:** Ensure Tribes/Squads (from previous task) can ideally be linked to these Alliances (manual or fuzzy match).

## 4. Execution
- [x] Run `AI_Guidance/Tools/domain_brain_ingest.py`.
