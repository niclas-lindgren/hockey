# Plan: Surface export actions at the top of the season plan header
**Goal:** `season_plan.html` shows the Excel/CSV/iCal export actions in a prominent top-of-header action row.
**Created:** 2026-06-14
**Intent:** Make downloads immediately visible without burying them beside the header stats.
**Backlog-ref:** 88

## Tasks
- [x] Rework the season-plan HTML header so export links render in a dedicated top action row above the title/stats cluster.
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/header.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/styles.css
  - Approach: Move the `$EXPORT_LINKS$` placeholder into a new top-level header action slot, keep the same download filenames/labels, and tweak CSS so the buttons read as a header action cluster instead of a side accessory.
- [x] Tighten the stage-4 HTML regression test to assert the export links appear before the main header content in `season_plan.html`.
  - Files: tests/test_stage4_export.py
  - Approach: Extend the HTML assertions to check ordering around the export block versus the page title/stats so the top-of-header placement stays locked down.

## Notes
The HTML exporter renders both `season_plan.html` and `season_plan_report.html` from the same template stack, so the layout change should stay consistent across both outputs. Keep filenames and button text unchanged.

## Acceptance Criteria
- [ ] `season_plan.html` contains Excel, CSV, and iCal download links in a top-of-header action row.
- [ ] `tests/test_stage4_export.py` verifies the export links are positioned before the main header stats/content.

## Log


### 2026-06-14 — Tighten the stage-4 HTML regression test to assert the export links appear before the main header content in `season_plan.html`.
**Done:** Added ordering assertions that place the export links before the header-main stats block in both season-plan HTML outputs.
**Rationale:** This locks in the new top-row placement and prevents regressions where export links drift back beside the stats cluster.
**Findings:** The existing test already covered filename presence; I strengthened it by asserting export-link ordering relative to the new header-main container.
**Files:** tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-14 — Rework the season-plan HTML header so export links render in a dedicated top action row above the title/stats cluster.
**Done:** Moved the export links into a dedicated top header action row above the title/stats cluster.
**Rationale:** The header now presents downloads as primary actions instead of a side accessory, matching the requested page-header placement.
**Findings:** The template already centralized the export-link HTML, so the layout change only needed template/CSS reshaping; no exporter logic changes were required.
**Files:** tournament_scheduler/html/templates/header.html; tournament_scheduler/html/templates/styles.css
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
