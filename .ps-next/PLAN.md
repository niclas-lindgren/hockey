# Plan: Strip schedule filters from the report page
**Goal:** `season_plan_report.html` shows diagnostics only, without leftover scheduling filters or count-bar UI.
**Created:** 2026-06-15
**Intent:** Keep the companion report page focused on review content instead of duplicating the interactive season-plan controls.
**Backlog-ref:** 89

## Tasks
- [ ] Remove schedule-only filter/count-bar UI from the report page
  - Files: tournament_scheduler/html/html_exporter.py, tests/test_stage4_export.py
  - Approach: Render filters and the count bar only for the main season-plan page, keep them out of `season_plan_report.html`, and add/adjust tests that assert the report page no longer contains the tournament filter controls or count bar while the season-plan page still does.

## Notes
The report page should remain diagnostics-focused: fairness gate, adjustment summary, review summary, team/travel stats, and heatmap stay; only interactive schedule controls are removed.

## Acceptance Criteria
- [ ] `season_plan_report.html` does not contain the filter controls or count bar, while `season_plan.html` still does.

## Log
<!-- pi-next appends entries here after each task -->
