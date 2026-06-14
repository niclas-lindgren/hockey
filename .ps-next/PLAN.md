# Plan: Split season-plan diagnostics into a companion report page
**Goal:** `season_plan.html` stays schedule-focused while a new diagnostics page carries fairness, hosting, travel, and review metrics.
**Created:** 2026-06-14
**Intent:** Keep the main season-plan view readable for organizers while preserving the existing quality and explanation data in a separate companion report.
**Backlog-ref:** 87

## Tasks
- [ ] Refactor the HTML exporter to emit a lean schedule page plus a separate diagnostics report page.
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/header.html, tournament_scheduler/html/templates/navbar.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/script.js, tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: split the current season-plan rendering into shared data preparation plus two page renderers; keep `season_plan.html` focused on header, exports, filters, and the tournament timeline, and generate `season_plan_report.html` for scores, fairness gate, fairness adjustments, travel stats, heatmap, club dashboard, and other review details; update navbar links so both pages can switch between schedule/report/calendars cleanly.
- [ ] Update regression coverage for both season-plan pages and the new export file layout.
  - Files: tests/test_stage4_export.py, tests/test_manual_adjustment_workflow.py
  - Approach: assert Stage 4 writes both HTML files, the schedule page no longer contains diagnostics blocks, the report page still contains the metrics/fairness content, and existing CLI/workflow entry points still produce the schedule page path expected by downstream code.

## Notes
The diagnostics content already exists in `HtmlExporter`; this change is mostly about moving it off the primary schedule page and keeping link/navigation behavior consistent with the existing calendars.html ↔ season_plan.html pattern.

## Acceptance Criteria
- [ ] `season_plan.html` contains the schedule view without fairness/metrics panels.
- [ ] `season_plan_report.html` contains the diagnostic panels and links back to the schedule view.
- [ ] Stage 4 export and workflow tests pass with the new two-page layout.

## Log
<!-- pi-next appends entries here after each task -->
