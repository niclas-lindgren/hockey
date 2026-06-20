# Plan: Extract shared SeasonPlan-to-dict + issue-count helper
**Goal:** Extract shared issue-counting helper used by _cmd_auto_adjust, _cmd_critic, _cmd_verdict in rvv_cli.py — all three convert SeasonPlan to dict and count issues identically
**Created:** 2026-06-20
**Intent:** Eliminate the inline hasattr check and repeated _plan_to_dict import inside the _cmd_auto_adjust loop, replacing duplicated conversion logic with a single shared helper callable by all three CLI commands.
**Backlog-ref:** 177

## Tasks
- [x] Added _resolve_plan_dict(plan_raw) to stage3_helpers.py; converts SeasonPlan objects via _plan_to_dict or returns dicts as-is. — 2026-06-20
  - Files: tournament_scheduler/pipeline/stage3_helpers.py
  - Approach: Define `_resolve_plan_dict(plan_raw) -> dict` that checks `hasattr(plan_raw, "__dict__")` and calls `_plan_to_dict` if true, or returns the raw dict if plan_raw is already a dict — encapsulating the inline logic currently inside _cmd_auto_adjust's iteration loop.

- [x] Added count_issues_from_plan(plan_raw) to plan_critic.py; imports _resolve_plan_dict and delegates to count_critic_issues_from_dict. — 2026-06-20
  - Files: tournament_scheduler/cli/plan_critic.py
  - Approach: Define `count_issues_from_plan(plan_raw) -> int` that imports `_resolve_plan_dict` from stage3_helpers, converts plan_raw to a dict, and delegates to `count_critic_issues_from_dict` — giving callers a single call that handles both SeasonPlan objects and raw dicts.

- [x] Replaced the 12-line inline hasattr block and inner loop import with a single count_issues_from_plan(plan_raw) call. — 2026-06-20
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Remove the inline `hasattr` check, the inline `from ..pipeline.stage3_helpers import _plan_to_dict as _p2d` inside the loop, and the manual dict assignment at lines 596-607; replace with a single `issue_count = count_issues_from_plan(plan_raw)` call, importing the new helper at the top of the function.

- [x] Added 5 tests for _resolve_plan_dict in test_stage3_helpers.py and 4 tests for count_issues_from_plan in test_plan_critic.py. — 2026-06-20
  - Files: tests/test_plan_critic.py, tests/test_stage3_helpers.py
  - Approach: In test_plan_critic.py add tests for `count_issues_from_plan` covering a SeasonPlan-like object (with __dict__) and a plain dict input; in test_stage3_helpers.py add tests for `_resolve_plan_dict` with both input types and a None/empty guard.

- [x] Ran pytest on test_auto_adjust.py, test_verdict_cli.py, test_plan_critic.py and test_stage3_helpers.py — all 60 tests pass with no regressions. — 2026-06-20
  - Files: tests/test_auto_adjust.py, tests/test_verdict_cli.py, tests/test_plan_critic.py
  - Approach: Run `pytest tests/test_auto_adjust.py tests/test_verdict_cli.py tests/test_plan_critic.py` and confirm no regressions; update any mock patches that referenced the old inline import path.

## Notes
Only _cmd_auto_adjust actually performs the SeasonPlan-to-dict conversion + count_critic_issues_from_dict call. _cmd_critic uses generate_critic_summary directly; _cmd_verdict does not count issues. The helper should still be available for future use by _cmd_critic/_cmd_verdict if needed, but the primary extraction target is _cmd_auto_adjust's inline loop logic.

The existing `_load_critic_state` helper (line 534 of rvv_cli.py) is already a shared pattern for loading checkpoints — follow the same module-level helper style.

`_plan_to_dict` is a private function (underscore prefix) in stage3_helpers.py. `_resolve_plan_dict` should remain private too. `count_issues_from_plan` in plan_critic.py should be public (no leading underscore) since it will be imported by rvv_cli.py.

## Acceptance Criteria
- [ ] The `_cmd_auto_adjust` function in rvv_cli.py no longer contains an inline `from ..pipeline.stage3_helpers import _plan_to_dict` import inside its loop body.
- [ ] `count_issues_from_plan` is defined in tournament_scheduler/cli/plan_critic.py and returns an integer when passed a SeasonPlan object or a plain dict.
- [ ] `_resolve_plan_dict` is defined in tournament_scheduler/pipeline/stage3_helpers.py and returns a dict for both SeasonPlan object inputs and raw dict inputs.
- [ ] Running `pytest tests/test_auto_adjust.py tests/test_verdict_cli.py tests/test_plan_critic.py` passes with no failures after the refactoring.
- [ ] The new helper functions are covered by tests in test_plan_critic.py or test_stage3_helpers.py that pass with `pytest`.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-20 — Added _resolve_plan_dict(plan_raw) to stage3_helpers.py; converts SeasonPlan objects via _plan_to_dict or returns dicts as-is.
**Rationale:** Straightforward extraction; returns empty dict for None/unknown inputs as a safe default.
**Findings:** Helper added at line ~84, just after _plan_to_dict.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage3_helpers.py (+15/-0)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Added count_issues_from_plan(plan_raw) to plan_critic.py; imports _resolve_plan_dict and delegates to count_critic_issues_from_dict.
**Rationale:** Single public callable for all CLI commands needing an issue count from either object or dict.
**Findings:** Defined after count_critic_issues_from_dict; also added Any to typing imports.
LESSONS: none
**Files:** tournament_scheduler/cli/plan_critic.py (+21/-1)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Replaced the 12-line inline hasattr block and inner loop import with a single count_issues_from_plan(plan_raw) call.
**Rationale:** Simpler than original; import of count_issues_from_plan added at top of function alongside suggest_moves.
**Findings:** count_critic_issues_from_dict import replaced with count_issues_from_plan in rvv_cli.py line 569.
LESSONS: none
**Files:** tournament_scheduler/cli/rvv_cli.py (+4/-14)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Added 5 tests for _resolve_plan_dict in test_stage3_helpers.py and 4 tests for count_issues_from_plan in test_plan_critic.py.
**Rationale:** Covers both SeasonPlan-like object input and plain dict input plus edge cases (None, empty, non-dict).
**Findings:** All 60 tests pass including the 9 new ones.
LESSONS: none
**Files:** tests/test_plan_critic.py (+40/-1), tests/test_stage3_helpers.py (+46/-2)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Ran pytest on test_auto_adjust.py, test_verdict_cli.py, test_plan_critic.py and test_stage3_helpers.py — all 60 tests pass with no regressions.
**Rationale:** No mock patches needed updating; the refactoring was clean.
**Findings:** 60 tests passed, 0 failures.
LESSONS: none
**Files:** none
**Commit:** [pending — fill after commit]
