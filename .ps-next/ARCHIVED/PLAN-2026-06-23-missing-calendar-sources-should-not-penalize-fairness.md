# Plan: Missing calendar sources should not penalize fairness
**Goal:** Calendar sources that are absent from scraping are surfaced as context, but they do not lower the fairness gate score or trigger roughness warnings.
**Created:** 2026-06-23
**Intent:** Keep the fairness gate focused on actual scheduling quality while still telling operators which clubs lacked calendar coverage.

## Tasks
- [x] Make missing-calendar clubs informational instead of a fairness penalty
  - Files: tournament_scheduler/fairness_scoring.py, tournament_scheduler/warnings.py
  - Approach: keep the missing-club list in the gate payload and host breakdown, but move it into a non-scoring note so the overall gate reflects only real schedule quality issues.
- [x] Update tests and report text to match the non-penalty behavior
  - Files: tests/test_season_planner.py, tournament_scheduler/cli/reporting.py, tournament_scheduler/html/renderers/fairness.py
  - Approach: assert the fairness gate stays pass when the only issue is missing calendar data, and keep the missing-club note visible in CLI/HTML output.

## Notes
- Preserve the existing warning/detail text so operators still see which clubs had no scrape coverage.
- Do not change host-deviation math beyond excluding missing clubs from the penalty path.

## Acceptance Criteria
- [ ] A plan with missing calendar coverage but no real scheduling issues returns a passing fairness gate while still listing the missing clubs in output.
- [ ] CLI and HTML fairness summaries still mention excluded clubs when calendar data is missing.

## Log


### 2026-06-23 — Update tests and report text to match the non-penalty behavior
**Done:** Updated the regression test to assert the gate stays PASS when only calendar coverage is missing, and taught the CLI/HTML fairness summaries to render the new non-scoring note payload.
**Rationale:** The user-facing outputs needed to match the new semantics so operators still see which clubs lacked coverage without the gate treating it as a failure signal.
**Findings:** CLI reporting now reads fairness_gate.notes first and falls back to the old metric shape for compatibility; HTML now renders note blocks above the metric grid; the missing-calendar host warning was removed so it no longer contributes to warning counts.
**Files:** tests/test_season_planner.py, tournament_scheduler/cli/reporting.py, tournament_scheduler/html/renderers/fairness.py
**Commit:** not committed
### 2026-06-23 — Make missing-calendar clubs informational instead of a fairness penalty
**Done:** Moved missing-calendar clubs out of the scoring path and into a non-scoring fairness-gate note so absent scrape coverage no longer changes the gate status or score.
**Rationale:** The gate should reflect real scheduling quality; missing calendar coverage is context for operators, not a fairness penalty.
**Findings:** hosting_deviation still uses only the available calendar clubs; missing clubs are retained in gate.notes and host-breakdown details; host warning counts no longer include missing-calendar clubs.
**Files:** tournament_scheduler/fairness_scoring.py, tournament_scheduler/warnings.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
