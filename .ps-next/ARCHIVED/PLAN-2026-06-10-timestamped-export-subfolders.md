# Plan: Timestamped export subfolders
**Goal:** Every `rvv-miniputt run` writes exports to a timestamped subfolder (e.g. `export/2026-06-10T1430/`) so changes between pipeline runs are diffable, while also keeping the flat `export/` copy for convenience.
**Created:** 2026-06-10
**Intent:** Currently `export/` is overwritten each run, making it impossible to compare outputs between runs or track how the season plan evolved. Timestamped subfolders solve this with minimal changes.
**Backlog-ref:** 34

## Tasks
- [x] Add `--timestamped-export` flag to `rvv-miniputt run` and `rvv-miniputt replan`
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Add `--timestamped-export` action="store_true" to run and replan subparsers. Pass `timestamped_export` flag down to stage4_export via a parameter.
- [x] Modify `stage4_export.run()` to create timestamped subfolders and also write to flat directory
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: When `timestamped_export=True`, create `export/<YYYY-MM-DDTHHMM>/` subfolder, write all files there, then copy to flat `export/`. When `False`, write to flat `export/` only (backward compatible).

## Notes
- The `rvv-miniputt run` already has `--export-dir` (default `export`). The timestamped subfolder goes inside that.
- Other subcommands that export (`cancel`, `replan`, `tournament add/remove`) should also benefit from this. But starting with `run` and `replan` is sufficient.
- Timestamp format: `YYYY-MM-DDTHHMM` (ISO-like, filesystem-safe).

## Acceptance Criteria
- [x] `rvv-miniputt run --timestamped-export` writes to `export/YYYY-MM-DDTHHMM/` and also copies to `export/`
- [x] `rvv-miniputt run` (without flag) writes to flat `export/` (backward compatible)
- [x] Old pipeline runs are preserved and diffable between runs
- [x] `rvv-miniputt replan --timestamped-export` also writes to timestamped subfolder

## Log


### 2026-06-10 — Modify `stage4_export.run()` to create timestamped subfolders and also write to flat directory
**Done:** Added timestamped_export parameter to stage4_export.run(). When True, creates export/YYYY-MM-DDTHHMM/ subfolder, writes all files there, then copies to flat export/ for convenience.
**Rationale:** Primary writes to timestamped subfolder for diffability; shutil.copy2 to flat export/ for backwards compatibility.
**Findings:** 12 files exported (6 originals + 6 flat copies). Timestamp format YYYY-MM-DDTHHMM is filesystem-safe.
**Files:** tournament_scheduler/pipeline/stage4_export.py (+15/-10)
**Commit:** not committed
### 2026-06-10 — Add `--timestamped-export` flag to `rvv-miniputt run` and `rvv-miniputt replan`
**Done:** Added --timestamped-export flag to run and replan subparsers in _build_parser(). Passed through _cmd_run → stage4_run and _cmd_replan/_do_re_export. Also fixed pre-existing bug where output count always showed 0.
**Rationale:** getattr(args, 'timestamped_export', False) handles subcommands without the flag. _do_re_export updated with keyword-only parameter.
**Findings:** Pre-existing bug: export.get('files', []) should be export.get('output_files', {}). Fixed alongside.
**Files:** tournament_scheduler/cli/rvv_cli.py (+18/-4)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
