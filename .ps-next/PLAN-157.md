# Plan: Fix Stage 4 export to write into a timestamped subfolder of export/ by default

**Feature:** Fix Stage 4 export to write into a timestamped subfolder of export/ by default (e.g. export/2026-06-19T08-21/) — currently exports flat to export/ even though --no-timestamped-export flag implies timestamped subfolders should be the default behavior
**Goal:** Fix Stage 4 export to write into a timestamped subfolder of export/ by default (e.g. export/2026-06-19T08-21/) — currently exports flat to export/ even though --no-timestamped-export flag implies timestamped subfolders should be the default behavior
**Backlog-ref:** 157
**Constraints:** none
**Date:** 2026-06-19
**Intent:** Make timestamped export subfolders the default for all Stage 4 export paths so the --no-timestamped-export flag name accurately reflects the opt-out behavior it advertises.

---

## Tasks

- [x] Changed timestamped_export default from False to True in run() so exports go to a timestamped subfolder by default. — 2026-06-19
  - **Files:** `tournament_scheduler/pipeline/stage4_export.py`
  - **Approach:** Change the default value of the `timestamped_export` parameter in `run()` from `False` to `True` (line 64). This makes the function's own default consistent with the desired behavior without requiring the caller to pass the flag explicitly.

- [x] Updated replan, adjust, review, and auto_adjust subcommands to use --no-timestamped-export with store_false and set_defaults(timestamped_exportTrue), matching the run subcommand pattern. — 2026-06-19
  - **Files:** `tournament_scheduler/cli/args.py`
  - **Approach:** For the `replan`, `adjust`, `review`, and `auto_adjust` subcommands, change `--timestamped-export` from `action=store_true` (default False) to `--no-timestamped-export` with `action=store_false, dest=timestamped_export` and call `<subparser>.set_defaults(timestamped_export=True)` — mirroring the pattern already used for the `run` subcommand at line 80-85.

- [x] Changed getattr fallback from False to True so any code path without explicit args.timestamped_export defaults to timestamped-on. — 2026-06-19
  - **Files:** `tournament_scheduler/cli/pipeline_orchestrator.py`
  - **Approach:** Change line 522's `getattr(args, "timestamped_export", False)` fallback to `getattr(args, "timestamped_export", True)` so that any code path that reaches stage4_run without an explicit args attribute defaults to timestamped-on rather than off.

- [ ] Update tests that call `run()` without `timestamped_export` to explicitly pass `timestamped_export=False`
  - **Files:** `tests/test_stage4_export.py`
  - **Approach:** Find all `run(...)` calls in `test_stage4_export.py` that do not pass `timestamped_export` and are asserting flat export paths (files directly under `export/`). Add `timestamped_export=False` to each so they continue testing flat export without being affected by the new default. Ensure the existing test at line 468-474 that tests `timestamped_export=True` remains unchanged.

- [ ] Add a test asserting that `run()` with default arguments produces a timestamped subfolder
  - **Files:** `tests/test_stage4_export.py`
  - **Approach:** Add a new test that calls `run(_make_plan_dict(), state, export_dir=str(tmp_path / "export"))` with no explicit `timestamped_export` argument and asserts that the exported files land under a subdirectory of `export/` matching the pattern `YYYY-MM-DDTHHMM`.

---

## Log

## Acceptance Criteria

When no --no-timestamped-export flag is provided, the Stage 4 export command writes files into a timestamped subfolder under export/ directory with format export/YYYY-MM-DDTHH-MM/.
When the --no-timestamped-export flag is provided, the Stage 4 export command writes files flat into the export/ directory without creating timestamped subfolders.
The Stage 4 export run() function produces a timestamped subfolder path when called with no explicit timestamped_export argument.
Running pytest passes with the updated default behavior, including all existing tests that now explicitly pass timestamped_export=False for flat-export assertions.
The replan, adjust, review, and auto_adjust subcommands write exports to a timestamped subfolder by default, matching the behavior of the run subcommand.

### 2026-06-19 — Changed timestamped_export default from False to True in run() so exports go to a timestamped subfolder by default.
**Rationale:** Straightforward one-line change — no alternatives considered.
**Findings:** All existing stage4_export tests pass with the new default.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage4_export.py (+1/-1)
**Commit:** 8aab93a (hockey)

### 2026-06-19 — Updated replan, adjust, review, and auto_adjust subcommands to use --no-timestamped-export with store_false and set_defaults(timestamped_exportTrue), matching the run subcommand pattern.
**Rationale:** Mirrored the run subcommand pattern exactly.
**Findings:** All tests pass.
LESSONS: none
**Files:** tournament_scheduler/cli/args.py (+20/-13)
**Commit:** 298ac6b (hockey)

### 2026-06-19 — Changed getattr fallback from False to True so any code path without explicit args.timestamped_export defaults to timestamped-on.
**Rationale:** Straightforward one-line fix.
**Findings:** All tests pass.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+1/-1)
**Commit:** [pending — fill after commit]
