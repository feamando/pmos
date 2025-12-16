# PLAN: Strategy Document Indexing

**Objective:** Fetch and index content for Domain Objectives (DOs) and Yearly Plans (YPs) referenced in Domain entities.

## 1. Inventory
- [x] Scan `Brain/Entities/Domain_*.md` for doc titles.
- [x] Create a target list of Documents to fetch.

## 2. Content Acquisition
- [x] **Script:** `AI_Guidance/Tools/strategy_indexer.py`
    - [x] Search GDrive for titles.
    - [x] Fetch content.
    - [x] Save to `Brain/Inbox/Strategy_Raw/`.

## 3. Knowledge Processing
- [x] **Yearly Plans:** Parse content to `Brain/Strategy/YP_2026_[Alliance].md`.
- [x] **Domain Objectives:** Parse content to `Brain/Strategy/DO_2026_[Domain].md`.
- [ ] **Update Links:** Update Domain entities to point to local files (or keep GDrive links if found).

## 4. Targets
- [x] Consumer Mega-Alliance YP (New Ventures YP found)
- [x] New Ventures YP (Found)
- [ ] Global Operations YP (Not Found)
- [ ] Procurement & FSQA DO (Not Found)
- [x] Fulfillment DO (Found)
- [x] Meal Kits DO (Found)
- [x] RTE DO (Found)
