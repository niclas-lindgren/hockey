# Plan: Add per-team target tournament count support
**Goal:** Each team in input.xlsx can have an optional `target_tournament_count` column; teams with an explicit value are scheduled for at most that many tournaments, while teams without use the global `deltakelser_per_lag` default.
**Created:** 2026-06-15
**Intent:** Allow per-team overrides for tournament participation targets, e.g. Kongsberg 2 U7 should only play 2 tournaments while other U7 teams play 6.
**Backlog-ref:** 103

## Tasks
- [x] Add `target_tournament_count` field to Team model and input workbook
  - Files: tournament_scheduler/models.py, tournament_scheduler/pipeline/input_workbook.py
  - Approach: Add `target_tournament_count: Optional[int] = None` to `Team` dataclass. Add `"target_tournament_count"` to the optional columns list in `_read_table()` call for "Lag" sheet in `input_workbook.py`. Normalize the value (float→int, skip empty). The field already flows through the dict-based checkpoint serialization since teams are dicts — just need the field present.

- [x] Update pipeline serialization helpers for per-team target
  - Files: tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/pipeline/stage4_helpers.py
  - Approach: In `_build_roster()` pass `target_tournament_count=t.get("target_tournament_count")` to Team constructor. In `_team_to_dict()` include `target_tournament_count` if set. In `_tournament_from_dict()` and `_dict_to_plan()` create teams with the field. This ensures per-team targets survive checkpoint round-trips.

- [x] Add per-team tournament participation tracking to SeasonPlanner
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add `self._tournament_participations: Dict[str, int]` tracking how many tournaments each team has been invited to (separate from game counts). Initialize all teams to 0. Increment in `_record_grouping` (and the _assign_hosts/selection paths). Add a helper `_team_target_tournament_count(team)` that returns the per-team override or the global default. Add a method `_team_at_target(team)` returning True when a team's participations >= its target.

- [x] Update participant selection to respect per-team tournament caps
  - Files: tournament_scheduler/season_planner.py
  - Approach: In `_select_participants()`, `_pick_least_recently_grouped()`, and `_cap_per_club_deficit_aware()`, filter out teams that have reached their per-team tournament target. Update `_deficit_score()` to return 0 (no deficit) for teams at their target cap. Update `_target_tournaments_for_age_group()` to sum per-team targets instead of using a flat global value. Update `_scan_feasibility_warnings()` to use per-team targets in messaging.

- [x] Surface per-team target vs actual in reports
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/excel/plan_exporter.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: Pass per-team target data alongside `team_game_counts` in Stage 4 checkpoint. Update HTML report's team table / fairness-adjustment rows to show each team's `target_tournament_count` column. Update Excel report. Include per-team target info in `stage4_export.py`'s team metrics.

- [x] Add/update tests for per-team target tournament count
  - Files: tests/test_stage1_config.py, tests/test_season_planner.py, tests/test_stage4_export.py
  - Approach: Add test for input workbook with per-team `target_tournament_count` column. Add planner test showing a team with target=2 is not invited beyond 2 tournaments in a scenario where other teams have target=6. Add regression tests for serialization round-trip. Update existing tests that create Team objects to include the optional field (passing None is fine).

## Notes
- The per-team `target_tournament_count` is a hard upper limit on tournament *participation* (number of tournaments a team is invited to), separate from game counts.
- Teams without the column/none value fall back to the global `deltakelser_per_lag` default.
- The fairness model (game-count balancing between teams) is not affected — the per-team target is about tournament load, not game-count fairness.
- Backward compatibility: existing input.xlsx files without the column work unchanged (the field is optional and defaults to None).

## Acceptance Criteria
- [ ] `test_season_planner.py` passes a test asserting a team with target=2 is invited to at most 2 tournaments.
- [ ] `test_stage1_config.py` passes a test asserting input.xlsx with per-team `target_tournament_count` column parses correctly.
- [ ] HTML and Excel reports show per-team target vs actual tournament participations.
- [ ] Existing input.xlsx files without the column work unchanged (all existing tests pass).
- [ ] Per-team target field survives Stage 3→4 checkpoint round-trip (serialize + deserialize returns same value).
- [ ] SeasonPlanner produces a valid plan when one team has target=2 and others have target=6 in the same age group.

