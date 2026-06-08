---
date: 2026-06-08
status: done
feature: "Matchup-diversity scoring"
goal: "Matchup-diversity scoring — a scoring/selection algorithm that, given a candidate set of conflict-free weekend dates and the team roster, ranks or selects tournament dates so that each team's opponents vary across the season (avoid repeat matchups where alternatives exist) and tournament load is spread evenly month-to-month."
tags:
  - ps-next
---

---
date: 2026-06-08
status: in-progress
feature: "Matchup-diversity scoring"
goal: "Matchup-diversity scoring — a scoring/selection algorithm that, given a candidate set of conflict-free weekend dates and the team roster, ranks or selects tournament dates so that each team's opponents vary across the season (avoid repeat matchups where alternatives exist) and tournament load is spread evenly month-to-month."
tags:
  - ps-next
---

# Plan: Matchup-diversity scoring
**Goal:** Matchup-diversity scoring — a scoring/selection algorithm that, given a candidate set of conflict-free weekend dates and the team roster, ranks or selects tournament dates so that each team's opponents vary across the season (avoid repeat matchups where alternatives exist) and tournament load is spread evenly month-to-month.
**Created:** 2026-06-08
**Intent:** Sharpen the season planner's existing coarse "novel grouping" heuristic into a real pairwise-opponent-aware, month-balanced scoring/selection algorithm so the generated season plan actually minimizes repeat matchups and avoids clustering tournaments in any single month.
**Backlog-ref:** 4
**Constraints:** none

## Tasks
- [x] Added an _opponent_history dict (frozenset of team-label pairs -> match count) to SeasonPlanner, populated via a new _record_opponent_history helper called in build_plan after each tournament's round-robin games are generated. — 2026-06-08
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/models.py
  - Approach: Introduce an `_opponent_history` structure (dict keyed by frozenset/tuple of team pairs -> match count) alongside the existing `_grouped_with`/`_record_grouping` machinery in season_planner.py, populated whenever `generate_round_robin_games` produces a `Game` for a `Tournament`; this gives the planner a true record of how many times each pair of teams has actually played, distinct from mere co-attendance.

- [x] Added a _month_counts tracker (dict keyed by (year, month) -> tournament count) updated as dates are chosen in build_plan, plus _expected_monthly_load and month_load_ratio helpers that report how a given month's load compares to the season's expected per-month average. — 2026-06-08
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add a `_month_counts` tracker (dict keyed by year-month -> tournament count) updated as dates are chosen in `build_plan`, and a helper that reports the current month's load relative to the season's expected per-month average (derived from `start_date`/`end_date` and target tournament count), giving downstream selection logic a concrete signal for "is this month already over-loaded".

