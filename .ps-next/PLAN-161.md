# Plan: Add --iterations N flag to stage3_planning

**Feature:** Add --iterations N flag to stage3_planning: run the planner N times with different random seeds and keep the plan with the best composite score (pairwise + diversity + month_balance). This unlocks the self-improvement loop in rvv-miniputt:run where the skill re-runs stage3+4 until the judgment verdict is no longer IKKE KLAR.
**Goal:** Add --iterations N flag to stage3_planning: run the planner N times with different random seeds and keep the plan with the best composite score (pairwise + diversity + month_balance). This unlocks the self-improvement loop in rvv-miniputt:run where the skill re-runs stage3+4 until the judgment verdict is no longer IKKE KLAR.
**Backlog-ref:** 161
**Constraints:** none
**Date:** 2026-06-19
**Intent:** Enable multi-seed planning so the pipeline can automatically find a higher-quality plan by trying N randomized variations and surfacing the best composite fairness score, which is the foundational step for a self-improvement loop that reruns until the plan reaches SOLID or BLANDET judgment.

---

## Tasks

- [x] Added seed: int  None  None parameter to SeasonPlanner.__init__ and _make_planner(); stored self._rng  random.Random(seed) and shuffled age_groups list in build_plan before date assignment. — 2026-06-20
  - Files: `tournament_scheduler/season_planner.py`, `tournament_scheduler/pipeline/stage3_helpers.py`
  - Approach: Add an optional `seed: int | None = None` parameter to `SeasonPlanner.__init__` and use it to initialise a `random.Random` instance that shuffles team/club orderings before each planning pass. Update `_make_planner()` in `stage3_helpers.py` to accept and forward a `seed` keyword argument to `SeasonPlanner`.

- [ ] Implement N-iteration loop with best-score selection in stage3_planning.run()
  - Files: `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: Add an `iterations: int = 1` parameter to `run()`. When `iterations > 1`, loop from `seed=0` to `seed=iterations-1`, call `_make_planner(..., seed=i)` and `planner.build_plan(start_date, end_date)` each time, evaluate the composite score via `build_fairness_gate(planner, plan)["score"]` from `fairness_scoring`, track the best-scoring plan, and write only that plan to the Stage 3 checkpoint. Import `build_fairness_gate` from `..fairness_scoring`.

- [ ] Add --iterations CLI flag to stage3_planning __main__ entry point
  - Files: `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: In the `if __name__ == "__main__"` argparse block, add `parser.add_argument("--iterations", type=int, default=1, help="Run the planner N times with different random seeds and keep the plan with the best composite fairness score.")` and pass `cli_args.iterations` into the `run()` call.

- [ ] Thread --iterations through the pipeline orchestrator
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`, `tournament_scheduler/cli/args.py`
  - Approach: Add `--iterations` (type int, default 1) to the `run` subcommand's argparse definition in `args.py`. In `pipeline_orchestrator.py` `_cmd_run`, pass `iterations=getattr(args, "iterations", 1)` to `stage3_run(...)` at line 482.

- [ ] Add tests for multi-iteration behavior in test_stage3_planning.py
  - Files: `tests/test_stage3_planning.py`
  - Approach: Add test cases that call `run(..., iterations=3)` with canonical config fixtures, assert that the returned checkpoint is non-empty and that the plan's composite score is at least as good as a single-iteration run. Also add a test that verifies `iterations=1` (default) produces identical behavior to the existing tests.

---

## Log
- 2026-06-19 Plan created

## Acceptance Criteria

When the --iterations N flag is provided to stage3_planning, the command runs the planner N times with different random seeds and outputs the plan with the best composite score.
When stage3_planning receives the --iterations N flag, it produces N separate plan attempts and reports which one has the highest composite score based on pairwise, diversity, and month_balance metrics.
If stage3_planning is called with --iterations 3, it runs the planning process three times with distinct random seeds and returns only the plan that achieves the optimal composite score.
The CLI interface for stage3_planning accepts --iterations N as a valid parameter and has a positive integer type constraint.
The stage3_planning process does not modify any existing deterministic behavior when --iterations is not specified, ensuring backward compatibility with current pipeline_orchestrator.py usage.

### 2026-06-20 — Added seed: int  None  None parameter to SeasonPlanner.__init__ and _make_planner(); stored self._rng  random.Random(seed) and shuffled age_groups list in build_plan before date assignment.
**Rationale:** Straightforward parameter threading; age_groups shuffle ensures different ordering per seed which affects date assignment and participant selection tiebreakers via candidates.index(t).
**Findings:** age_groups shuffle in build_plan varies which age groups get first pick of free dates, producing structurally different plans per seed
LESSONS: none
**Files:** season_planner.py (+5/-0), stage3_helpers.py (+2/-0)
**Commit:** [pending — fill after commit]
