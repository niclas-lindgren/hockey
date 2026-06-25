# Plan: Age-group-aware host assignment

**Goal:** Host assignment treats each age group independently — same-arena same-day reuse is allowed across different age groups, and consecutive-weekend streak constraints only apply within the same age group.

**Created:** 2026-06-25

**Intent:** Currently `assign_hosts` and the weekend-balance warning scan track consecutive hosting streaks and last-hosted dates globally per club. This means a club hosting U7 on Saturday cannot also host U10 on the same day (they would compete for the arena), and hosting U7 one week artificially penalizes the club's streak for U10 the following week. The fix makes both the host-assignment cost function and the warning scanner age-group-aware.

**Backlog-ref:** 198

## Tasks

- [x] Make host-assignment consecutive-streak tracking per-age-group
  - Files: tournament_scheduler/host_assignment.py
  - Approach: Change `last_hosted_date_by_club` → `last_hosted_date_by_club_age` keyed by `(club, age_group)`. Change `consecutive_streak_by_club` → `consecutive_streak_by_club_age` with the same compound key. In `_projected_streak`, look up the streak using the current tournament's age group. The overall gap penalty (`-gap`) remains global to distribute hosting load, but streak timing is scoped per age group.

- [x] Make weekend-balance warning scan per-age-group
  - Files: tournament_scheduler/warnings.py
  - Approach: In `scan_weekend_balance`, group host dates by `(club, age_group)` instead of just club. Compute consecutive streaks per age group. The reported max consecutive load for a club is the worst across all its age groups, but each streak is only counted within its own age group.

- [x] Update tests for age-group-aware host assignment
  - Files: tests/test_host_assignment.py
  - Approach: Add test cases where the same club hosts different age groups on consecutive weekends — verify no streak penalty. Add test case where same club hosts the same age group on consecutive weekends — verify streak penalty still applies. Verify same-day same-arena different-age-group assignment is allowed.

## Notes

- `_sequence_same_arena_day_start_times` in season_planner.py already handles same-day same-arena tournaments by sequencing start times — the planning side already allows this. The only fix needed is in the host-assignment cost function so it doesn't penalize arena reuse across age groups.
- The gap component (`-gap`) in the scoring tuple should remain global (club-wide) to spread a club's hosting duties across the season. Only the streak penalty should be age-group-scoped.
- Holiday-heavy hosting penalty should also remain global — it's a club-wide burden regardless of age group.
- The gap-check (4th tuple element in `_score`) uses `last_hosted_date_by_club` — this should remain global to spread load.

## Acceptance Criteria

- [ ] pytest tests pass on existing tests.
- [ ] New test shows assign_hosts consecutive-streak penalty is 0 when a club hosts different age groups on consecutive weekends.
- [ ] New test shows assign_hosts consecutive-streak penalty > 0 when a club hosts the SAME age group on consecutive weekends.
- [ ] New test shows assign_hosts does not reject same-arena same-day assignments for different age groups.
- [ ] New test shows scan_weekend_balance tracks streaks independently per age group.

## Log



### 2026-06-25 — Update tests for age-group-aware host assignment
**Done:** Added `TestAgeGroupAwareHostStreak` class to test_host_assignment.py with 3 tests: different-age-group-no-streak-penalty, same-age-group-streak-still-applies, and same-arena-same-day-different-age-groups-allowed.
**Rationale:** Tests the observable behavior difference: same club hosting different age groups on consecutive weekends should not trigger streak penalty, same club hosting same age group should still be penalized, and same-day multi-age-group hosting at the same arena is allowed.
**Findings:** Existing SeasonPlanner failures (test_proposes_target_tournaments_per_age_group, test_tournament_dates_are_spread_across_the_season_window) and canonical_input bug are pre-existing. 120 relevant tests pass.
**Files:** tests/test_host_assignment.py
**Commit:** not committed
### 2026-06-25 — Make weekend-balance warning scan per-age-group
**Done:** Changed `hosting_weekend_balance_breakdown` to group tournament dates by `(club, age_group)` instead of just club. Consecutive-weekend streaks are now computed independently per age group. The reported max per club is the worst streak across its age groups. The output schema (same keys) is preserved for downstream consumers.
**Rationale:** The consecutive streak check should only apply within the same age group. Hosting facilities may be shared across age groups on different weekends without creating a problematic streak.
**Findings:** The function is called from two places: `fairness_scoring.py` (for the fairness gate) and `scan_hosting_warnings` within `warnings.py` itself. Both use the same output schema keys which are preserved unchanged.
**Files:** tournament_scheduler/warnings.py
**Commit:** not committed
### 2026-06-25 — Make host-assignment consecutive-streak tracking per-age-group
**Done:** Changed `last_hosted_date_by_club` and `consecutive_streak_by_club` dicts in `assign_hosts()` to be keyed by `(club, age_group)` tuple instead of just club. The recency gap penalty (`-gap` in the scoring tuple) remains global to spread total hosting load across weekends. Streak tracking and projection now use the compound key, so hosting U7 on one weekend does not create a streak penalty for U10 on the next weekend.
**Rationale:** The streak is an age-group concept — a club hosting two different age groups on consecutive weekends is not a problematic streak. Same-age-group consecutive hosting should still be penalized. Keeping the global gap penalty preserves overall load spreading.
**Findings:** The `_projected_streak` function is a closure that captures `age_group` from the outer loop scope, so it naturally works with the age-group-keyed lookup. Two existing test failures in `test_season_planner.py` are pre-existing and unrelated to this change.
**Files:** tournament_scheduler/host_assignment.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
