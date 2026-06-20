# Plan: Decompose _cmd_run god function into per-stage helpers
**Goal:** Decompose _cmd_run god function in pipeline_orchestrator.py — 300+ line function handles stage dispatch, judge invocation, refinement loop, export, and calendar generation inline; split into per-stage helpers
**Created:** 2026-06-20
**Intent:** Eliminate the 300+ line god function so each pipeline stage can be read, tested, and modified independently without navigating a tangled monolith.
**Backlog-ref:** 174

## Tasks
- [x] Moved _judge_stage from inside _cmd_run to module level; added state and log_fn parameters; kept lazy import of llm_judge inside the function; updated 3 call sites. — 2026-06-20
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: The nested `_judge_stage` function defined inside `_cmd_run` (lines 445–515) calls `get_judge_if_headless`, `build_stage_prompt`, `state.write_judgment`, and `judge.judge(prompt)`; move it to module level with the same signature and update the call site in `_cmd_run`.
- [x] Extracted Stage 1 inline block from _cmd_run into module-level _run_stage1(args, state, strict, log_fn, resume_from) returning (cfg, abort); call site in _cmd_run reduced to 3 lines. — 2026-06-20
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: The inline block at lines 529–558 calls `stage1_run` and `load_effective_config`; extract it into a new module-level function `_run_stage1(args, state, strict)` and replace the inline block with a call to it.
- [x] Extracted Stage 2 inline block from _cmd_run into module-level _run_stage2 returning (scraping, abort, stage_failed); handles force-refresh, judge gate, checkpoint gate, and non-strict fallback. — 2026-06-20
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: The inline block at lines 563–632 calls `stage2_run`, `_force_refresh_stage2_inputs`, and `_check_stage2_checkpoint`; extract into `_run_stage2(args, cfg, state, start, end, strict, allow_missing_sources)` following the same pattern as other module-level helpers in this file.
- [x] Extracted Stage 4 inline block from _cmd_run into module-level _run_stage4_export(args, plan, state, strict, log_fn, resume_from) returning (generated_calendars, abort, stage_failed). — 2026-06-20
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: The inline block at lines 673–694 calls `stage4_run`; extract into `_run_stage4_export(args, plan, state, strict)` and replace the inline block with a call to it.
- [x] Extracted calendar regeneration block from _cmd_run into module-level _regenerate_calendar(args, log_fn) returning bool; removed generate_html import from _cmd_run. — 2026-06-20
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: The inline block at lines 744–755 calls `generate_html`; extract into `_regenerate_calendar(args)` and replace the inline block with a call to it.
- [ ] Verify existing test suite passes after all extractions
  - Files: tests/test_pipeline_orchestrator_judgment.py
  - Approach: Run `pytest tests/test_pipeline_orchestrator_judgment.py` and confirm all tests pass; if patches reference the old inline nesting paths, update the patch targets to the new module-level names.

## Notes
Constraints: none

The `_run_refinement_loop` function is already extracted at module level (line 56) — do not re-extract it. Existing module-level helpers `_compute_verdict_tone`, `_cmd_calendars`, `_write_run_log`, `_resolve_resume_stage`, `_force_refresh_stage2_inputs`, `_run_approval_gate`, and `_check_stage2_checkpoint` establish the naming and signature conventions to follow. All new helpers should live in `pipeline_orchestrator.py`, not in new files, unless a helper is large enough to warrant its own module.

## Acceptance Criteria
- [ ] `_cmd_run` contains no inline nested function definitions — `_judge_stage` is a module-level function in pipeline_orchestrator.py.
- [ ] `pipeline_orchestrator.py` has at least four new module-level helper functions that replace the previously inline stage 1, stage 2, stage 4, and calendar blocks.
- [ ] `pytest tests/test_pipeline_orchestrator_judgment.py` passes with no test failures after the refactor.
- [ ] `_cmd_run` is not longer than 100 lines after all extractions are applied.
- [ ] The existing behavior of `rvv-miniputt run` is not changed — `_cmd_run` still calls all four pipeline stages in the same order.

## Log
<!-- PS:next appends entries here after each task is executed -->

### 2026-06-20 — Moved _judge_stage from inside _cmd_run to module level; added state and log_fn parameters; kept lazy import of llm_judge inside the function; updated 3 call sites.
**Rationale:** Straightforward extraction — state and log closure had to become explicit parameters; build_stage_prompt import removed from _cmd_run since it is now only used inside the module-level function.
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+82/-78)
**Commit:** 227d601 (hockey)

### 2026-06-20 — Extracted Stage 1 inline block from _cmd_run into module-level _run_stage1(args, state, strict, log_fn, resume_from) returning (cfg, abort); call site in _cmd_run reduced to 3 lines.
**Rationale:** none
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+57/-32)
**Commit:** d6ac5dd (hockey)

### 2026-06-20 — Extracted Stage 2 inline block from _cmd_run into module-level _run_stage2 returning (scraping, abort, stage_failed); handles force-refresh, judge gate, checkpoint gate, and non-strict fallback.
**Rationale:** none
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+80/-54)
**Commit:** bf7f670 (hockey)

### 2026-06-20 — Extracted Stage 4 inline block from _cmd_run into module-level _run_stage4_export(args, plan, state, strict, log_fn, resume_from) returning (generated_calendars, abort, stage_failed).
**Rationale:** stage4_run remains in _cmd_run imports because the refinement loop re-export uses it directly
**Findings:** none
LESSONS: stage4_run must stay imported in _cmd_run even after extracting the main Stage 4 block, because the refinement loop re-exports via stage4_run directly
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+56/-22)
**Commit:** fbce624 (hockey)

### 2026-06-20 — Extracted calendar regeneration block from _cmd_run into module-level _regenerate_calendar(args, log_fn) returning bool; removed generate_html import from _cmd_run.
**Rationale:** none
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+23/-9)
**Commit:** [pending — fill after commit]
