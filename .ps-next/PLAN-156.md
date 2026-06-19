# Plan: Fix Stage 2 checkpoint finalization on partial-resume
**Goal:** Fix Stage 2 scraping checkpoint finalization bug: stage exits 0 but leaves checkpoint as 'running' with no data when resuming from a previously interrupted run — checkpoint finalization is skipped on partial-resume; second run fixes it via cache
**Created:** 2026-06-19
**Intent:** Eliminate the silent data-loss bug where an interrupted Stage 2 run leaves the pipeline permanently stuck with a 'running' checkpoint until a second run happens to succeed via cache.
**Backlog-ref:** 156

## Tasks
- [x] Replace write_stage({}, RUNNING) with _set_status(RUNNING) on line 113 so the in-progress marker patches only the status field without wiping the existing checkpoint data. — 2026-06-19
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/state.py
  - Approach: Replace line 113's `state.write_stage(StageName.SCRAPING, {}, status=StageStatus.RUNNING)` with `state._set_status(StageName.SCRAPING, StageStatus.RUNNING)` so the RUNNING marker patches only the status field of the existing checkpoint without overwriting the data payload; add a `_set_status` call to `PipelineState` that creates a minimal envelope if no file exists yet.

- [x] Added TestCheckpointPreservationOnResume with two tests: one verifying that a prior checkpoint's data is preserved when resuming, and one verifying the fresh-run (no prior checkpoint) scenario still works correctly. — 2026-06-19
  - Files: tests/test_stage2_scraping.py
  - Approach: Write a test that (1) calls `state.write_stage(SCRAPING, existing_data, DONE)` to simulate a prior completed checkpoint, (2) then calls `run()` with a mock that raises mid-scrape to simulate interruption, (3) asserts the checkpoint still contains `existing_data` (not an empty dict) and is not left with `status=running` after the re-run completes successfully from cache.

- [x] The fresh-run regression test (test_fresh_run_with_no_prior_checkpoint_works_correctly) was included in the prior task's commit as part of TestCheckpointPreservationOnResume — it verifies that _set_status creates a minimal RUNNING envelope when no checkpoint exists and that write_stage then overwrites it with full data and DONE status. — 2026-06-19
  - Files: tests/test_stage2_scraping.py
  - Approach: Verify the fix does not break the first-ever run scenario: when no checkpoint file exists, `_set_status` should create a minimal RUNNING envelope and the final `write_stage(checkpoint, DONE)` should overwrite it with full data and DONE status.

## Notes
Root cause: `stage2_scraping.py` line 113 calls `state.write_stage(StageName.SCRAPING, {}, status=StageStatus.RUNNING)` which overwrites any existing checkpoint with empty data at the start of every run. If the process is interrupted (SIGINT, crash, unhandled exception in ThreadPoolExecutor) after line 113 but before line 235's `state.write_stage(checkpoint, status=DONE)`, the checkpoint is permanently left as `{status: running, data: {}}`. The second run succeeds because all sources hit the cache and the flow completes normally to write the DONE checkpoint.

`state._set_status()` is an existing internal method in `state.py` that patches only the status field of an existing checkpoint without replacing its data payload — it is the correct primitive to use here. `state.read_envelope()` can be used as fallback to detect whether a checkpoint already exists.

## Acceptance Criteria
- [ ] Running Stage 2 after a simulated interruption (checkpoint left as RUNNING with empty data) produces a checkpoint with status DONE and non-empty sources data on the second run without needing any manual intervention.
- [ ] The pytest suite passes with no regressions in test_stage2_scraping.py after the fix is applied.
- [ ] The checkpoint file does not contain an empty data dict (`"data": {}`) after stage2_scraping.run() completes successfully.
- [ ] A fresh first run (no prior checkpoint file) still writes a DONE checkpoint with full source data.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Replace write_stage({}, RUNNING) with _set_status(RUNNING) on line 113 so the in-progress marker patches only the status field without wiping the existing checkpoint data.
**Rationale:** Used the existing _set_status helper which reads the current envelope and patches only the status field, preserving any previously-written data payload. No alternatives needed — the method already existed for exactly this purpose.
**Findings:** One-line change: _set_status(RUNNING) instead of write_stage({}, RUNNING). All tests pass.
LESSONS: none
**Files:** stage2_scraping.py (+1/-1)
**Commit:** 7840d3a (hockey)

### 2026-06-19 — Added TestCheckpointPreservationOnResume with two tests: one verifying that a prior checkpoint's data is preserved when resuming, and one verifying the fresh-run (no prior checkpoint) scenario still works correctly.
**Rationale:** Both tests run against real PipelineState and a seeded cache to isolate just the _set_status change without triggering live scrapers.
**Findings:** Both tests pass; no regressions in the full suite.
LESSONS: none
**Files:** tests/test_stage2_scraping.py (+96)
**Commit:** c38a049 (hockey)

### 2026-06-19 — The fresh-run regression test (test_fresh_run_with_no_prior_checkpoint_works_correctly) was included in the prior task's commit as part of TestCheckpointPreservationOnResume — it verifies that _set_status creates a minimal RUNNING envelope when no checkpoint exists and that write_stage then overwrites it with full data and DONE status.
**Rationale:** Implemented together with the interrupted-run test in the previous task; no separate code needed.
**Findings:** Test already present in tests/test_stage2_scraping.py and passes.
LESSONS: none
**Files:** tests/test_stage2_scraping.py (already committed)
**Commit:** [pending — fill after commit]
