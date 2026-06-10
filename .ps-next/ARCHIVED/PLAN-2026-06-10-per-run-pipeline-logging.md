# Plan: Per-run pipeline logging
**Goal:** Every `rvv-miniputt run` writes a timestamped log file to `.pipeline/logs/` showing stage-by-stage progress, failures, and LLM fallback info — for troubleshooting and verification.
**Created:** 2026-06-10
**Intent:** Currently there is no persistent per-run record of pipeline execution. When the pipeline fails (e.g. Stage 2 blocked sources, Stage 3 planning errors), the only artifact is transient terminal output. A per-run log file enables post-hoc troubleshooting and audit.
**Backlog-ref:** 40

## Tasks
- [x] Verify and fix remaining gaps in the per-run logging implementation
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Review all code paths in _cmd_run — strict, non-strict, each stage failure. Ensure _write_run_log is called in every termination path with the correct success/failure flag. Ensure non-strict failures also produce FAILED logs (currently fixed). Verify the log file content is complete and readable.

## Notes
- Implementation already mostly done: `_log()` helper collects stage-level log lines, `_write_run_log()` writes `.pipeline/logs/pipeline_run_<timestamp>_<status>.log`.
- Fixed: non-strict failures now set `run_failed = True` so the final log reflects FAILED status.
- The `calendars` and `calendars --refresh` subcommands are out of scope — they are not the 4-stage pipeline.
- The `rvv-miniputt logs` command already exists but only reads old-format logs from `.pipeline/logs/*.log`. The new per-run logs will be discoverable by the same command.

## Acceptance Criteria
- [x] `rvv-miniputt run` (strict, blocked source) writes a FAILED log with the blocked source and LLM fallback info
- [x] `rvv-miniputt run --non-strict` with stage failures writes a FAILED log, not a SUCCESS log
- [x] A successful `rvv-miniputt run` writes a SUCCESS log with all 4 stages and calendar generation logged
- [x] grep: `run_failed = True` appears in each non-strict retry path in tournament_scheduler/cli/rvv_cli.py
- [x] grep: `_write_run_log` appears for every exit path in `_cmd_run` (both failure and success)

## Log

### 2026-06-10 — Verify and fix remaining gaps in the per-run logging implementation
**Done:** Fixed non-strict path logging: added run_failed flag, set True in each non-strict retry path and calendars.html failure. All 6 exit paths call _write_run_log, all 4 non-strict paths set run_failed = True.
**Rationale:** Non-strict failures always produced SUCCESS logs. Added run_failed boolean.
**Findings:** Non-strict failures now produce FAILED logs. LLM fallback info shown even in strict mode. Pre-existing test failure unrelated.
**Files:** tournament_scheduler/cli/rvv_cli.py (+50/-3)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
