# Plan: Global date-selection optimization
**Goal:** Season planning should rebalance tournament dates across the whole season, not just inside per-age-group greedy buckets.
**Created:** 2026-06-22
**Intent:** Improve month balance, avoid overlapping-age-group collisions, and let date selection feed on accumulated opponent-history pressure before host assignment.
**Backlog-ref:** 193

## Tasks
- [ ] Add a global date-selection optimization pass to SeasonPlanner
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/rules_report.py
  - Approach: factor date selection into a reusable global pass that replays the season schedule in a global best-first order, scoring candidate dates with month-load, overlap, and repeat-matchup pressure; wire build_plan to use the optimized schedule when it beats the existing greedy baseline; update the rules report wording to describe the new season-wide pass.

- [ ] Add regression coverage for the optimized date-selection pass
  - Files: tests/test_season_planner.py
  - Approach: add a deterministic test that compares the existing per-age-group greedy placement against the new global pass on a crafted roster/free-date set, asserting the optimized result improves the composite score and preserves overlap/collision expectations; cover a second small plan-build scenario so the public build_plan path exercises the new pass.

## Notes
- Keep the existing per-age-group helpers available as the fallback/baseline so behavior remains safe if the global pass cannot improve a schedule.
- The optimizer should use only scheduler/planner state already available during planning; no external services or new configuration knobs are needed.
- Because opponent diversity depends on earlier scheduling decisions, the pass needs to simulate schedule state rather than just reorder dates.

## Acceptance Criteria
- [ ] Build plan uses the optimized season-wide date-selection pass when it produces a better schedule than the old bucketed baseline.
- [ ] The rules report mentions the season-wide date-selection optimization instead of implying all date choice is purely per-age-group greedy.
- [ ] Tests prove the optimized schedule improves the composite score in a crafted scenario and still passes the overlap/collision checks.

## Log
<!-- pi-next appends entries here after each task -->
