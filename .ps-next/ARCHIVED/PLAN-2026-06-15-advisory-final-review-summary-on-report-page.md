# Plan: Advisory final review summary on report page
**Goal:** The generated `season_plan_report.html` includes a short human-readable advisory quality review after export, covering clumping, missing clubs, host patterns, and outliers without changing deterministic pass/fail gates.
**Created:** 2026-06-14
**Intent:** Give organizers a quick qualitative sanity check on the report page so obvious schedule oddities are easier to spot.
**Backlog-ref:** 86

## Tasks
- [x] Add an advisory review summary panel to the report HTML output
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/__init__.py, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/styles.css, tournament_scheduler/html/templates/review_summary.html, tests/test_stage4_export.py
  - Approach: Compute a small qualitative summary from the finished plan (week clumping, missing RVV host clubs, unusual host concentration, and obvious outliers), render it only on the report page as a non-blocking review panel, and add focused regression coverage for the report-only content.
- [x] Add regression coverage for the report summary and keep the season plan page unchanged
  - Files: tests/test_stage4_export.py
  - Approach: Extend the stage 4 HTML export tests to assert the report page contains the new review summary content while `season_plan.html` does not, using a plan that triggers at least one advisory finding.

## Notes
Use the fixed RVV club set from the project instructions when checking for missing hosts. Keep the summary advisory only; the deterministic fairness gate remains the authoritative pass/fail mechanism.

## Acceptance Criteria
- [ ] `season_plan_report.html` contains a readable advisory review section with at least one qualitative finding or a clear “no major issues” message.
- [ ] `season_plan.html` does not contain the advisory review section.
- [ ] The stage 4 HTML export tests pass.

## Log


### 2026-06-14 — Add regression coverage for the report summary and keep the season plan page unchanged
**Done:** Extended the stage 4 HTML export regression test so the report page must show the advisory review summary while the season plan page must not.
**Rationale:** The test locks in the report-only behavior and catches regressions if the summary leaks back into the main season plan view.
**Findings:** The existing stage 4 export test already had a realistic multi-age-group plan fixture, so the new assertions could reuse it and verify the report wording directly.
**Files:** tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-14 — Add an advisory review summary panel to the report HTML output
**Done:** Added a report-only advisory review panel that summarizes clumping, missing RVV host clubs, host concentration, and per-team game-count outliers.
**Rationale:** The report page now gives organizers a short qualitative sanity check after the deterministic exports finish, while leaving the season plan page unchanged.
**Findings:** The RVV club set is fixed in project instructions, so the missing-host check can safely compare against all 9 clubs. The new report summary is advisory only and uses existing plan data; no new pipeline state was required.
**Files:** tournament_scheduler/html/html_exporter.py; tournament_scheduler/html/templates/__init__.py; tournament_scheduler/html/templates/page_template.html; tournament_scheduler/html/templates/styles.css; tournament_scheduler/html/templates/review_summary.html; tests/test_stage4_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
