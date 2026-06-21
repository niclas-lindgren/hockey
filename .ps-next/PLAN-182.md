# Plan: Add monthly-balance constraint to Stage 3 planner

**Feature:** Add monthly-balance constraint to Stage 3 planner: cap the number of hosting *days* per club per month during initial scheduling so clusters like "Jar hosts 6 tournaments in September" never appear in the first place. The constraint should operate on distinct calendar days (not tournament count) because same-day consecutive age groups at the same arena are a single hosting burden. Implementation: in `season_planner.py` `_score_candidate_date` (or the date-availability check), count how many distinct days the candidate club already hosts in the candidate month and reject/penalise dates that would push it over a configurable threshold (e.g. `max_hosting_days_per_month`, defaulting from `Innstillinger` sheet). Expose the threshold in `input.xlsx` as a new `max_hosting_days_per_month` key in the Innstillinger sheet. Acceptance: fresh Stage 3 output has no club-month pair exceeding the threshold; threshold defaults to 2 but is overridable; no regression in existing tests.
**Goal:** Add monthly-balance constraint to Stage 3 planner: cap the number of hosting *days* per club per month during initial scheduling so clusters like "Jar hosts 6 tournaments in September" never appear in the first place.
**Backlog-ref:** 182
**Constraints:** none
**Date:** 2026-06-21
**Intent:** Prevent hosting-load clustering by enforcing a per-club, per-month cap on distinct hosting days at the date-scoring stage so the initial plan is already balanced before any post-hoc adjustment.

---

## Tasks

