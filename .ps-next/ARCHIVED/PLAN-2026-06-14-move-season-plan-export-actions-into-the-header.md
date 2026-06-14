# Plan: Move season-plan export actions into the header
**Goal:** Export buttons are visible in the page header on season_plan.html and season_plan_report.html.
**Created:** 2026-06-14
**Intent:** Make download/export actions immediately accessible without scrolling past the main metrics.
**Backlog-ref:** 88

## Tasks
- [x] Render export links in the HTML header instead of below the metrics bar
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/header.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/styles.css
  - Approach: Move the existing $EXPORT_LINKS$ insertion into the header fragment, remove the old body placement, and adjust header CSS so the export buttons appear as a top-row action cluster without breaking the existing stats/theme toggle layout.
- [x] Update the stage-4 HTML regression tests to pin the header placement
  - Files: tests/test_stage4_export.py
  - Approach: Extend the HTML assertions so they verify the export links are present in the header area and no longer sit in the main content stack below the metrics section.

## Notes
The repo already generates both season_plan.html and season_plan_report.html from the same exporter, so the change should affect both pages consistently. Keep the existing download filenames and button labels unchanged.

## Acceptance Criteria
- [ ] `tests/test_stage4_export.py` shows the export buttons in the header-focused HTML layout.
- [ ] `season_plan.html` still contains Excel, CSV, and iCal download links with the same filenames.

## Log


### 2026-06-14 — Update the stage-4 HTML regression tests to pin the header placement
**Done:** Extended the stage-4 HTML regression test so it checks export links appear ahead of the header stats row, which pins the new top-of-page placement.
**Rationale:** The regression test now guards the layout move and prevents the buttons from drifting back into the main content stack.
**Findings:** The exporter renders both season_plan.html and season_plan_report.html from the same header fragment, so one assertion covers both outputs cleanly.
**Files:** tests/test_stage4_export.py, .ps-next/BACKLOG.md, .ps-next/.lock
**Commit:** not committed
### 2026-06-14 — Render export links in the HTML header instead of below the metrics bar
**Done:** Moved the season-plan download buttons into the page header so export actions are immediately visible on both season_plan.html and season_plan_report.html.
**Rationale:** The header is the most discoverable place for download actions and keeps them adjacent to the page title/theme toggle instead of buried after the metrics block.
**Findings:** The existing exporter already centralised the download-link HTML, so the change was mostly a template/layout move. I also updated the HTML regression test while validating the new placement, even though that file was tracked in the follow-up task.
**Files:** tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/header.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/styles.css, tests/test_stage4_export.py, .ps-next/BACKLOG.md, .ps-next/.lock
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
