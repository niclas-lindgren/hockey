# Plan: Fix _run_approval_gate always returning True
**Goal:** Fix _run_approval_gate always returning True (pipeline_orchestrator.py ~line 304) — gate is a no-op so critical issues can never block the pipeline
**Created:** 2026-06-21
**Intent:** Prevent the pipeline from silently proceeding to Stage 4 export when the season plan has critical fairness gate failures, so organizers cannot accidentally produce exports from a fundamentally broken plan.
**Backlog-ref:** 169

## Tasks
- [x] Implemented blocking logic: when strictTrue and fairness_gate.status is 'fail', prints Norwegian error and returns False; when non-strict, prints Fortsetter pga --non-strict warning. — 2026-06-21
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Inspect fairness_gate.status from the season_plan dict inside _run_approval_gate; when strict=True and status is "fail", print a Norwegian-language error message and return False. When non-strict, print the "Fortsetter pga --non-strict" warning following the pattern used by other stage wrappers in the same file.

- [x] Implemented warn handling: when fairness_gate.status is 'warn', calls generate_critic_summary and prints each issue as a warning, then returns True. — 2026-06-21
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: When fairness_gate.status is "warn" (regardless of strict mode), call generate_critic_summary and print each returned issue as a warning, then return True so the pipeline continues — matching how other non-fatal issues are surfaced.

- [x] Replaced misleading 'always returns True (non-blocking)' docstring with accurate description of blocking behavior. — 2026-06-21
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Replace the misleading "always returns True (non-blocking)" docstring with accurate description: returns False when strict=True and fairness_gate.status is "fail", True otherwise.

- [x] Added 7 test cases in TestRunApprovalGate covering strict-block, non-strict-allow, warn-allow, pass-allow scenarios, and critic call verification. — 2026-06-21
  - Files: tests/test_pipeline_orchestrator.py
  - Approach: Add test cases in the existing test file that construct a minimal plan_checkpoint dict with fairness_gate.status="fail" and call _run_approval_gate with strict=True — assert return value is False. Mirror the existing _run_refinement_loop test structure.

- [x] Tests for non-strict fail (returns True), warn (returns True), and pass (returns True) are included in the TestRunApprovalGate class already added in task 4. — 2026-06-21
  - Files: tests/test_pipeline_orchestrator.py
  - Approach: Add test cases for strict=False with status="fail" (returns True), strict=True with status="warn" (returns True), and status="pass" (returns True regardless of strict) — verifying no accidental blocking outside the one blocking case.

## Notes
Constraints: none

Key findings:
- _run_approval_gate is at line 416 of tournament_scheduler/cli/pipeline_orchestrator.py
- It receives args, plan_checkpoint (dict), state, strict (bool), console, log_fn
- plan_checkpoint["plan"]["fairness_gate"]["status"] is "fail"/"warn"/"pass"
- generate_critic_summary(season_plan) returns List[str] ordered by severity; "fail" issues first
- The calling site at line 923 already does: if not _run_approval_gate(...): return 1
- No existing tests cover _run_approval_gate return value or blocking behavior

## Acceptance Criteria
- [ ] When _run_approval_gate is called with strict=True and fairness_gate.status is "fail", it returns False and the pipeline exits with code 1.
- [ ] When _run_approval_gate is called with strict=False and fairness_gate.status is "fail", it prints a warning containing "non-strict" and returns True.
- [ ] When fairness_gate.status is "pass", _run_approval_gate returns True regardless of strict mode.
- [ ] Running pytest tests/test_pipeline_orchestrator.py passes with new test cases covering the blocking and non-blocking behavior of _run_approval_gate.
- [ ] The docstring of _run_approval_gate no longer contains "always returns True".

## Log
<!-- PS:next appends entries here after each task is executed -->

### 2026-06-21 — Implemented blocking logic: when strictTrue and fairness_gate.status is 'fail', prints Norwegian error and returns False; when non-strict, prints Fortsetter pga --non-strict warning.
**Rationale:** Blocking on critical fairness failures in strict mode is now enforced inside _run_approval_gate.
**Findings:** gate_status'fail' branch checks strict flag, returns False if strict, prints non-strict warning otherwise
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+40/-2)
**Commit:** [pending — fill after commit]

### 2026-06-21 — Implemented warn handling: when fairness_gate.status is 'warn', calls generate_critic_summary and prints each issue as a warning, then returns True.
**Rationale:** Warn status surfaces critic issues without blocking the pipeline.
**Findings:** gate_status'warn' branch calls generate_critic_summary and prints warnings
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (same edit)
**Commit:** [pending — fill after commit]

### 2026-06-21 — Replaced misleading 'always returns True (non-blocking)' docstring with accurate description of blocking behavior.
**Rationale:** Docstring now accurately describes when the gate blocks vs allows.
**Findings:** Docstring updated in the same edit that implemented the blocking logic
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (same edit)
**Commit:** [pending — fill after commit]

### 2026-06-21 — Added 7 test cases in TestRunApprovalGate covering strict-block, non-strict-allow, warn-allow, pass-allow scenarios, and critic call verification.
**Rationale:** All 26 tests in test_pipeline_orchestrator.py pass.
**Findings:** Tests use plan_checkpoint dicts with fairness_gate dicts; patch target is plan_critic module (lazy import)
LESSONS: generate_critic_summary is imported lazily inside _run_approval_gate so patch at plan_critic module not orchestrator module
**Files:** tests/test_pipeline_orchestrator.py (+107)
**Commit:** [pending — fill after commit]

### 2026-06-21 — Tests for non-strict fail (returns True), warn (returns True), and pass (returns True) are included in the TestRunApprovalGate class already added in task 4.
**Rationale:** All allow-through cases are covered by the same 7 test cases.
**Findings:** Tests structured in same class as blocking tests per test file convention
LESSONS: none
**Files:** tests/test_pipeline_orchestrator.py (same edit)
**Commit:** [pending — fill after commit]