- [x] Added max_hosting_days_per_month: int  2 to SeasonPlanner.__init__ with self assignment, added the param to _make_planner in stage3_helpers.py, and extracted maxHostingDaysPerMonth from config in stage3_planning.py before passing it to _make_planner. — 2026-06-21
  - Files: `tournament_scheduler/season_planner.py`, `tournament_scheduler/pipeline/stage3_helpers.py`, `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: Add `max_hosting_days_per_month: int = 2` to `SeasonPlanner.__init__` and store it as `self.max_hosting_days_per_month`. In `stage3_helpers.py` `_make_planner`, extract the key `"max_hosting_days_per_month"` from the config dict (with default 2) and pass it to the constructor, following the same pattern as `max_hosting_deviation`.

- [x] Added _hosting_days_by_club_month tracking dict to SeasonPlanner, populate it during date selection using a least-total-days predicted-host heuristic, and penalise candidate dates with a 1e6 score in _score_candidate_date when all clubs would exceed max_hosting_days_per_month in that month. Also update the dict with actual hosts after tournament commitment. — 2026-06-21
  - Files: `tournament_scheduler/season_planner.py`
  - Approach: Add an instance dict `self._hosting_days_by_club_month: dict[tuple[str, tuple[int,int]], set[date]]` that records, for each `(club, (year, month))`, the set of distinct dates already assigned as host. In `_score_candidate_date`, derive the predicted host club for the candidate date (using the least-recently-hosted club heuristic already in `_assign_hosts`), look up how many distinct days that club already hosts in the candidate month, and return a very large penalty (e.g. 1e6) if adding this date would exceed `self.max_hosting_days_per_month`. Update the tracking structure after a date is committed in `build_plan`.

- [x] Added maxHostingDaysPerMonth forwarding in _parse_config (stage1_helpers.py) and propagation through load_effective_config (stage1_config.py) so stage3 receives the value from the checkpoint dict. — 2026-06-21
  - Files: `tournament_scheduler/pipeline/input_workbook.py`, `tournament_scheduler/pipeline/stage1_helpers.py`
  - Approach: `_read_settings` already reads arbitrary key/value pairs, so the Innstillinger row is sufficient; no code change is needed in `input_workbook.py` itself. In `stage1_helpers.py` `_parse_config`, forward the key `"max_hosting_days_per_month"` (int-coerced, defaulting to 2) into the stage 1 checkpoint dict alongside existing forwarded keys like `"maxHostingDeviation"` and `"target_tournament_count"`.

- [x] Appended a new row to the Innstillinger sheet with feltmax_hosting_days_per_month and verdi2 using openpyxl. — 2026-06-21
  - Files: `input.xlsx`
  - Approach: Open the workbook and append a new row to the Innstillinger sheet with `felt = "max_hosting_days_per_month"` and `verdi = 2`, following the existing key/value layout; save the file.

- [ ] Add unit tests for the monthly hosting-day constraint in `test_season_planner.py`
  - Files: `tests/test_season_planner.py`
  - Approach: Write test cases that construct a minimal `SeasonPlanner` with `max_hosting_days_per_month=2`, schedule enough tournaments for one club to hit the cap in a single month, and assert that `_score_candidate_date` returns a large penalty for a date that would exceed the cap. Also add a regression test confirming the constraint is not triggered when hosting days are below the threshold.

---

## Acceptance Criteria

When the Stage 3 planner processes a schedule, it produces a plan where no club-month pair has more distinct hosting days than the configured threshold.
The SeasonPlanner class return a `max_hosting_days_per_month` parameter that defaults to 2 and can be overridden via the Innstillinger sheet in `input.xlsx`.
The planner output contain no club-month pairs where the hosting days exceed the configured threshold during Stage 3 planning.
Existing tests that validate Stage 3 planning continue to pass without modification when the new constraint is applied.
The new unit tests in `tests/test_season_planner.py` run and pass, covering both the penalty case and the no-penalty case for the hosting-day cap.

---

## Log

### 2026-06-21 — Added max_hosting_days_per_month: int  2 to SeasonPlanner.__init__ with self assignment, added the param to _make_planner in stage3_helpers.py, and extracted maxHostingDaysPerMonth from config in stage3_planning.py before passing it to _make_planner.
**Rationale:** Followed exact same pattern as max_hosting_deviation: param in __init__, param in _make_planner, config.get() in stage3_planning.py.
**Findings:** Parameter wires cleanly through all three layers with no test regressions from this change.
LESSONS: none
**Files:** stage3_helpers.py (+2), stage3_planning.py (+2), season_planner.py (+2)
**Commit:** 72b59dd (hockey)

### 2026-06-21 — Added _hosting_days_by_club_month tracking dict to SeasonPlanner, populate it during date selection using a least-total-days predicted-host heuristic, and penalise candidate dates with a 1e6 score in _score_candidate_date when all clubs would exceed max_hosting_days_per_month in that month. Also update the dict with actual hosts after tournament commitment.
**Rationale:** none
**Findings:** Tracking is populated in two phases: predicted during date selection (so penalty fires for subsequent age groups) and actual after tournament commitment. All tests pass.
LESSONS: none
**Files:** season_planner.py (+40)
**Commit:** a635350 (hockey)

### 2026-06-21 — Added maxHostingDaysPerMonth forwarding in _parse_config (stage1_helpers.py) and propagation through load_effective_config (stage1_config.py) so stage3 receives the value from the checkpoint dict.
**Rationale:** Also updated stage1_config.py load_effective_config to include maxHostingDaysPerMonth from checkpoint, since that file was not listed in Files but is required for the key to reach stage3.
**Findings:** All tests pass; the key flows from Innstillinger sheet through Stage 1 checkpoint to Stage 3 config.
LESSONS: load_effective_config in stage1_config.py must also be updated to pass the key from checkpoint — the task Files list is incomplete.
**Files:** stage1_helpers.py (+3), stage1_config.py (+1)
**Commit:** 356bea0 (hockey)

### 2026-06-21 — Appended a new row to the Innstillinger sheet with feltmax_hosting_days_per_month and verdi2 using openpyxl.
**Rationale:** none
**Findings:** Row added successfully; stage1_helpers._parse_config will now read and forward this value.
LESSONS: none
**Files:** input.xlsx (binary, row added)
**Commit:** [pending — fill after commit]
