# Plan: Age-group-aware host assignment

**Goal:** Host assignment treats each age group independently — same-arena same-day reuse is allowed across different age groups, and consecutive-weekend streak constraints only apply within the same age group.

**Created:** 2026-06-25

**Intent:** Currently `assign_hosts` and the weekend-balance warning scan track consecutive hosting streaks and last-hosted dates globally per club. This means a club hosting U7 on Saturday cannot also host U10 on the same day (they would compete for the arena), and hosting U7 one week artificially penalizes the club's streak for U10 the following week. The fix makes both the host-assignment cost function and the warning scanner age-group-aware.

**Backlog-ref:** 198

## Tasks

- [ ] Make host-assignment consecutive-streak tracking per-age-group
  - Files: tournament_scheduler/host_assignment.py
  - Approach: Change `last_hosted_date_by_club` → `last_hosted_date_by_club_age` keyed by `(club, age_group)`. Change `consecutive_streak_by_club` → `consecutive_streak_by_club_age` with the same compound key. In `_projected_streak`, look up the streak using the current tournament's age group. The overall gap penalty (`-gap`) remains global to distribute hosting load, but streak timing is scoped per age group.

- [ ] Make weekend-balance warning scan per-age-group
  - Files: tournament_scheduler/warnings.py
  - Approach: In `scan_weekend_balance`, group host dates by `(club, age_group)` instead of just club. Compute consecutive streaks per age group. The reported max consecutive load for a club is the worst across all its age groups, but each streak is only counted within its own age group.

- [ ] Update tests for age-group-aware host assignment
  - Files: tests/test_host_assignment.py
  - Approach: Add test cases where the same club hosts different age groups on consecutive weekends — verify no streak penalty. Add test case where same club hosts the same age group on consecutive weekends — verify streak penalty still applies. Verify same-day same-arena different-age-group assignment is allowed.

## Notes

- `_sequence_same_arena_day_start_times` in season_planner.py already handles same-day same-arena tournaments by sequencing start times — the planning side already allows this. The only fix needed is in the host-assignment cost function so it doesn't penalize arena reuse across age groups.
- The gap component (`-gap`) in the scoring tuple should remain global (club-wide) to spread a club's hosting duties across the season. Only the streak penalty should be age-group-scoped.
- Holiday-heavy hosting penalty should also remain global — it's a club-wide burden regardless of age group.
- The gap-check (4th tuple element in `_score`) uses `last_hosted_date_by_club` — this should remain global to spread load.

## Acceptance Criteria

- [ ] Verify that a club hosting U7 on weekend N and U10 on weekend N+7 does NOT introduce a consecutive-streak penalty in assign_hosts.
- [ ] Verify that a club hosting U7 on weekend N and U7 on weekend N+7 DOES introduce a consecutive-streak penalty in assign_hosts.
- [ ] Verify that assign_hosts allows the same arena on the same day for different age groups without penalizing the second assignment.
- [ ] Verify that scan_weekend_balance reports per-age-group streaks, not a mixing of age groups into one global streak.
- [ ] Verify that existing tests pass without modification and new tests pass.

## Log
<!-- pi-next appends entries here after each task -->
