# Plan: Replace sys.exit(1) with exceptions in tournament_updater.py __main__ block

**Feature:** Replace sys.exit(1) with exceptions in tournament_updater.py __main__ block — library code calling sys.exit kills the process when imported and hit during pipeline use
**Goal:** Replace sys.exit(1) with exceptions in tournament_updater.py __main__ block — library code calling sys.exit kills the process when imported and hit during pipeline use
**Backlog-ref:** 178
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Prevent sys.exit calls in library code from killing the process when tournament_updater.py is imported as a module and an error condition is encountered during pipeline execution.

## Tasks

- [x] Added TournamentUpdateError and TournamentValidationError exception classes after the imports/logger section in tournament_updater.py. — 2026-06-20
  - Files: tournament_scheduler/pipeline/tournament_updater.py
  - Approach: Add `TournamentUpdateError` and `TournamentValidationError` custom exception classes near the top of tournament_updater.py (after imports, before function definitions), so that the __main__ block can raise typed exceptions instead of calling sys.exit.

- [x] Replaced all six sys.exit(1) calls in the __main__ block with raises of TournamentValidationError/TournamentUpdateError; wrapped the block in a single try/except that catches TournamentUpdateError and prints to stderr then exits cleanly. — 2026-06-20
  - Files: tournament_scheduler/pipeline/tournament_updater.py
  - Approach: Locate the six sys.exit(1) calls in the `if __name__ == "__main__":` block (lines 862, 866, 875, 886, 896, 907) and replace each with a raise of `TournamentValidationError` or `TournamentUpdateError`, preserving all error messages; wrap the entire __main__ block in a try/except that catches these and prints to stderr then exits cleanly for CLI use.

- [x] Added TournamentUpdateError/TournamentValidationError imports and a TestExceptionClasses suite (4 tests) to test_tournament_updater.py; no existing tests needed updating as none mocked sys.exit. — 2026-06-20
  - Files: tests/test_tournament_updater.py, tests/test_pipeline_orchestrator.py, tests/test_cancellation_workflow.py
  - Approach: Update any test cases that mock or expect sys.exit calls to instead assert that `TournamentValidationError` or `TournamentUpdateError` is raised, using pytest.raises() as appropriate.

- [x] Verified that cancellation_workflow.py, manual_adjustment_workflow.py, update_command.py, and rvv_cli.py all call updater library methods (load_plan, drop_team, move_date) which do not raise TournamentUpdateError/TournamentValidationError — those exceptions are only raised in the __main__ block. No code changes needed. — 2026-06-20
  - Files: tournament_scheduler/pipeline/cancellation_workflow.py, tournament_scheduler/pipeline/manual_adjustment_workflow.py, tournament_scheduler/cli/update_command.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: Review each importing module to confirm it does not invoke the __main__ block code paths, and if any caller re-exposes the updater's validation logic, add try/except handling for `TournamentUpdateError`/`TournamentValidationError` rather than relying on sys.exit to terminate.

## Acceptance Criteria

The __main__ block in tournament_updater.py does not contain any sys.exit(1) calls; all error conditions raise a typed exception instead.
Code that imports tournament_updater.py as a library module does not have its process terminated when a validation error is triggered.
Running `pytest tests/test_tournament_updater.py` passes after the replacement, with tests asserting exceptions rather than process exits.
The CLI entry point for the updater (invoked via `python -m tournament_scheduler.pipeline.tournament_updater`) still prints a Norwegian-language error message to stderr and exits with a non-zero code when validation fails.
No sys.exit call remains in tournament_updater.py outside of the `if __name__ == "__main__":` guard.

## Log

### 2026-06-20 — Added TournamentUpdateError and TournamentValidationError exception classes after the imports/logger section in tournament_updater.py.
**Rationale:** Straightforward addition; no alternatives needed.
**Findings:** Custom exception classes defined; tests pass.
LESSONS: none
**Files:** tournament_scheduler/pipeline/tournament_updater.py (+13/-0)
**Commit:** 32c3835 (hockey)

### 2026-06-20 — Replaced all six sys.exit(1) calls in the __main__ block with raises of TournamentValidationError/TournamentUpdateError; wrapped the block in a single try/except that catches TournamentUpdateError and prints to stderr then exits cleanly.
**Rationale:** Wrapping in try/except at the top of __main__ keeps CLI behavior while allowing library import without sys.exit risk.
**Findings:** All tests pass; __main__ block now uses exceptions exclusively for error paths.
LESSONS: none
**Files:** tournament_scheduler/pipeline/tournament_updater.py (+42/-40)
**Commit:** dcf5e46 (hockey)

### 2026-06-20 — Added TournamentUpdateError/TournamentValidationError imports and a TestExceptionClasses suite (4 tests) to test_tournament_updater.py; no existing tests needed updating as none mocked sys.exit.
**Rationale:** No existing tests used sys.exit mocking, so only additions were needed; a dedicated class verifies the exception hierarchy.
**Findings:** 4 new tests added; all 25 tests in the file pass.
LESSONS: none
**Files:** tests/test_tournament_updater.py (+33/-1)
**Commit:** f55f69f (hockey)

### 2026-06-20 — Verified that cancellation_workflow.py, manual_adjustment_workflow.py, update_command.py, and rvv_cli.py all call updater library methods (load_plan, drop_team, move_date) which do not raise TournamentUpdateError/TournamentValidationError — those exceptions are only raised in the __main__ block. No code changes needed.
**Rationale:** The new exceptions are confined to __main__; library callers are unaffected.
**Findings:** All four importing modules confirmed safe; rvv_cli.py has its own separate sys.exit in _load_plan_and_updater for CLI use which is appropriate.
LESSONS: The new TournamentUpdateError/TournamentValidationError exceptions are only raised in the __main__ block, not in library methods — callers that import TournamentUpdater directly are not affected.
**Files:** none
**Commit:** [pending — fill after commit]
