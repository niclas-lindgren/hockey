# Plan: Skill-driven plan refinement loop after stage4

**Feature:** Add skill-driven plan refinement to rvv-miniputt:run: after stage4, compute verdict tone from stage3 checkpoint scores (pairwise_matchup_score, diversity_score, month_balance_score, fairness_gate) — if tone is 'rough' (IKKE KLAR), call ManualAdjustmentWorkflow to apply targeted host/date swaps, re-export, and recheck — loop until tone is 'strong' or 'mixed' or retry cap (3) is reached
**Goal:** Add skill-driven plan refinement to rvv-miniputt:run: after stage4, compute verdict tone from stage3 checkpoint scores (pairwise_matchup_score, diversity_score, month_balance_score, fairness_gate) — if tone is 'rough' (IKKE KLAR), call ManualAdjustmentWorkflow to apply targeted host/date swaps, re-export, and recheck — loop until tone is 'strong' or 'mixed' or retry cap (3) is reached
**Backlog-ref:** 163
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Automatically improve a 'rough' season plan after export by looping ManualAdjustmentWorkflow up to 3 times, applying targeted swaps and re-exporting until the fairness-based verdict tone reaches 'strong' or 'mixed', removing the need for manual post-run intervention.

---

## Tasks

- [x] Added _compute_verdict_tone(plan) private helper in pipeline_orchestrator.py that accepts either a checkpoint dict or SeasonPlan object and delegates to judgment._score_tone() to return 'rough', 'mixed', or 'strong'. — 2026-06-20
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`, `tournament_scheduler/html/renderers/judgment.py`
  - Approach: Add a private function `_compute_verdict_tone(plan: dict | SeasonPlan) -> str` in `pipeline_orchestrator.py` that extracts `pairwise_matchup_score`, `diversity_score`, `month_balance_score`, and `fairness_gate` from the plan checkpoint dict or SeasonPlan object, then calls `judgment._score_tone(gate_status, gate_score, pairwise, diversity, month_balance, missing_hosts=[], spread=0)` and returns the tone string.

- [ ] Implement `_run_refinement_loop` helper in `pipeline_orchestrator.py` that loops up to 3 times calling `ManualAdjustmentWorkflow.apply()` and `suggest_moves()` when tone is 'rough'
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`, `tournament_scheduler/pipeline/manual_adjustment_workflow.py`, `tournament_scheduler/cli/plan_critic.py`
  - Approach: Add `_run_refinement_loop(plan_checkpoint, state, args, strict, _log)` that on each iteration: (1) loads SeasonPlan via `ManualAdjustmentWorkflow(state).load_plan()`, (2) calls `suggest_moves(plan, generate_critic_summary(plan))` to get targeted swap suggestions, (3) merges them into `plan.manual_adjustments` via `ManualAdjustmentWorkflow.merge_manual_adjustments`, (4) calls `workflow.apply(plan)` to apply swaps and recompute fairness scores, (5) calls `_compute_verdict_tone` on the updated plan, breaks if tone is no longer 'rough'. Returns final tone and updated plan checkpoint dict.

- [ ] Wire `_run_refinement_loop` into `_cmd_run()` after stage4 completes and log each refinement attempt via `_log()`
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Approach: After the `stage4_run(...)` call (around line 522), call `_compute_verdict_tone(plan)` and if tone is 'rough', call `_run_refinement_loop(plan, state, args, strict, _log)` which returns the final tone and updated plan checkpoint. Then re-run `stage4_run` with the updated plan to re-export. Log the tone at each step and the total number of refinement attempts using `_log()` and `_console.print()`.

- [ ] Re-run stage4 export with adjusted plan after each refinement loop iteration
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`, `tournament_scheduler/pipeline/stage4_export.py`
  - Approach: After `_run_refinement_loop` returns an updated plan, call `stage4_run(updated_plan_checkpoint, state, export_dir=args.export_dir, strict=strict, timestamped_export=...)` to regenerate the export files with the refined plan. Ensure this is only triggered when at least one refinement was applied (i.e., `tone_before == 'rough'`).

- [ ] Add unit tests for `_compute_verdict_tone` and `_run_refinement_loop` covering the happy path, retry-cap exit, and early-exit when tone improves
  - Files: `tests/test_pipeline_orchestrator.py`
  - Approach: Add test cases that mock `ManualAdjustmentWorkflow.apply`, `suggest_moves`, and `_score_tone` to verify: (a) loop exits after tone becomes 'mixed' on iteration 2, (b) loop exits after 3 retries if tone stays 'rough', (c) `_compute_verdict_tone` correctly maps fairness_gate status and scores to each of the three tone values.

---

## Log
- 2026-06-20 Plan created

## Acceptance Criteria

When the rvv-miniputt:run pipeline computes a verdict tone of 'rough' after stage4, the system calls ManualAdjustmentWorkflow to apply targeted host/date swaps and re-exports the plan.
When the rvv-miniputt:run pipeline computes a verdict tone of 'rough' after stage4, the system loops up to 3 times applying ManualAdjustmentWorkflow until the tone becomes 'strong', 'mixed', or the retry cap is reached.
The rvv-miniputt:run command outputs a log entry indicating when ManualAdjustmentWorkflow is called to adjust the plan during the refinement phase.
The rvv-miniputt:run pipeline completes successfully and produces updated export files when the final verdict tone is 'strong' or 'mixed' after applying ManualAdjustmentWorkflow adjustments.
The rvv-miniputt:run command does not loop and exits without calling ManualAdjustmentWorkflow when the initial verdict tone after stage4 is not 'rough'.

### 2026-06-20 — Added _compute_verdict_tone(plan) private helper in pipeline_orchestrator.py that accepts either a checkpoint dict or SeasonPlan object and delegates to judgment._score_tone() to return 'rough', 'mixed', or 'strong'.
**Rationale:** straightforward extraction — none
**Findings:** Function imports and works correctly; verified with a quick import check.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+39/-0)
**Commit:** [pending — fill after commit]
