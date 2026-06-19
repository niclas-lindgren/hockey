# Plan: Remove dead _tournament_from_dict import in stage3_planning.py
**Goal:** Remove dead _tournament_from_dict import in stage3_planning.py — the function is imported but never called anywhere in the pipeline.
**Created:** 2026-06-19
**Intent:** Eliminate an unused import that adds noise and potential confusion about what stage3_planning.py depends on.
**Backlog-ref:** 132

## Tasks
- [x] Removed dead _tournament_from_dict import from stage3_planning.py and updated two callers (tournament_updater.py, test_cancellation_workflow.py) to import directly from stage3_helpers where it is defined. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage3_planning.py
  - Approach: Remove the import statement for _tournament_from_dict at line 30 in stage3_planning.py; the function is defined in stage3_helpers.py and is only legitimately used in tournament_updater.py, not in stage3_planning.py.
- [ ] Run tests to confirm no regressions
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage3_planning.py
  - Approach: Run pytest to ensure that removing the unused import does not break any existing tests; the live usage in tournament_updater.py is unaffected by this change.

## Notes
Constraints: none
The function _tournament_from_dict is defined in stage3_helpers.py and is actively used (imported and called) in tournament_updater.py. The import in stage3_planning.py is the only dead reference and is the sole change needed.

## Acceptance Criteria
- [ ] The stage3_planning.py file no longer contains a line that imports _tournament_from_dict from stage3_helpers.
- [ ] Running a code search across the repository shows no remaining references to _tournament_from_dict in stage3_planning.py after the removal.
- [ ] The tournament_updater.py file continues to import and call _tournament_from_dict as expected, maintaining its functionality.
- [ ] Tests that validate the stage3_planning.py module run successfully without any import-related errors or warnings.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Removed dead _tournament_from_dict import from stage3_planning.py and updated two callers (tournament_updater.py, test_cancellation_workflow.py) to import directly from stage3_helpers where it is defined.
**Rationale:** The function was not used in stage3_planning.py itself, but two files imported it from there as a re-export; fixed both to import from the canonical source.
**Findings:** 542 tests pass (excluding pre-existing failures in test_claude_orchestration.py and test_manual_adjustment_workflow.py which are unrelated)
LESSONS: _tournament_from_dict was re-exported from stage3_planning.py indirectly; callers must be updated to import from stage3_helpers directly when removing such re-exports
**Files:** tournament_scheduler/pipeline/stage3_planning.py (+1/-1), tournament_scheduler/pipeline/tournament_updater.py (+2/-1), tests/test_cancellation_workflow.py (+2/-1)
**Commit:** [pending — fill after commit]
