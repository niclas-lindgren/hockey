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

- [ ] Score and rank candidate dates by projected matchup diversity and month balance
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add a `_score_candidate_date(date, age_group, candidate_participants)` method that combines (a) a penalty derived from `_opponent_history` for how many repeat matchups the candidate participant set would create and (b) a penalty derived from `_month_counts` for how far the candidate date's month is above the season's per-month average; wire this scoring into `_pick_spread_dates` (or the per-bucket "best date" selection within it) so the planner ranks/picks dates using this combined score rather than spread-only bucket selection.

- [ ] Use opponent-history scoring to drive participant selection
  - Files: tournament_scheduler/season_planner.py
  - Approach: Replace or extend `_pick_least_recently_grouped` in `_select_participants` with a selection that, among otherwise-eligible candidate teams, prefers the subset minimizing total repeat-matchup count per `_opponent_history` (falling back to the existing least-recently-grouped tie-break when opponent history is equal), so that "avoid repeat matchups where alternatives exist" is enforced directly at selection time rather than only measured after the fact.

- [ ] Replace the aggregate diversity score with a pairwise-matchup + month-balance metric
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/models.py, tournament_scheduler/utils/rich_output.py
  - Approach: Rework `_diversity_score` to compute a metric grounded in `_opponent_history` (e.g. fraction of scheduled matchups that are first-time pairings, or average repeat count per pair) plus a month-balance figure derived from `_month_counts`, store both on `SeasonPlan` (extending the existing `diversity_score` field / adding a `month_balance_score` field in models.py), and update `print_diversity_summary` in rich_output.py to render both figures so they're visible in console output alongside the existing arena-count summary.

- [ ] Add unit tests for opponent-history tracking, scoring, and month balance
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
**Commit:** [pending — fill after commit]
