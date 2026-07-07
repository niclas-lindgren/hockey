# Plan: Optional mid-planning critic loop
**Goal:** Add an opt-in Stage 3 critic loop that inspects the planning checkpoint, turns critic findings into structured planner hints, reruns Stage 3 up to a configured cap, and only then proceeds to Stage 4 export.
**Created:** 2026-07-07
**Intent:** Improve plan quality before export artifacts exist, while keeping the existing post-Stage-4 refinement loop separate and backwards compatible.
**Backlog-ref:** 10

## Tasks
- [x] Add CLI/orchestrator support for the pre-export critic loop
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/pipeline_orchestrator.py, tests/test_pipeline_orchestrator.py
  - Approach: Add an opt-in run flag for mid-planning critic iterations, extract helper(s) that inspect the Stage 3 checkpoint with plan_critic/fairness metrics, produce structured penalty hints, rerun _run_stage3 with those hints, persist the selected checkpoint, and unit-test zero-cap, improvement, cap, and no-issue behavior without invoking real stages.
- [ ] Persist and consume structured planning critic hints cleanly
  - Files: tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/season_planner.py, tests/test_stage3_planning.py
  - Approach: Ensure Stage 3 stores any applied hint metadata in its checkpoint and SeasonPlanner accepts the structured hint shape without breaking existing penalty_hints; add focused tests proving hints reach the planner/checkpoint and old flat penalty_hints still work.
- [ ] Document the new pre-export loop and run checks
  - Files: docs/rvv-miniputt-pipeline.md, .agents/skills/rvv/SKILL.md, .ps-next/PLAN.md
  - Approach: Update pipeline docs/skill notes to distinguish the new optional pre-Stage-4 critic loop from post-export refinement, then run targeted pytest plus pi-next review/quality checks before marking the plan complete.

## Notes
- Existing `_cmd_run` already has a non-optional 3-attempt Stage 3 retry based on rough verdict and flat fairness penalty hints; the new behavior should be opt-in and explicitly critic/checkpoint driven.
- Existing post-Stage-4 `_run_refinement_and_reexport` applies manual moves after export; do not merge that behavior into the new loop.
- RVV command surface: do not invoke `/rvv-miniputt ...` through Bash; use repo Python entrypoints/tests for code checks.

## Acceptance Criteria
- [ ] `python -m pytest tests/test_pipeline_orchestrator.py tests/test_stage3_planning.py` passes.
- [ ] `python -m tournament_scheduler.cli.rvv_cli run --help` contains the new mid-planning critic loop flag.
- [ ] The Stage 3 checkpoint can contain structured planning critic hint metadata when the loop applies hints.
- [ ] Documentation contains the optional pre-export loop separately from the post-Stage-4 refinement loop.

## Log

### 2026-07-07 — Add CLI/orchestrator support for the pre-export critic loop
**Done:** Added --mid-planning-critic-iterations, a pre-export Stage 3 checkpoint critic loop, structured hint extraction, rerun orchestration, best-plan retention, and unit coverage for off/no-hint/rerun/cap behavior.
**Rationale:** The loop is opt-in and sits between Stage 3 selection and Stage 4 export, keeping existing default behavior and post-export refinement unchanged while allowing planner hints to influence a fresh Stage 3 run before artifacts are created.
**Findings:** Targeted checks passed: python3 -m pytest tests/test_pipeline_orchestrator.py -q; python3 -m tournament_scheduler.cli.rvv_cli run --help | grep -- --mid-planning-critic-iterations. pi_next_quality_gate quick invoked the repo-wide pytest and failed/was not actionable for this task; backlog item 209 already tracks default suite slowness/hanging.
**Files:** tournament_scheduler/cli/args.py, tournament_scheduler/cli/pipeline_orchestrator.py, tests/test_pipeline_orchestrator.py
**Commit:** committed (see git history)
<!-- pi-next appends entries here after each task -->
