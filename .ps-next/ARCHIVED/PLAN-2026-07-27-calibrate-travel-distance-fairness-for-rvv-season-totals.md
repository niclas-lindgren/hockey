# Plan: Calibrate travel-distance fairness for RVV season totals
**Goal:** The fairness gate treats cumulative team travel as a season-total metric with a realistic default threshold, so balanced plans can pass instead of warning by construction.
**Created:** 2026-07-27
**Intent:** Keep the travel metric meaningful for the current nine-club RVV geography and align the code and docs with how the metric is actually computed.

## Tasks
- [x] Recalibrate the default cumulative travel threshold and centralize the constant
  - Files: tournament_scheduler/fairness_scoring.py, tournament_scheduler/season_planner.py
  - Approach: move the default `max_team_travel_km` into the shared fairness-threshold definition, raise it to a season-total value that matches real RVV runs, and clarify the metric comment/detail so it is obvious the number applies to total season travel, not a single trip.
- [x] Refresh the rules-report wording and add a regression test for the new boundary
  - Files: docs/rvv-miniputt-rules-report.md, tests/test_season_planner.py
  - Approach: update the rules-report threshold table to match the new travel default and add a focused fairness-gate test that monkeypatches cumulative travel totals at the threshold and just above it, asserting pass-at-threshold and warn-above-threshold behavior.

## Notes
The current code already computes `travel_distance` from `compute_team_travel_distances(plan)`, i.e. cumulative season travel across away tournaments. The existing 700 km default is too low for a full RVV season and should not be interpreted as a per-trip cap.

## Acceptance Criteria
- [ ] The default fairness threshold for `max_team_travel_km` reflects cumulative season travel and no longer makes balanced plans warn by default.
- [ ] The rules-report docs describe the updated travel threshold consistently with the code.
- [ ] A test proves the travel metric passes at the threshold and warns above it.

## Log


### 2026-07-27 — Refresh the rules-report wording and add a regression test for the new boundary
**Done:** Updated the rules-report threshold line to match the new season-total travel default and added a regression test that proves the travel metric passes exactly at the boundary and warns one kilometer above it.
**Rationale:** The docs need to match the calibrated default, and the regression test locks down the intended cumulative-season semantics so the threshold doesn't drift back toward a per-trip guess.
**Findings:** The new test monkeypatches cumulative travel totals, so the fairness gate now proves pass-at-threshold / warn-above-threshold behavior for the season-total metric. Plan-drift reported the earlier code files as unplanned on this task because they were already completed in the previous task and remained in the same working tree.
**Files:** docs/rvv-miniputt-rules-report.md, tests/test_season_planner.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/season_planner.py
**Commit:** not committed
### 2026-07-27 — Recalibrate the default cumulative travel threshold and centralize the constant
**Done:** Raised the default `max_team_travel_km` from 700 to a season-total value suitable for full RVV seasons and made `season_planner.py` consume the shared fairness-threshold dict instead of carrying its own copy.
**Rationale:** The travel metric already measures cumulative season travel, so the old number behaved like a per-trip guess and produced noise on otherwise balanced plans.
**Findings:** `travel_distance` is cumulative across away tournaments; the fairness detail now says so explicitly, and the default threshold is centralized in `fairness_scoring.py` so the planner and fairness gate stay in sync.
**Files:** tournament_scheduler/fairness_scoring.py, tournament_scheduler/season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
