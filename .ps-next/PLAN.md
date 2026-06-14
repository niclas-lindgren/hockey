# Plan: Advisory final review summary on report page
**Goal:** The generated `season_plan_report.html` includes a short human-readable advisory quality review after export, covering clumping, missing clubs, host patterns, and outliers without changing deterministic pass/fail gates.
**Created:** 2026-06-14
**Intent:** Give organizers a quick qualitative sanity check on the report page so obvious schedule oddities are easier to spot.
**Backlog-ref:** 86

## Tasks
- [ ] Add an advisory review summary panel to the report HTML output
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/__init__.py, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/styles.css, tournament_scheduler/html/templates/review_summary.html, tests/test_stage4_export.py
  - Approach: Compute a small qualitative summary from the finished plan (week clumping, missing RVV host clubs, unusual host concentration, and obvious outliers), render it only on the report page as a non-blocking review panel, and add focused regression coverage for the report-only content.
- [ ] Add regression coverage for the report summary and keep the season plan page unchanged
  - Files: tests/test_stage4_export.py
  - Approach: Extend the stage 4 HTML export tests to assert the report page contains the new review summary content while `season_plan.html` does not, using a plan that triggers at least one advisory finding.

## Notes
Use the fixed RVV club set from the project instructions when checking for missing hosts. Keep the summary advisory only; the deterministic fairness gate remains the authoritative pass/fail mechanism.

## Acceptance Criteria
- [ ] `season_plan_report.html` contains a readable advisory review section with at least one qualitative finding or a clear “no major issues” message.
- [ ] `season_plan.html` does not contain the advisory review section.
- [ ] The stage 4 HTML export tests pass.

## Log
<!-- pi-next appends entries here after each task -->
