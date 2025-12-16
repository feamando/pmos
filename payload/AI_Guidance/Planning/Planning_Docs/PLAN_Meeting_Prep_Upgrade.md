# Plan: Meeting Prep System Upgrade

## Objectives
1.  **GDrive & Calendar Linking:** Upload pre-reads to GDrive and link them in Calendar events.
2.  **Recurring Meetings:** Maintain single "Series" files with history.
3.  **Context Expansion:** Auto-ingest past meeting notes from GDrive.
4.  **Sync:** Maintain local/remote parity.

## Execution Steps

### Phase 1: Authentication & Permissions
- [ ] Update `SCOPES` in `meeting_prep.py` to include `calendar.events` (write) and `drive.file` (write).
- [ ] Delete `AI_Guidance/Tools/gdrive_mcp/token.json` to force re-auth.

### Phase 2: Logic Refactor (meeting_prep.py)
- [x] **Architecture:** Split logic into `MeetingManager` class.
- [x] **File Management:**
    -   Create `Planning/Meeting_Prep/Series/` and `Planning/Meeting_Prep/AdHoc/`.
    -   Implement `get_file_path(event)` based on `recurringEventId`.
- [x] **Content Generation:**
    -   Ad-Hoc: Standard template.
    -   Recurring: Series template (Append new instance to top/bottom).
- [x] **GDrive Sync:**
    -   Implement `upload_file()` using `googleapiclient`.
    -   Implement `update_calendar_event(link)`.

### Phase 3: Context Loop (Advanced)
- [x] Implement `find_past_notes(series_id)` to search GDrive for Gemini notes.
- [x] Implement `summarize_and_inject(notes, prep_file)` to update the *past* section of a series file.

### Phase 4: Integration
- [x] Update `update-context.ps1` to handle the new flow.

## Recurring Meeting File Structure (Proposed)

```markdown
# Meeting Series: [Title]
**Cadence:** Weekly | **Attendees:** [List]

## [YYYY-MM-DD] Upcoming Meeting
[Pre-read Content from Gemini]

---

## [YYYY-MM-DD] Past Meeting
[Summary of notes found in GDrive]
**Action Items:**
- [ ] Item 1
```
