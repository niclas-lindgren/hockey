# Plan: Calendar heatmap in HTML report
**Goal:** The HTML report shows a month-grid heatmap (Oct–Apr) of tournament assignments per weekend, colour-coded by host club, so organizers can spot scheduling density at a glance.
**Created:** 2026-06-10
**Intent:** The existing schedule is timeline-based; a heatmap gives a bird's-eye view of the whole season showing which weekends are busy, free, or have clashes, complementary to the tabular output.
**Backlog-ref:** 28

## Tasks
- [x] Compute weekend-heatmap data in HtmlExporter.export()
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Build a dict mapping ISO-week string (e.g. "2025-W40") → set of (host_club, age_group) tuples for all non-cancelled tournaments. Determine the season's month range (Oct–Apr). Serialize to JSON as `$HEATMAP_JSON$`. Also compute `$HEATMAP_CLUB_COLORS_JSON$` mapping club names to colour values.

- [x] Add heatmap HTML section and JS rendering
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Add a new collapsible `<details>` section "🗓️ Sesongvarmekart" between the score bar and filters. Render a month-grid table where columns are weekends (Sat+Sun date ranges) and rows are clubs. Each cell shows the age group abbreviation with club-colour background if a tournament is hosted there that weekend; empty cells are dimmed. Add a legend. Build all rendering client-side in JS from the embedded `HEATMAP` and `HEATMAP_CLUB_COLORS` JSON. Use the existing colour palette from pipeline/calendar_viewer.py.

## Acceptance Criteria
- [ ] The HTML report contains a `<details>` section with id `heatmapSection`.
- [ ] `run:pytest tests/test_stage4_export.py -x -q` passes unchanged.
- [ ] The heatmap shows at least 4 club rows and October–April columns.
- [ ] Cells with tournaments are color-coded and show the age group abbreviation.

## Log


### 2026-06-10 — Add heatmap HTML section and JS rendering
**Done:** Added heatmap collapsible section (open by default) with month-grouped week columns, club rows, color-coded tournament cells, and a legend. Built as client-side JS rendering from embedded HEATMAP/HEATMAP_CLUB_COLORS JSON.
**Rationale:** Heatmap uses a sticky first column for club names, horizontal scrolling for weeks. Week columns are grouped by month label. Cells show age group abbreviations with club-coloured backgrounds when tournaments exist; empty cells are dimmed. Legend renders below the table. Follows the dark-theme design system with var(--ice-*) CSS.
**Findings:** All 31 tests pass. ISO week → month calculation uses UTC dates for consistency. Heatmap defaults to `open` so it's visible on page load but collapsible.
**Files:** tournament_scheduler/html/html_exporter.py (+80 lines: HTML section, JS rendering, template markers)
**Commit:** not committed
### 2026-06-10 — Compute weekend-heatmap data in HtmlExporter.export()
**Done:** Computed heatmap data in export(): groups non-cancelled tournaments by ISO week and host club, collects age groups. Computes week/club ordered lists and dark-theme club colour map.
**Rationale:** Heatmap structure: dict[week_key, dict[club, list[age_group]]]. Uses Python's isocalendar() for ISO week extraction. Club colours adapted from calendar_viewer.py palette for dark theme (dark backgrounds with bright text).
**Findings:** html_exporter.py coverage jumps from 0% to 78% thanks to stage4_export tests exercising the full export pipeline. Uncovered lines are template strings (HTML/JS) and the CLI main block — all expected.
**Files:** tournament_scheduler/html/html_exporter.py (+40 lines in export() method)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
