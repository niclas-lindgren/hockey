# Plan: Stage 3 checkpoint stores game_count_spread_by_age_group per age group
**Goal:** Stage 3 should compute game_count_spread_by_age_group per age group and store it in the checkpoint instead of leaving it None; the stored global game_count_spread is misleading
**Created:** 2026-06-22
**Intent:** Replace the misleading global game_count_spread in the Stage 3 checkpoint with per-age-group spread values so that plan_critic.py and other consumers can validate fairness correctly per age group.
**Backlog-ref:** 186

## Tasks
- [x] Added game_count_spread_by_age_group to _plan_to_dict checkpoint dict in stage3_helpers.py — 2026-06-22
  - Files: tournament_scheduler/pipeline/stage3_helpers.py
  - Approach: Add `"game_count_spread_by_age_group": plan.game_count_spread_by_age_group` to the dict returned by `_plan_to_dict`, following the existing pattern for `"game_count_spread"`.
- [x] Added game_count_spread_by_age_group deserialization in _dict_to_plan in stage4_helpers.py — 2026-06-22
  - Files: tournament_scheduler/pipeline/stage3_helpers.py
  - Approach: In `_dict_to_plan`, read `d.get("game_count_spread_by_age_group", {})` and pass it to the `SeasonPlan` constructor, mirroring how `game_count_spread` is currently read on the adjacent line.
- [x] plan_critic.py now uses stored spread_by_ag with inline fallback; always checks per age group and only falls back to global spread when no age-group mapping is available — 2026-06-22
  - Files: tournament_scheduler/cli/plan_critic.py
  - Approach: Replace the fallback-to-global path in plan_critic.py (lines 118-130) so that when `plan.game_count_spread_by_age_group` is non-empty it is used directly; the global `game_count_spread` fallback is only used when the dict is absent.
- [x] Added game_count_spread_by_age_group to load_plan() in tournament_updater.py so it's propagated when rebuilding SeasonPlan from checkpoint — 2026-06-22
  - Files: tournament_scheduler/pipeline/tournament_updater.py
  - Approach: Wherever `tournament_updater.py` builds `UpdateResult` changes from the checkpoint plan, include `game_count_spread_by_age_group` alongside the existing `game_count_spread` entry so downstream callers receive per-age-group data.
- [ ] Add tests covering round-trip serialization and consumer behaviour
  - Files: tests/test_stage3_helpers.py, tests/test_plan_critic.py
  - Approach: Write a pytest round-trip test asserting that a `SeasonPlan` with a populated `game_count_spread_by_age_group` survives `_plan_to_dict` → `_dict_to_plan` with values intact; add a plan_critic test asserting it uses the per-age-group dict when present instead of the global spread.

## Notes
Constraints: none
The SeasonPlan model already has `game_count_spread_by_age_group: Dict[str, int]` with `default_factory=dict`, and `season_planner.py` already populates it correctly in `build_plan()`. The only gap is the checkpoint serialization/deserialization layer in `stage3_helpers.py`. The global `game_count_spread` field may be kept for backward compatibility but should be computed from the per-age-group max, not stored as a separate misleading value.

## Acceptance Criteria
- [ ] The stage3 checkpoint JSON contains a `game_count_spread_by_age_group` key with a non-empty dict after Stage 3 completes on a roster with multiple age groups.
- [ ] `_dict_to_plan` returns a `SeasonPlan` whose `game_count_spread_by_age_group` is populated when reading a checkpoint that contains the key.
- [ ] `plan_critic.py` reports per-age-group spread violations using `game_count_spread_by_age_group` when the field is non-empty, not the global `game_count_spread`.
- [ ] `pytest` passes with tests covering the round-trip serialization of `game_count_spread_by_age_group` through `_plan_to_dict` and `_dict_to_plan`.
- [ ] No age group's spread is silently masked by the global spread value — each age group's deviation is visible in plan_critic output.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-22 — Added game_count_spread_by_age_group to _plan_to_dict checkpoint dict in stage3_helpers.py
**Rationale:** Straightforward addition following existing pattern for game_count_spread
**Findings:** Field is Dict[str, int] defaulting to empty dict; added one line after game_count_spread serialization
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage3_helpers.py (+1/-0)
**Commit:** 33fb6a6 (hockey)

### 2026-06-22 — Added game_count_spread_by_age_group deserialization in _dict_to_plan in stage4_helpers.py
**Rationale:** Straightforward addition following existing game_count_spread pattern
**Findings:** _dict_to_plan is in stage4_helpers.py not stage3_helpers.py as the plan stated
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage4_helpers.py (+1/-0)
**Commit:** 3085179 (hockey)

### 2026-06-22 — plan_critic.py now uses stored spread_by_ag with inline fallback; always checks per age group and only falls back to global spread when no age-group mapping is available
**Rationale:** The code was already present as unstaged working-tree changes; staged and committed as part of this task
**Findings:** The old code only ran the per-age-group path if spread_by_ag was non-empty; the new code always groups by age group and uses stored spread when available
LESSONS: none
**Files:** tournament_scheduler/cli/plan_critic.py (+39/-32)
**Commit:** cf35876 (hockey)

### 2026-06-22 — Added game_count_spread_by_age_group to load_plan() in tournament_updater.py so it's propagated when rebuilding SeasonPlan from checkpoint
**Rationale:** tournament_updater.py has its own load_plan() that builds SeasonPlan directly from dict; it needed the field added alongside game_count_spread
**Findings:** The plan_to_dict method in tournament_updater delegates to _plan_to_dict so serialization was already handled; only deserialization needed fixing
LESSONS: none
**Files:** tournament_scheduler/pipeline/tournament_updater.py (+1/-0)
**Commit:** [pending — fill after commit]