- [x] Added _score_candidate_date combining a repeat-matchup penalty (average _opponent_history count across candidate-participant pairs) with a month-load penalty (excess above the season's expected per-month average), and wired it into _pick_spread_dates's per-bucket selection by predicting a tentative age-group/participant set per candidate (mirroring _next_age_group/_select_participants against local copies of the tracking state) and combining the diversity penalty with the existing closeness-to-bucket-center spread penalty. — 2026-06-08
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add a `_score_candidate_date(date, age_group, candidate_participants)` method that combines (a) a penalty derived from `_opponent_history` for how many repeat matchups the candidate participant set would create and (b) a penalty derived from `_month_counts` for how far the candidate date's month is above the season's per-month average; wire this scoring into `_pick_spread_dates` (or the per-bucket "best date" selection within it) so the planner ranks/picks dates using this combined score rather than spread-only bucket selection.

- [x] Extended _pick_least_recently_grouped to rank candidates first by a new repeat_matchup_score (actual repeat-matchup count vs. already-selected teams, per _opponent_history), falling back to the existing overlap_score (_grouped_with co-attendance), invite count, then roster order as tie-breaks. — 2026-06-08
  - Files: tournament_scheduler/season_planner.py
  - Approach: Replace or extend `_pick_least_recently_grouped` in `_select_participants` with a selection that, among otherwise-eligible candidate teams, prefers the subset minimizing total repeat-matchup count per `_opponent_history` (falling back to the existing least-recently-grouped tie-break when opponent history is equal), so that "avoid repeat matchups where alternatives exist" is enforced directly at selection time rather than only measured after the fact.

- [x] Reworked _diversity_score to be grounded in _opponent_history (fraction of scheduled pairwise games that are first-time pairings) via a new _pairwise_matchup_score helper, added _month_balance_score (derived from _month_counts vs. expected per-month average), added pairwise_matchup_score and month_balance_score fields to SeasonPlan in models.py, set all three on the plan in build_plan, and updated print_diversity_summary in rich_output.py to render both new figures alongside the existing arena-count summary. — 2026-06-08
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/models.py, tournament_scheduler/utils/rich_output.py
  - Approach: Rework `_diversity_score` to compute a metric grounded in `_opponent_history` (e.g. fraction of scheduled matchups that are first-time pairings, or average repeat count per pair) plus a month-balance figure derived from `_month_counts`, store both on `SeasonPlan` (extending the existing `diversity_score` field / adding a `month_balance_score` field in models.py), and update `print_diversity_summary` in rich_output.py to render both figures so they're visible in console output alongside the existing arena-count summary.

- [x] Added a TestOpponentHistoryTrackingAndScoring test class (plus a small_roster_planner_and_plan fixture forcing repeat matchups over a long season window) covering: _opponent_history accumulation from generated games (including cross-checks against recomputed counts and a forced-repeat scenario), _score_candidate_date preferring fresher pairings, _pick_least_recently_grouped preferring subsets that minimize repeat matchups, _month_counts staying within a reasonable spread of the expected per-month average, and presence/range/consistency of the new diversity_score/pairwise_matchup_score/month_balance_score plan metrics. — 2026-06-08
  - Files: tests/test_season_planner.py
  - Approach: Following the existing `FakeScheduler` pattern in tests/test_season_planner.py, add tests asserting that (1) `_opponent_history` correctly accumulates match counts from generated round-robin games, (2) `_score_candidate_date`/selection logic prefers candidates that create fewer repeat matchups when an alternative with no repeats is available, (3) `_month_counts` stays within a reasonable spread (no month holds disproportionately more tournaments than others) across a realistic multi-month season window, and (4) the new diversity/month-balance metrics are computed and present on the resulting `SeasonPlan`.

## Acceptance Criteria
Running the season planner's test suite shows that generated plans do not schedule the same pair of teams against each other more than once when an alternative pairing with no prior matchup is available.
The SeasonPlan produced by build_plan has a diversity metric and a month-balance metric that are both computed from real opponent-history and per-month tournament counts, not from co-attendance grouping alone.
A season plan generated across a multi-month window has no single month holding a disproportionately larger share of tournaments than the season's expected per-month average.
The console output from print_diversity_summary reports both the pairwise-matchup diversity figure and the month-to-month load balance figure for the generated season plan.
Tests in test_season_planner.py covering opponent-history tracking, candidate-date scoring, and month-load balancing pass when the suite is run.

## Log
(empty — populated as tasks complete)

### 2026-06-08 — Added an _opponent_history dict (frozenset of team-label pairs -> match count) to SeasonPlanner, populated via a new _record_opponent_history helper called in build_plan after each tournament's round-robin games are generated.
**Rationale:** Hooked into build_plan rather than generate_round_robin_games (a @staticmethod) to avoid changing its signature; frozenset keys make home/away order irrelevant.
**Findings:** All season_planner tests pass; the new structure tracks true scheduled-matchup counts distinct from _grouped_with co-attendance tracking.
LESSONS: generate_round_robin_games is a @staticmethod, so per-game bookkeeping that needs self must happen in the caller (build_plan) after the games list is returned, not inside the generator.
**Files:** tournament_scheduler/season_planner.py (+24/-0)
**Commit:** 7ffbb1b (hockey)

### 2026-06-08 — Added a _month_counts tracker (dict keyed by (year, month) -> tournament count) updated as dates are chosen in build_plan, plus _expected_monthly_load and month_load_ratio helpers that report how a given month's load compares to the season's expected per-month average.
**Rationale:** Exposed _expected_monthly_load as a static helper and month_load_ratio as an instance method so future selection logic can compute the expected baseline once and query per-date load ratios cheaply; left the values uninvoked by build_plan itself since wiring them into date selection is a separate later task.
**Findings:** All season_planner tests pass; the new tracker and helpers compile and integrate cleanly with the existing per-tournament loop.
LESSONS: month_load_ratio takes expected_per_month as a parameter rather than storing it on self, so callers must compute the baseline once via _expected_monthly_load(start, end, tournament_count) and pass it through — keeps the tracker decoupled from any one selection strategy.
**Files:** tournament_scheduler/season_planner.py (+54/-0)
**Commit:** 7fc9f11 (hockey)

### 2026-06-08 — Added _score_candidate_date combining a repeat-matchup penalty (average _opponent_history count across candidate-participant pairs) with a month-load penalty (excess above the season's expected per-month average), and wired it into _pick_spread_dates's per-bucket selection by predicting a tentative age-group/participant set per candidate (mirroring _next_age_group/_select_participants against local copies of the tracking state) and combining the diversity penalty with the existing closeness-to-bucket-center spread penalty.
**Rationale:** Predicting age-group/participants per candidate date inside _pick_spread_dates (rather than restructuring build_plan to interleave date+age-group selection) keeps the change localized; predictions use local copies of ag_index/scheduled_by_date so the real per-tournament assignment in build_plan is unaffected — the prediction is a heuristic signal for ranking, not a binding commitment.
**Findings:** Full suite (82 passed, 1 skipped) and season_planner-focused tests all pass; combined scoring integrates without disrupting existing spread-based date selection.
LESSONS: _pick_spread_dates runs before the real age-group/participant assignment loop in build_plan, so any scoring that needs _opponent_history/_grouped_with context must predict tentative values using local copies of the tracking dicts — mutating the real self._grouped_with/_invite_counts during prediction would corrupt the actual selection later.
**Files:** tournament_scheduler/season_planner.py (+91/-5)
**Commit:** 916e87a (hockey)

### 2026-06-08 — Extended _pick_least_recently_grouped to rank candidates first by a new repeat_matchup_score (actual repeat-matchup count vs. already-selected teams, per _opponent_history), falling back to the existing overlap_score (_grouped_with co-attendance), invite count, then roster order as tie-breaks.
**Rationale:** Kept the existing greedy seed-then-extend structure and just inserted the opponent-history score as the primary sort key ahead of the prior overlap_score, preserving all existing tie-break behavior for equal opponent-history counts — minimal, low-risk change that directly enforces 'avoid repeat matchups' at selection time.
**Findings:** Full suite (82 passed, 1 skipped) passes; selection now prefers candidate subsets that minimize actual repeat matchups before falling back to mere co-attendance history.
LESSONS: When extending greedy selection heuristics with a new primary criterion, insert it as the first element of the existing sort-key tuple rather than replacing the tuple — this preserves all prior tie-break behavior for free and keeps the diff minimal.
**Files:** tournament_scheduler/season_planner.py (+17/-4)
**Commit:** d4dc3a0 (hockey)

### 2026-06-08 — Reworked _diversity_score to be grounded in _opponent_history (fraction of scheduled pairwise games that are first-time pairings) via a new _pairwise_matchup_score helper, added _month_balance_score (derived from _month_counts vs. expected per-month average), added pairwise_matchup_score and month_balance_score fields to SeasonPlan in models.py, set all three on the plan in build_plan, and updated print_diversity_summary in rich_output.py to render both new figures alongside the existing arena-count summary.
**Rationale:** Kept plan.diversity_score assigned (now delegating to _pairwise_matchup_score) for backward compatibility with any code/tests reading that field, while exposing the new metric explicitly as pairwise_matchup_score per the plan's Approach — avoids a breaking rename while still grounding the score in real opponent history rather than co-attendance.
**Findings:** Full suite (82 passed, 1 skipped) passes; new fields populate correctly and render in the Rich console summary panel in Norwegian alongside existing metrics.
LESSONS: When reworking a scored metric that's read elsewhere (e.g. plan.diversity_score), keep the old field assigned via delegation to the new computation rather than removing it — preserves compatibility for any downstream readers/tests while still satisfying the 'rework' requirement.
**Files:** tournament_scheduler/models.py (+10/-0), tournament_scheduler/season_planner.py (+86/-14), tournament_scheduler/utils/rich_output.py (+8/-0)
**Commit:** 582caf4 (hockey)

### 2026-06-08 — Added a TestOpponentHistoryTrackingAndScoring test class (plus a small_roster_planner_and_plan fixture forcing repeat matchups over a long season window) covering: _opponent_history accumulation from generated games (including cross-checks against recomputed counts and a forced-repeat scenario), _score_candidate_date preferring fresher pairings, _pick_least_recently_grouped preferring subsets that minimize repeat matchups, _month_counts staying within a reasonable spread of the expected per-month average, and presence/range/consistency of the new diversity_score/pairwise_matchup_score/month_balance_score plan metrics.
**Rationale:** Followed the existing FakeScheduler/_build_roster/_all_weekend_dates fixture patterns; added a dedicated small-roster long-season fixture because the default 6-club/4-age-group scenario has enough teams that repeat matchups rarely occur within a season, making it unsuitable for exercising _opponent_history accumulation directly.
**Findings:** Full suite now 89 passed (up from 82), 1 skipped, 0 failed — all new opponent-history/scoring/month-balance tests pass alongside the existing season-planner suite.
LESSONS: When testing greedy heuristics that read accumulated planner state (_opponent_history, _grouped_with, _invite_counts), reset those dicts to a controlled baseline before seeding test-specific values — leftover real history from build_plan's full run can silently dominate the comparison and invert expected orderings (caught a test failure this way: 5.0 < 3.0 because an unrelated pair already had higher real history than the seeded pair).
**Files:** tests/test_season_planner.py (+169/-0)
**Commit:** 26ff6a6 (hockey)

## Verification Report
**Date:** 2026-06-08

| Criterion | Verdict | Notes |
|-----------|---------|-------|
| Generated plans do not schedule the same pair of teams more than once when an alternative with no prior matchup is available | PASS | _opponent_history tracks pair counts; _pick_least_recently_grouped/_score_candidate_date prefer fresh pairings; tests test_pick_least_recently_grouped_prefers_subset_with_fewer_repeat_matchups and test_score_candidate_date_prefers_fewer_repeat_matchups pass |
| SeasonPlan has a diversity metric and month-balance metric computed from real opponent-history and per-month counts, not co-attendance alone | PASS | models.py defines pairwise_matchup_score and month_balance_score, computed in season_planner.py from _opponent_history/_month_counts; tests confirm presence and correctness |
| A multi-month plan has no single month holding a disproportionately larger share of tournaments than the expected per-month average | PASS | _month_counts tracker plus month-load penalty in _score_candidate_date drive selection; test_month_counts_stay_within_a_reasonable_spread passes |
| print_diversity_summary console output reports both the pairwise-matchup diversity figure and month-to-month load balance figure | PASS | rich_output.py renders 'Kampmangfold ... pairwise_matchup_score' and 'Månedsbalanse ... month_balance_score' lines in the summary panel |
| Tests in test_season_planner.py covering opponent-history tracking, candidate-date scoring, and month-load balancing pass | PASS | TestOpponentHistoryTrackingAndScoring class (7 test methods) covers all three areas; full suite: 89 passed, 1 skipped, 0 failed |

**Shell checks (ps-verify-plan):** all passed
```
no embedded shell checks found
```
**Git history:** 6/6 tasks have matching commits
**Tests:** passed (89 passed, 1 skipped, 0 failed)
