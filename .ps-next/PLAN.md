# Plan: Split season_planner.py into focused helper modules
**Goal:** Refactor `tournament_scheduler/season_planner.py` into a thin orchestration facade backed by dedicated participant selection, host assignment, game generation, fairness, warning, and rules-report modules, while keeping behavior unchanged.
**Created:** 2026-06-15
**Intent:** `season_planner.py` is a ~2500-line mixed-concern module. Splitting the planning heuristics into focused modules will make the scheduling logic easier to understand, test, and change without altering the public API.

## Tasks
- [x] Extract participant-selection and host-assignment helpers into dedicated modules
  - Files: tournament_scheduler/participant_selection.py, tournament_scheduler/host_assignment.py, tournament_scheduler/season_planner.py
  - Approach: Move the date/participant/host selection heuristics (`_pick_spread_dates`, `_target_tournaments_for_age_group`, `_next_age_group`, `_select_participants`, `_pick_least_recently_grouped`, `_assign_hosts`, `_find_slot_for_tournament`, and supporting capacity/target helpers) into standalone helper functions or mixin classes, then make `SeasonPlanner` delegate to them.

- [ ] Extract game-generation, fairness-scoring, and warning helpers into dedicated modules
  - Files: tournament_scheduler/game_generation.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/warnings.py, tournament_scheduler/season_planner.py
  - Approach: Move round-robin generation plus `_rebalance_rounds`/`_best_round_subset`, fairness metrics/gate construction, and warning scanners/properties into focused modules. Keep the existing `SeasonPlanner` API by delegating from thin wrapper methods.

- [ ] Extract the rules report into its own module and trim `SeasonPlanner`
  - Files: tournament_scheduler/rules_report.py, tournament_scheduler/season_planner.py
  - Approach: Move `rules_report()` and any report-specific helpers into a standalone module, then remove duplicated logic from `SeasonPlanner` so the class mainly orchestrates the pipeline and exposes compatibility wrappers.

- [ ] Run regression checks and document the refactor
  - Files: tests/test_season_planner.py, .ps-next/PLAN.md
  - Approach: Run the season-planner test suite and verify the refactor does not change behavior. If tests pass, record the results in the PLAN log and keep the public imports working without caller changes.

## Notes
- Preserve the public import path `from tournament_scheduler.season_planner import SeasonPlanner`.
- Avoid circular imports: new helper modules should depend on models/constants, not on `SeasonPlanner` internals except through explicit delegation boundaries.
- Existing tests and CLI call sites use the current `SeasonPlanner` API, including private helpers in some tests, so wrappers must keep method names stable.
- Keep any moved logic behaviorally identical; this refactor is structural only.

## Acceptance Criteria
- [ ] `pytest tests/test_season_planner.py -q` passes without changing test expectations.
- [ ] `python3 -c "from tournament_scheduler.season_planner import SeasonPlanner; print('ok')"` succeeds.
- [ ] `python3 -c "from tournament_scheduler.participant_selection import __name__ as _; from tournament_scheduler.game_generation import __name__ as __; print('ok')"` succeeds.
- [ ] No circular imports are introduced between the new helper modules and `season_planner.py`.

## Log

### 2026-06-15 — Extract participant-selection and host-assignment helpers into dedicated modules
**Done:** Moved the date/host/participant selection logic into `tournament_scheduler/participant_selection.py` and `tournament_scheduler/host_assignment.py`, then made `SeasonPlanner` delegate to those helper modules via thin compatibility bindings.
**Rationale:** This separates the orchestration facade from the heuristic-heavy selection logic without changing the public `SeasonPlanner` API.
**Findings:** The refactor is behavior-preserving; the existing season-planner test suite still passes after the delegation swap.
**Files:** tournament_scheduler/participant_selection.py (+1 new), tournament_scheduler/host_assignment.py (+1 new), tournament_scheduler/season_planner.py (imports + delegation bindings)
**Commit:** 0ad51d9
<!-- pi-next appends entries here after each task -->
