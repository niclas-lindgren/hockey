# Plan: Ignore unavailable calendars in hosting fairness
**Goal:** Missing or unavailable calendar sources are only noted, not counted as hosting-fairness failures, so pre-season runs no longer stay ROUGH for clubs we cannot scrape yet.
**Created:** 2026-06-23
**Intent:** Pre-season is incomplete by design; the planner should assess fairness only for clubs with real calendar coverage and surface the missing clubs as a warning instead of a fail.

## Tasks
- [x] Exclude clubs without scraped calendar coverage from hosting fairness scoring
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/warnings.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/cli/reporting.py, tests/test_season_planner.py
  - Approach: Track the set of clubs present in `events_by_club`, ignore clubs outside that set when computing hosting deviation / hosting warnings, and add a dedicated warning/metric that lists excluded clubs so the gap is visible in the plan.
- [x] Add regression tests for missing-calendar exclusion
  - Files: tests/test_season_planner.py
  - Approach: Cover a roster where one club has no `events_by_club` entry and assert that hosting deviation no longer fails because of that club, while the plan still reports the missing calendar coverage.

## Notes
- The Stage 2 checkpoint already omits zero-event / unavailable sources from `events_by_club`, so that map can drive the exclusion logic.
- Keep the change narrow: this should soften fairness scoring, not hide other real hosting imbalances.

## Acceptance Criteria
- [ ] A season plan with one club missing calendar data no longer gets `fairness_gate.status = fail` solely because that club hosted 0 tournaments.
- [ ] The plan reports an explicit warning or metric naming the excluded club(s).
- [ ] Tests covering the missing-calendar case pass.

## Log


### 2026-06-23 — Add regression tests for missing-calendar exclusion
**Done:** Added a regression test showing a club without `events_by_club` coverage is excluded from hosting-deviation failures while still being surfaced as a missing-calendar warning.
**Rationale:** This locks in the intended pre-season behavior and protects against reintroducing a fail on unavailable calendars.
**Findings:** The test uses a minimal roster with one available club and one unavailable club, then asserts hosting_deviation stays pass, the overall gate becomes warn, and the excluded club is named in the warning path.
**Files:** tests/test_season_planner.py
**Commit:** not committed
### 2026-06-23 — Exclude clubs without scraped calendar coverage from hosting fairness scoring
**Done:** Hosting fairness now ignores clubs that have no scraped calendar coverage, and the plan/status output explicitly calls out the excluded clubs as a warning instead of failing the gate.
**Rationale:** Pre-season calendars are incomplete by design, so missing sources should be visible but not treated as real hosting-fairness failures.
**Findings:** The Stage 2 checkpoint only exposes clubs with actual event data in events_by_club, so that key is the right availability signal. The gate still stays non-pass for other real balance issues, but missing calendar coverage no longer forces a fail.
**Files:** tournament_scheduler/season_planner.py, tournament_scheduler/warnings.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/cli/reporting.py, tests/test_season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->