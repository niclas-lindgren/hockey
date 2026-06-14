# Plan: Split season-plan diagnostics into a companion report page
**Goal:** `season_plan.html` stays schedule-focused while a new diagnostics page carries fairness, hosting, travel, and review metrics.
**Created:** 2026-06-14
**Intent:** Keep the main season-plan view readable for organizers while preserving the existing quality and explanation data in a separate companion report.
**Backlog-ref:** 87

## Tasks
- [x] Refactor the HTML exporter to emit a lean schedule page plus a separate diagnostics report page.
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/header.html, tournament_scheduler/html/templates/navbar.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/script.js, tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: split the current season-plan rendering into shared data preparation plus two page renderers; keep `season_plan.html` focused on header, exports, filters, and the tournament timeline, and generate `season_plan_report.html` for scores, fairness gate, fairness adjustments, travel stats, heatmap, club dashboard, and other review details; update navbar links so both pages can switch between schedule/report/calendars cleanly.
- [x] Update regression coverage for both season-plan pages and the new export file layout.
  - Files: tests/test_stage4_export.py, tests/test_manual_adjustment_workflow.py
  - Approach: assert Stage 4 writes both HTML files, the schedule page no longer contains diagnostics blocks, the report page still contains the metrics/fairness content, and existing CLI/workflow entry points still produce the schedule page path expected by downstream code.

## Notes
The diagnostics content already exists in `HtmlExporter`; this change is mostly about moving it off the primary schedule page and keeping link/navigation behavior consistent with the existing calendars.html ↔ season_plan.html pattern.

## Acceptance Criteria
- [ ] `season_plan.html` contains the schedule view without fairness/metrics panels.
- [ ] `season_plan_report.html` contains the diagnostic panels and links back to the schedule view.
- [ ] Stage 4 export and workflow tests pass with the new two-page layout.

## Log


### 2026-06-14 — Update regression coverage for both season-plan pages and the new export file layout.
**Done:** Covered the split layout with export and CLI regression checks.
**Rationale:** The new report page needs test coverage so the schedule page stays lean and downstream callers still get the expected main HTML path.
**Findings:** The existing Stage 4 tests already exercised most of the export flow; they just needed to assert the new `season_plan_report.html` artifact and the absence of diagnostics from the schedule page.
**Files:** tests/test_stage4_export.py, tests/test_manual_adjustment_workflow.py
**Commit:** not committed
### 2026-06-14 — Refactor the HTML exporter to emit a lean schedule page plus a separate diagnostics report page.
**Done:** Split Stage 4 HTML into `season_plan.html` (schedule-only) and `season_plan_report.html` (diagnostics).
**Rationale:** Organizers get a cleaner primary plan view, while the fairness/travel/hosting review data remains available in a companion page without losing any of the existing metrics.
**Findings:** The shared HTML renderer needed only one codepath for both pages, but the client JS had to tolerate a report page without a timeline; the report path is now written alongside the main export and linked from the navbar/calendars view.
**Files:** tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/header.html, tournament_scheduler/html/templates/navbar.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/script.js, tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/calendar_viewer.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
