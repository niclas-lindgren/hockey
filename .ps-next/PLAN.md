# Plan: Workbook/config fingerprints for stale pipeline checkpoints
**Goal:** Stage 1 records deterministic workbook/effective-config fingerprints and pipeline status marks downstream checkpoints stale when the current `input.xlsx` no longer matches the Stage 1 checkpoint.
**Created:** 2026-07-07
**Intent:** Prevent organizers from trusting `done` Stage 2–4 checkpoints or exports after editing the roster/config workbook.
**Backlog-ref:** 207

## Tasks
- [x] Add Stage 1 fingerprint metadata
  - Files: tournament_scheduler/pipeline/fingerprints.py, tournament_scheduler/pipeline/stage1_config.py, tests/test_stage1_config.py
  - Approach: Add deterministic SHA-256 helpers for the workbook file and effective config payload, store `input_fingerprint` and `effective_config_fingerprint` in the Stage 1 checkpoint, and assert fingerprints change when workbook content changes.
- [x] Mark stale checkpoints from pipeline status
  - Files: tournament_scheduler/pipeline/state.py, tournament_scheduler/cli/reporting.py, tests/test_pipeline_state.py, tests/test_rvv_cli_portability.py
  - Approach: Add a state helper that compares current workbook/effective-config fingerprints to Stage 1 metadata, invalidates Stage 2–4 with a clear stale reason when they differ, and invoke it from status reporting before rendering stage statuses.
- [ ] Verify focused pipeline status behavior
  - Files: tests/test_stage1_config.py, tests/test_pipeline_state.py, tests/test_rvv_cli_portability.py, .ps-next/PLAN.md
  - Approach: Run targeted pytest for Stage 1 fingerprinting, PipelineState stale invalidation, and CLI status portability; fix regressions and record verification evidence.

## Notes
- `input.xlsx` is the canonical pipeline input workbook; Stage 1 checkpoint intentionally stores computed fields plus metadata.
- Existing downstream invalidation already happens when Stage 1 writes DONE/FAILED; the missing case is detecting workbook/config drift between runs when status still shows old checkpoints as done.
- Keep status output human-readable and avoid requiring the full scraping/planning pipeline in tests.

## Acceptance Criteria
- [ ] Stage 1 checkpoints contain `input_fingerprint.sha256` and `effective_config_fingerprint.sha256` after a successful run.
- [ ] `rvv-miniputt status` marks Stage 2, Stage 3, and Stage 4 checkpoints stale/failed when the current workbook fingerprint differs from the Stage 1 checkpoint metadata.
- [ ] Targeted tests pass with `pytest tests/test_stage1_config.py tests/test_pipeline_state.py tests/test_rvv_cli_portability.py`.

## Log


### 2026-07-07 — Mark stale checkpoints from pipeline status
**Done:** Added PipelineState stale detection that recomputes Stage 1 workbook/effective-config fingerprints and marks config plus Stage 2–4 checkpoints failed/stale when they drift; status reporting invokes the check before rendering.
**Rationale:** Status is the first operator-visible command after workbook edits, so running fingerprint comparison there prevents stale done checkpoints and exports from appearing trustworthy.
**Findings:** pytest tests/test_pipeline_state.py tests/test_rvv_cli_portability.py -q passed (27 tests).
**Files:** tournament_scheduler/pipeline/state.py, tournament_scheduler/cli/reporting.py, tests/test_pipeline_state.py, tests/test_rvv_cli_portability.py
**Commit:** not committed
### 2026-07-07 — Add Stage 1 fingerprint metadata
**Done:** Added deterministic Stage 1 fingerprint metadata for workbook bytes and effective config payload; successful Stage 1 runs now write sha256 metadata into the config checkpoint.
**Rationale:** Keeping fingerprints with the checkpoint gives later status/reporting code a stable baseline for detecting workbook/config drift without rerunning the whole pipeline.
**Findings:** pytest tests/test_stage1_config.py -q passed (31 tests). Drift tool did not include the new untracked fingerprints.py in its changed-file list, but the file is expected by the task plan.
**Files:** tournament_scheduler/pipeline/fingerprints.py (new), tournament_scheduler/pipeline/stage1_config.py, tests/test_stage1_config.py
**Commit:** 89d4292
<!-- pi-next appends entries here after each task -->
