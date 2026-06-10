# Plan: Even time-distribution validator
**Goal:** The season plan surfaces explicit warnings when any month carries significantly more or fewer tournaments than the expected seasonal average, so organizers can spot unbalanced scheduling before finalizing.
**Created:** 2026-06-10
**Intent:** The planner already scores month-balance internally, but the user never sees *which* months are over/under-loaded. This adds explicit per-month warnings surfaced as CLI output and Excel.
**Backlog-ref:** 7

## Tasks
- [x] Add month-load warnings to SeasonPlanner
  - Files: tournament_scheduler/season_planner.py
  - Approach: (a) Add `max_month_deviation_ratio: float = 0.5` parameter — a month is flagged when its tournament count deviates by more than 50% from the expected average. (b) Add `_scan_month_load_warnings` method (same pattern as `_scan_game_count_warnings`) that compares `_month_counts` to expected monthly load and appends tuples `(year, month, count, expected, pct_deviation)`. (c) Add `month_load_warnings` property. (d) Call `_scan_month_load_warnings` at the end of `build_plan` (after `_month_balance_score`).

- [x] Surface warnings in CLI output
  - Files: tournament_scheduler/cli/season_command.py
  - Approach: Add `_print_month_load_warnings` static method that renders over/under-loaded months using `TournamentOutput.print_warning`. Norwegian text: "Måneder med ujevn turneringsbelastning (avvik >X% fra forventet)". Call it after other warnings.

- [x] Update rules report
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add a "Jevn månedsbelastning" entry in `rules_report()` mentioning the deviation threshold.

## Notes
- Month names should be in Norwegian (januar, februar, …).
- The expected average is `target_tournament_count / num_months_in_window`.
- Reuses `_month_counts` already populated during build_plan.

## Acceptance Criteria
- [ ] `month_load_warnings` property returns structured warnings for months with >50% deviation.
- [ ] CLI prints "Måneder med ujevn turneringsbelastning" with Norwegian month names and deviation percentages.
- [ ] Existing tests continue to pass (no regressions).
- [ ] New test verifies month_load_warnings fires for an uneven plan.

## Log
<!-- pi-next appends entries here after each task -->
