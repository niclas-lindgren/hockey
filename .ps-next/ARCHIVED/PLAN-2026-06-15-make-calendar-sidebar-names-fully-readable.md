# Plan: Make calendar sidebar names fully readable
**Goal:** Club names in the scraped calendars HTML are no longer truncated in the sidebar filter list.
**Created:** 2026-06-15
**Intent:** Keep the calendar viewer usable when club names are long, so organizers can read and toggle sources without guessing.
**Backlog-ref:** 90

## Tasks
- [x] Widen and reflow the calendar source filter rows so long club names remain visible
  - Files: tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: Adjust the inline sidebar CSS for `.sidebar`, `.filter-item`, and `.club-label` so the name column can grow or wrap instead of ellipsizing; keep the stats/freshness badges aligned and preserve mobile behavior.
- [x] Add a regression test that renders calendars HTML and asserts long source names are not ellipsized by the generated markup/styling
  - Files: tests/test_calendar_viewer.py
  - Approach: Build a tiny fake scraped cache in a temp directory, run `generate_html()`, and assert the output contains the updated sidebar layout rules and the long club name text is preserved.

## Notes
- The issue lives in the `calendars.html` viewer, not the season-plan report.
- The current sidebar uses `overflow: hidden` + `text-overflow: ellipsis` on `.club-label`, which hides long source names.

## Acceptance Criteria
- [ ] `generate_html()` produces `calendars.html` where long club names are shown without ellipsis truncation in the sidebar filter list.
- [ ] The regression test passes and checks the sidebar name rendering/layout for a long source name.

## Log


### 2026-06-15 — Add a regression test that renders calendars HTML and asserts long source names are not ellipsized by the generated markup/styling
**Done:** Added a regression test that generates calendars.html from a fake cache and checks the long club name layout rules are present.
**Rationale:** This locks in the no-ellipsis behavior without requiring browser automation.
**Findings:** A focused HTML-content assertion is enough here; the generated page is deterministic and the relevant CSS is emitted inline by calendar_viewer.py.
**Files:** tests/test_calendar_viewer.py
**Commit:** not committed
### 2026-06-15 — Widen and reflow the calendar source filter rows so long club names remain visible
**Done:** Expanded the calendar sidebar and reflowed source filter rows so long club names can wrap instead of being clipped.
**Rationale:** The viewer was truncating source names with ellipsis, making some clubs hard to identify in the calendar filter list.
**Findings:** The truncation lives entirely in the inline calendars HTML CSS; changing the sidebar width plus label wrapping is sufficient and does not affect the season-plan report.
**Files:** tournament_scheduler/pipeline/calendar_viewer.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
