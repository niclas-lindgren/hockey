# Plan: Fix validate_config path resolution relative to input_path
**Goal:** Fix stage1_helpers.validate_config path resolution: currently checks Path(teams_val).exists() with no CWD anchor, so the check passes/fails based on the process launch directory rather than the location of input.xlsx. Resolve relative to input_path.
**Created:** 2026-06-19
**Intent:** Ensure validate_config resolves relative teams file paths against the directory of input.xlsx so the check is deterministic regardless of the process launch directory.
**Backlog-ref:** 135

## Tasks
- [x] Changed validate_config to accept input_path: Path and resolve relative team-file paths against input_path.parent, so the existence check is CWD-independent. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage1_helpers.py
  - Approach: Change the function signature from `validate_config(raw: dict[str, Any])` to `validate_config(raw: dict[str, Any], input_path: Path)` so the directory context of input.xlsx is available for path resolution.
- [x] Already implemented in the previous task: (input_path.parent / teams_val).resolve() is used to anchor relative team-file paths to the workbook directory. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage1_helpers.py
  - Approach: Replace `Path(teams_val).exists()` with `(Path(input_path).parent / teams_val).exists()` so relative paths are resolved relative to the input file location, not CWD. Absolute paths should remain unaffected (Path division with an absolute right-hand side keeps the absolute path).
- [x] Already implemented in task 1: the single call site at line 151 was updated to pass Path(input_path) as the second argument. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage1_config.py
  - Approach: Update both calls to `validate_config` (at lines ~48 and ~151) in stage1_config.py to include the `input_path` argument, which is already in scope at each call site.
- [ ] Update existing tests and add path-resolution test cases in test_stage1_config.py
  - Files: /Users/niclasl/src/hockey/tests/test_stage1_config.py
  - Approach: Update all existing `validate_config` calls in the test file to pass an `input_path` argument. Add new test cases that verify a relative teams path resolves correctly relative to the input file directory, and fails when the same relative path does not exist relative to that directory.

## Notes
Constraints: none

The bug is in `tournament_scheduler/pipeline/stage1_helpers.py` — `validate_config` calls `Path(teams_val).exists()` without anchoring to the input file's directory. The `input_path` is already available in `stage1_config.py` at both call sites but was never threaded into `validate_config`. Absolute paths are unaffected by the fix because `Path('/abs/path') / '/abs/path'` returns the absolute right-hand side unchanged in Python's pathlib.

## Acceptance Criteria
- [ ] validate_config returns no error when a relative teams path exists relative to the directory of input_path, and returns a validation error when that same relative path does not exist relative to the current working directory (but exists relative to input_path.parent).
- [ ] Running pytest passes after the fix, including tests that supply a relative teams path located alongside input_path.
- [ ] A relative teams path that does not exist relative to input_path causes validate_config to return a validation error.
- [ ] validate_config returns no error when an absolute teams path exists, regardless of the input_path location.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Changed validate_config to accept input_path: Path and resolve relative team-file paths against input_path.parent, so the existence check is CWD-independent.
**Rationale:** Straightforward signature extension; call site in stage1_config.py already had Path(input_path) available.
**Findings:** All tests pass; teams file path now resolved relative to the workbook directory.
LESSONS: none
**Files:** stage1_config.py (+2/-1), stage1_helpers.py (+12/-3)
**Commit:** 014f37f (hockey)

### 2026-06-19 — Already implemented in the previous task: (input_path.parent / teams_val).resolve() is used to anchor relative team-file paths to the workbook directory.
**Rationale:** This task was subsumed by the signature-change task which was implemented together.
**Findings:** Path resolution already in place from prior task; absolute paths unaffected because Path division with an absolute RHS preserves the absolute path.
LESSONS: none
**Files:** no additional files changed
**Commit:** f02d7f3 (hockey)

### 2026-06-19 — Already implemented in task 1: the single call site at line 151 was updated to pass Path(input_path) as the second argument.
**Rationale:** Line 48 in the plan note is the import statement, not a second call site; there is only one call.
**Findings:** Only one call site exists; already updated in prior task.
LESSONS: none
**Files:** no additional files changed
**Commit:** [pending — fill after commit]
