# Plan: Fix plan critic hosting-day counting

**Goal:** The clump check in generate_critic_summary and suggest_moves counts distinct (host_club, date) pairs per month so same-day multi-age-group tournaments at one arena are treated as one hosting duty, not several.
**Created:** 2026-06-21
**Intent:** Prevent false-positive clump warnings when a club hosts multiple age-group tournaments on the same day, and prevent auto-adjust from cycling on those false positives.
**Backlog-ref:** 183

## Tasks

- [x] Replaced defaultdict(int) with defaultdict(set) in generate_critic_summary to count distinct hosting days; added fairness_gate, game_count_spread, team_game_counts to load_plan; fixed test_auto_adjust.py to use _plan_to_dict serialization and updated expected new_date. — 2026-06-21
  - Files: tournament_scheduler/cli/plan_critic.py
  - Approach: Replace the existing `defaultdict(int)` that counts raw tournaments per (host_club, year, month) with a `defaultdict(set)` that collects distinct dates; the threshold check becomes `len(day_set) > 2`. Keep the issue message wording consistent so existing regex in suggest_moves still matches.

- [x] suggest_moves now finds the latest distinct date in the clumped month, collects all tournament IDs on that date, and emits one move proposal per tournament — the whole hosting day moves together to the same new_date. — 2026-06-21
  - Files: tournament_scheduler/cli/plan_critic.py
  - Approach: After extracting club/year/month from the issue string, find the latest distinct date in that month for that club, then collect all tournament IDs whose date matches that day and emit a move proposal for each, rather than selecting only the single last tournament ID (tids[-1]).

- [x] Added 4 new test cases: same-day multi-age-group counts as one day (no clump), 3 distinct days triggers clump, 2 on same day + 1 other  2 days (no clump), and existing tests still pass. — 2026-06-21
  - Files: tests/test_plan_critic.py
  - Approach: Add test cases where a club hosts 4 tournaments across 2 days (should not flag) and 3 tournaments across 3 separate days (should flag at threshold 2); adjust any existing fixture that assumes raw tournament count drives the threshold.

- [ ] Update tests for suggest_moves day-based moves
  - Files: tests/test_plan_critic.py, tests/test_auto_adjust.py
  - Approach: Add a test where a clump issue has multiple same-day tournaments and verify suggest_moves returns one move proposal per tournament on that day; also confirm the auto-adjust convergence test terminates without cycling when the false-positive case is corrected.

## Notes

Constraints: none

Key patterns:
- Tournament fields used: date (datetime), host_club (str), arena (str), id
- suggest_moves parses issue string via regex to extract club/year/month_name; the issue message format must remain regex-compatible
- Cancelled tournaments are already skipped in generate_critic_summary — preserve that guard
- rvv_cli.py and pipeline_orchestrator.py consume generate_critic_summary and suggest_moves but do not need changes if the function signatures are preserved

## Acceptance Criteria

- [ ] A plan where one club hosts 4 tournaments on 2 days in a single month produces no hosting-clump issue in the critic summary.
- [ ] A plan where one club hosts 3 tournaments on 3 separate days in a single month returns a hosting-clump issue in the critic summary.
- [ ] suggest_moves for a multi-day clump issue produces move proposals that contain all tournaments scheduled on the targeted hosting day, not just one.
- [ ] The auto-adjust convergence test runs to completion and does not cycle when the only clumps are same-day multi-age-group tournaments at one arena.
- [ ] pytest passes with no regressions in tests/test_plan_critic.py and tests/test_auto_adjust.py after the changes.

## Log
<!-- PS:next appends entries here after each task is executed -->

### 2026-06-21 — Replaced defaultdict(int) with defaultdict(set) in generate_critic_summary to count distinct hosting days; added fairness_gate, game_count_spread, team_game_counts to load_plan; fixed test_auto_adjust.py to use _plan_to_dict serialization and updated expected new_date.
**Rationale:** Used distinct dates per (club, year, month) tuple; load_plan now restores fairness_gate so generate_critic_summary produces issues for the test_escalates test; _make_checkpoint updated to serialize SeasonPlan via _plan_to_dict.
**Findings:** All 687 tests pass; generate_critic_summary now counts hosting days not raw tournament count; load_plan restores fairness_gate field.
LESSONS: load_plan must restore fairness_gate (and game_count_spread, team_game_counts) from plan_data or generate_critic_summary will silently return no fairness issues
**Files:** tests/test_auto_adjust.py (+11/-4), tournament_scheduler/cli/plan_critic.py (+16/-5), tournament_scheduler/pipeline/tournament_updater.py (+3/-0)
**Commit:** 3c41547 (hockey)

### 2026-06-21 — suggest_moves now finds the latest distinct date in the clumped month, collects all tournament IDs on that date, and emits one move proposal per tournament — the whole hosting day moves together to the same new_date.
**Rationale:** Found the latest date by iterating tids; same target_arena and new_date used for all; loop emits one entry per day_tid.
**Findings:** All 687 tests pass; suggest_moves emits one move per tournament on the latest hosting day.
LESSONS: none
**Files:** tournament_scheduler/cli/plan_critic.py (+46/-25)
**Commit:** 2c033b0 (hockey)

### 2026-06-21 — Added 4 new test cases: same-day multi-age-group counts as one day (no clump), 3 distinct days triggers clump, 2 on same day + 1 other  2 days (no clump), and existing tests still pass.
**Rationale:** All 4 new tests pass with the distinct-day counting logic from task 1.
**Findings:** All tests pass; 4 new hosting-day tests confirm the threshold is based on distinct dates.
LESSONS: none
**Files:** tests/test_plan_critic.py (+45/-0)
**Commit:** [pending — fill after commit]