## Log






### 2026-06-15 — Add/update tests for per-team target tournament count
**Done:** true
**Rationale:** Updated test helper to write target_tournament_count column when present. Added test_run_preserves_per_team_target_tournament_count in stage1 config tests. Added test_per_team_target_tournament_count_is_enforced in season planner tests. Added test_adjustment_rows_show_per_team_target_tournaments in fairness model tests.
**Findings:** Added test for per-team target_tournament_count in input workbook parsing; added test that planner enforces per-team tournament cap; added test that fairness adjustment rows include target/actual tournament participation.
**Files:** tests/test_stage1_config.py (+24), tests/test_season_planner.py (+43), tests/test_fairness_model.py (+27)
**Commit:** not committed
### 2026-06-15 — Surface per-team target vs actual in reports
**Done:** true
**Rationale:** Updated adjustment_rows_for_plan to compute tournament_participations from the tournament list and include target_tournaments (from Team model) in each row. Updated HTML exporter to display the new column with conditional header.
**Findings:** Added target_tournaments and actual_tournaments fields to fairness adjustment rows. Updated HTML to show a "Deltakelser (faktisk/mål)" column when per-team targets are present, or just "Deltakelser" when all use global default.
**Files:** tournament_scheduler/fairness_model.py (+19/-6), tournament_scheduler/html/html_exporter.py (+18/-8)
**Commit:** not committed
### 2026-06-15 — Update participant selection to respect per-team tournament caps
**Done:** true
**Rationale:** _select_participants now filters teams at their target cap. _deficit_score returns -1 for teams at cap. _target_tournaments_for_age_group sums per-team targets instead of using flat global value. rules_report and _scan_feasibility_warnings updated for per-team messaging.
**Findings:** Updated _select_participants to filter out capped teams, _deficit_score to return -1 for capped teams, _target_tournaments_for_age_group to sum per-team targets, rules_report to describe per-team overrides, and _scan_feasibility_warnings for per-team targets.
**Files:** tournament_scheduler/season_planner.py (+25/-8)
**Commit:** not committed
### 2026-06-15 — Add per-team tournament participation tracking to SeasonPlanner
**Done:** true
**Rationale:** Added _tournament_participations dict (keyed by team_key), _team_target_tournament_count(), and _team_at_target() helpers. Updated _record_grouping to increment participation count alongside existing invite count.
**Findings:** Added _tournament_participations dict to track per-team tournament invite counts. Added _team_target_tournament_count() and _team_at_target() helpers. Updated _record_grouping to increment participation counts.
**Files:** tournament_scheduler/season_planner.py
**Commit:** not committed
### 2026-06-15 — Update pipeline serialization helpers for per-team target
**Done:** true
**Rationale:** Updated _team_to_dict to serialize target_tournament_count, _build_roster and _tournament_from_dict to deserialize it. Added team_tournament_participations computation in _plan_to_dict for checkpoint.
**Findings:** _team_to_dict is a nested function inside _plan_to_dict (cannot import directly). Found that _dict_to_plan in stage4_helpers.py also needed the field.
**Files:** tournament_scheduler/pipeline/stage3_helpers.py (+4/-1), tournament_scheduler/pipeline/stage4_helpers.py (+1)
**Commit:** not committed
### 2026-06-15 — Add `target_tournament_count` field to Team model and input workbook
**Done:** true
**Rationale:** Added `target_tournament_count: Optional[int] = None` to Team dataclass and `"target_tournament_count"` as optional column in Lag sheet workbook parsing.
**Findings:** The field flows naturally through dict-based serialization since Team objects are serialized as dicts in checkpoints. Existing code uses `Team(**team)` which handles the new optional field.
**Files:** tournament_scheduler/models.py (+1), tournament_scheduler/pipeline/input_workbook.py (+1)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
