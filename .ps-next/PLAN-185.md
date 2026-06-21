# PLAN

**Feature:** Hosting count per month check compares across age groups — should only flag over-hosting when a single club hosts too many tournaments of the same age group in a month, not total across all age groups. Fix the critic/rules check so the monthly hosting spread is scoped per age group.
**Goal:** Hosting count per month check compares across age groups — should only flag over-hosting when a single club hosts too many tournaments of the same age group in a month, not total across all age groups. Fix the critic/rules check so the monthly hosting spread is scoped per age group.
**Backlog-ref:** 185
**Constraints:** none
**Date:** 2026-06-21
**Intent:** Prevent false-positive over-hosting warnings caused by conflating tournaments of different age groups when evaluating monthly hosting load per club.

---

## Tasks

- [x] Scoped host_month_days key to include age_group so clump detection fires per-age-group, not across all age groups. Added test verifying 3 different age groups on 3 separate days does not trigger a warning. — 2026-06-21
  - Files: `tournament_scheduler/cli/plan_critic.py`
  - Approach: Change `host_month_days` key from `(host_club, t_date.year, t_date.month)` to `(host_club, t_date.year, t_date.month, age_group)` so that day-deduplication and the >2 threshold are evaluated per age group. Retrieve `age_group` via `getattr(t, "age_group", None)` and skip entries where it is missing.

- [ ] Update `count_critic_issues_from_dict` to count per age group
  - Files: `tournament_scheduler/cli/plan_critic.py`
  - Approach: Change `host_month_counts` key from `(host_club, d.year, d.month)` to `(host_club, d.year, d.month, age_group)` by reading `t.get("age_group")` from each serialized tournament dict before incrementing the counter. Skip entries with a missing age_group rather than conflating them.

- [ ] Update `suggest_moves` hosting lookups to include age group in keys
  - Files: `tournament_scheduler/cli/plan_critic.py`
  - Approach: Extend `_club_month_count` and `host_month_to_tids` keys to `(host_club, year, month, age_group)`. Parse the age_group out of the clump issue string (or look it up via `host_month_to_tids`) so that target-month selection only considers months where that same age group has capacity.

- [ ] Add regression tests for per-age-group clump scoping
  - Files: `tests/test_plan_critic.py`
  - Approach: Add a test where one club hosts 3 U10 tournaments on 3 separate days in the same month alongside U12 tournaments on those same days — the U10 sequence should trigger a clump while U12 remains under the threshold. Also add a negative test confirming that 3 hosting days across 3 different age groups (one per day) does NOT trigger a clump.

- [ ] Verify existing same-day multi-age-group tests still pass
  - Files: `tests/test_plan_critic.py`
  - Approach: Run `pytest tests/test_plan_critic.py` and confirm the existing same-day deduplication tests (e.g. 4 tournaments across 2 days with two age groups per day) still pass without modification after the key changes above.

---

## Log

- 2026-06-21 Plan created

---

## Acceptance Criteria

When analyzing hosting counts per month, the system produces separate monthly hosting counts for each age group rather than aggregated totals across all age groups.
The critic reports over-hosting issues only when a single club hosts more than 2 distinct hosting days for the same age group in a month, not when the total across all age groups exceeds the limit.
Tests in test_plan_critic.py pass and contain at least one test verifying that hosting 3 different age groups on 3 separate days does not trigger a clump warning.
Running pytest against the updated plan_critic module returns no false-positive clump issues for a club that hosts one tournament per age group per month across multiple age groups.

### 2026-06-21 — Scoped host_month_days key to include age_group so clump detection fires per-age-group, not across all age groups. Added test verifying 3 different age groups on 3 separate days does not trigger a warning.
**Rationale:** Straightforward key expansion; the existing same-day deduplication (using a set of dates) still works correctly within each age group.
**Findings:** All 23 plan_critic tests pass including the new test_three_age_groups_on_three_days_no_clump.
LESSONS: none
**Files:** tests/test_plan_critic.py (+19/-0), tournament_scheduler/cli/plan_critic.py (+15/-6)
**Commit:** [pending — fill after commit]
