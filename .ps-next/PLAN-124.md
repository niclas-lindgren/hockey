# Plan: Re-evaluate fairness warnings after manual adjustments
**Goal:** Re-evaluate fairness warnings after manual adjustments: manual_adjustment_workflow.py currently patches the plan without re-running game count spread, hosting deviation, or month load checks — add a post-patch warnings pass
**Created:** 2026-06-17
**Intent:** Ensure organizers see an up-to-date picture of plan fairness immediately after applying manual adjustments, so violations introduced or resolved by the patch are surfaced without requiring a full pipeline re-run.
**Backlog-ref:** 124

## Tasks
- [x] Added post_patch_warnings: list[str] field with default_factorylist to the UpdateResult dataclass so callers can receive structured warning data after patch operations. — 2026-06-17
  - Files: tournament_scheduler/pipeline/tournament_updater.py
  - Approach: Extend the UpdateResult dataclass with a `post_patch_warnings: list[str]` field (default empty list) so callers receive structured warning data alongside the existing conflicts and changes fields.

- [x] Added _collect_post_patch_warnings(planner, plan) to ManualAdjustmentWorkflow, calling scan_game_count_warnings, scan_hosting_warnings, scan_month_load_warnings, and scan_arena_day_collision_warnings, collecting results into deduplicated warning strings. — 2026-06-18
  - Files: tournament_scheduler/pipeline/manual_adjustment_workflow.py, tournament_scheduler/warnings.py
  - Approach: Add a private method that calls `scan_game_count_warnings(planner, ...)`, `scan_hosting_warnings(planner, plan)`, `scan_month_load_warnings(planner, expected_per_month, ...)`, and `scan_arena_day_collision_warnings(plan)` using the already-primed planner and updated plan; collect and deduplicate the returned warning strings.

- [x] Called _collect_post_patch_warnings(planner, plan) in apply() after _refresh_plan_metadata() and passed the result as post_patch_warnings on the returned UpdateResult. — 2026-06-18
  - Files: tournament_scheduler/pipeline/manual_adjustment_workflow.py
  - Approach: After `_refresh_plan_metadata()` completes inside `apply()`, call `_collect_post_patch_warnings()` and assign the result to `UpdateResult.post_patch_warnings`, ensuring the planner state is already fresh (it is, because `_prime_planner()` runs before `_refresh_plan_metadata()`).

- [x] Added a loop in both update_command.py and review_command.py that calls TournamentOutput.print_warning(w) for each entry in result.post_patch_warnings, displayed between the summary line and the plan-path info line. — 2026-06-18
  - Files: tournament_scheduler/pipeline/manual_adjustment_workflow.py, tournament_scheduler/utils/rich_output.py
  - Approach: After `apply()` returns, check `result.post_patch_warnings` and print each warning using the Rich output helper (following the existing warning print pattern used in `season_command.py`), so organizers see the warnings without inspecting the returned dict directly.

- [ ] Add regression tests for post-patch warning scanning
  - Files: tests/test_manual_adjustment_workflow.py
  - Approach: Write tests that apply a manual adjustment that introduces a game count spread or hosting deviation violation, then assert that `UpdateResult.post_patch_warnings` is non-empty and contains the expected warning string; also assert that the no-violation case returns an empty list.

## Notes
- The planner is already primed with plan tournament data inside `apply()` via `_prime_planner()`, so warning scanners can use its state directly.
- `scan_game_count_warnings` and `scan_month_load_warnings` append to `planner.warnings` (they return None); collect from `planner.warnings` after calling them.
- `scan_arena_day_collision_warnings` returns a `List[str]` directly.
- Keep all warning text Norwegian-language consistent with existing warning output.

## Acceptance Criteria
- [ ] After applying manual adjustments, the system runs game count spread warnings and outputs any new warnings to the caller via UpdateResult.
- [ ] When manual adjustments are applied, the system re-runs hosting deviation checks and includes any new warnings in the returned result.
- [ ] The manual adjustment workflow produces updated fairness warnings after patching plans, ensuring month load checks are executed and reported.
- [ ] Applying manual adjustments causes the system to report any newly detected arena day collision warnings as part of the post-patch validation.
- [ ] Regression tests pass for both the case where post-patch warnings are triggered and the case where no violations are present.

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-17 — Added post_patch_warnings: list[str] field with default_factorylist to the UpdateResult dataclass so callers can receive structured warning data after patch operations.
**Rationale:** Straightforward dataclass extension; no alternatives needed.
**Findings:** All 418 tests pass with no changes required elsewhere.
LESSONS: none
**Files:** tournament_scheduler/pipeline/tournament_updater.py (+1/-0)
**Commit:** f98fca3 (hockey)

### 2026-06-18 — Added _collect_post_patch_warnings(planner, plan) to ManualAdjustmentWorkflow, calling scan_game_count_warnings, scan_hosting_warnings, scan_month_load_warnings, and scan_arena_day_collision_warnings, collecting results into deduplicated warning strings.
**Rationale:** Imported the four scan functions from warnings.py; formatted tuple-based warnings into Norwegian strings matching existing CLI patterns; deduplicated by ordered set.
**Findings:** All 418 tests pass; method returns list[str] ready for wiring into apply() in the next task.
LESSONS: none
**Files:** tournament_scheduler/pipeline/manual_adjustment_workflow.py (+66/-0)
**Commit:** c278ff4 (hockey)

### 2026-06-18 — Called _collect_post_patch_warnings(planner, plan) in apply() after _refresh_plan_metadata() and passed the result as post_patch_warnings on the returned UpdateResult.
**Rationale:** none
**Findings:** All 418 tests pass; post_patch_warnings is now populated on every apply() call.
LESSONS: none
**Files:** tournament_scheduler/pipeline/manual_adjustment_workflow.py (+2/-0)
**Commit:** 8945ca5 (hockey)

### 2026-06-18 — Added a loop in both update_command.py and review_command.py that calls TournamentOutput.print_warning(w) for each entry in result.post_patch_warnings, displayed between the summary line and the plan-path info line.
**Rationale:** none
**Findings:** All 418 tests pass; warnings now surface to the organizer immediately after manual adjustments are applied in both CLI paths.
LESSONS: none
**Files:** tournament_scheduler/cli/review_command.py (+2/-0), tournament_scheduler/cli/update_command.py (+2/-0)
**Commit:** [pending — fill after commit]
