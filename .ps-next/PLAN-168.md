# Plan: Fix refinement loop silently dropping moves
**Goal:** Fix refinement loop silently dropping moves — `requested_adjustments` is built in `_run_refinement_loop` (pipeline_orchestrator.py ~line 122) but never applied back to the plan, so all manual moves from refinement iterations are discarded
**Created:** 2026-06-20
**Intent:** Ensure the automated refinement loop actually moves tournaments to their suggested new dates so plan quality improves across iterations instead of silently doing nothing.
**Backlog-ref:** 168

## Tasks
- [x] Fixed the auto_moves loop to actually append old_date to banned_dates in requested_adjustments so adjustments are propagated to merge_manual_adjustments. — 2026-06-20
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Approach: In the auto_moves loop (lines 197–205), change `requested_adjustments.setdefault("banned_dates", [])` to actually append `move.get("old_date")` to the list so it is non-empty when passed to `merge_manual_adjustments`.

- [x] Auto-fixable moves with both tournament_id and new_date now call TournamentUpdater.move_date directly; moves without tournament_id fall back to banning the old date. — 2026-06-20
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`, `tournament_scheduler/pipeline/manual_adjustment_workflow.py`, `tournament_scheduler/pipeline/tournament_updater.py`
  - Approach: For each auto-fixable move that has both `tournament_id` and `new_date`, call the existing TournamentUpdater move API directly (similar to how `--update-tournament` works in `update_command.py`) so tournaments land on the specific suggested date, not an arbitrary replacement chosen by `_find_replacement_date()`.

- [ ] Verify workflow.apply() is invoked with non-empty adjustments and persists the checkpoint
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Approach: After applying fixes, add a guard that skips `workflow.apply()` and `write_updated_checkpoint()` when `requested_adjustments` is effectively empty (all lists empty) to avoid a no-op apply that resets scores.

- [ ] Add unit tests asserting requested_adjustments is populated and apply() receives non-empty adjustments
  - Files: `tests/test_pipeline_orchestrator.py`
  - Approach: Extend the existing `_run_refinement_loop` test fixtures to supply moves with `old_date` and `new_date` set; assert that the `apply` mock is called with a `plan_obj` whose `manual_adjustments["banned_dates"]` is non-empty.

## Notes
Root cause: in `_run_refinement_loop` (pipeline_orchestrator.py lines 197–211), the loop body calls `requested_adjustments.setdefault("banned_dates", [])` but never appends the old_date — so `requested_adjustments` is always `{"banned_dates": []}` (empty list) or `{}`. `merge_manual_adjustments` merges nothing and `apply()` has no dates to act on. Additionally, even with the correct old_date banned, `apply()` picks a random replacement date via `_find_replacement_date()` rather than the specific `new_date` returned by `suggest_moves`.

`suggest_moves` return keys: `tournament_id`, `new_date`, `old_date`, `can_auto_fix`, `reason`.
`ManualAdjustmentWorkflow.merge_manual_adjustments` supported keys: `locked_dates`, `banned_dates`, `pinned_tournament_ids`, `forced_host_clubs`, `excluded_host_clubs`.

## Acceptance Criteria
- [ ] After the fix, `requested_adjustments["banned_dates"]` contains at least one date when `suggest_moves` returns auto-fixable moves with a non-null `old_date`.
- [ ] `workflow.apply()` is not called when `requested_adjustments` has no non-empty lists (empty-adjustment guard is in place).
- [ ] Tournaments targeted by the refinement loop are updated to the specific `new_date` from `suggest_moves`, not a random replacement date.
- [ ] Tests in `tests/test_pipeline_orchestrator.py` pass and include at least one assertion that `plan_obj.manual_adjustments` has a non-empty `banned_dates` after a refinement iteration with auto-fixable moves.

## Log
<!-- PS:next appends entries here after each task is executed -->

### 2026-06-20 — Fixed the auto_moves loop to actually append old_date to banned_dates in requested_adjustments so adjustments are propagated to merge_manual_adjustments.
**Rationale:** The dict was initialized with setdefault but old_date was never appended — adding .append(old_date) after the setdefault call fixes the silent no-op.
**Findings:** banned_dates list now populated correctly; adjustments will be applied in subsequent refinement iterations.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+4/-2)
**Commit:** 3c371c3 (hockey)

### 2026-06-20 — Auto-fixable moves with both tournament_id and new_date now call TournamentUpdater.move_date directly; moves without tournament_id fall back to banning the old date.
**Rationale:** Direct move_date call ensures tournaments land on the critic-suggested date instead of an arbitrary replacement from _find_replacement_date().
**Findings:** TournamentUpdater.move_date called per auto-fixable move; fallback banned_dates path retained for moves without tournament_id.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+37/-11)
**Commit:** [pending — fill after commit]
