# Plan: Export-folder run logs
**Goal:** All structured and human-readable run logs land in the active export folder, and log inspectors prefer that export copy over legacy workspace logs.
**Created:** 2026-07-28
**Intent:** Keep run logs collocated with the exported season-plan artifacts so each run is easy to inspect and archive.

## Tasks
- [x] Add a shared active-run log directory resolver and route update/cancellation writers through it
  - Files: tournament_scheduler/pipeline/run_log_paths.py, tournament_scheduler/pipeline/tournament_updater.py, tournament_scheduler/pipeline/cancellation_workflow.py
  - Approach: introduce one helper that prefers Stage 4 `output_files` parents, then an explicit export dir hint, then falls back to `<work_dir>/logs`; have `log_update()` and `log_cancellation()` use it so they append to the export folder when a run export already exists.
- [x] Reuse the resolver in the pipeline run-log/archive helpers so full runs stay collocated with Stage 4 artifacts
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/cli/run_log_archive.py, tournament_scheduler/cli/reporting.py
  - Approach: replace local export-dir guessing with the shared resolver, keep the human-readable `pipeline_run_*.log` writer and structured JSONL archive in sync, and preserve export-tree preference in list/show/stats output.
- [x] Add regression coverage for export-folder log selection and update the doc wording
  - Files: tests/test_tournament_updater.py, tests/test_cancellation_workflow.py, tests/test_run_log_archive.py, tests/test_pipeline_logs.py, docs/rvv-miniputt-pipeline.md
  - Approach: assert that update/cancellation logs append to the Stage 4 export directory when both export and `.pipeline/logs` exist, and that log listing/showing resolves the export copy; tweak the docs or inline comments so the canonical location matches the code.

## Notes
- `docs/rvv-miniputt-pipeline.md` already says run logs live in the export tree; the code still has legacy `.pipeline/logs` writers that need to stop being the canonical source.
- The Pi log inspector already prefers export-tree run logs, so keep it aligned with the Python reporting path rather than reintroducing workspace-log fallback.

## Acceptance Criteria
- [ ] `TournamentUpdater.log_update()` and `CancellationWorkflow.log_cancellation()` write to the export-folder log when a Stage 4 export exists, not only to `.pipeline/logs`.
- [ ] `rvv-miniputt logs list/show/stats` resolve the export-tree run log when both the export tree and `.pipeline/logs` contain the same run id.
- [ ] Full runs keep `pipeline_run_*.log` and `run-*.jsonl` under the active timestamped export folder.
- [ ] The docs and tests describe the same canonical run-log location.

## Log



### 2026-07-28 — Add regression coverage for export-folder log selection and update the doc wording
**Done:** Added regression coverage for update/cancellation export-folder log routing and export-tree preference in log list/show/stats, and updated pipeline docs to state `.pipeline/logs` is only a fallback.
**Rationale:** Tests lock down the canonical export-tree log location and prevent stale workspace logs from becoming authoritative again.
**Findings:** Targeted regressions pass; the broader quick pytest gate has an unrelated existing failure in `tests/test_stage2_scraping.py::TestUnifiedCache::test_stale_cache_triggers_rescrape`.
**Files:** tests/test_tournament_updater.py, tests/test_cancellation_workflow.py, tests/test_pipeline_logs.py, tests/test_run_log_archive.py, docs/rvv-miniputt-pipeline.md
**Commit:** not committed
### 2026-07-28 — Reuse the resolver in the pipeline run-log/archive helpers so full runs stay collocated with Stage 4 artifacts
**Done:** Reused the shared resolver in the pipeline human-readable run-log directory selection and structured run-log archive posthook; clarified Python log reporting's export-tree-only lookup.
**Rationale:** The full-run and archive paths now apply the same export-folder preference as manual update/cancellation logging.
**Findings:** `rvv-miniputt logs` already ignored `.pipeline/logs` in the Python path; the code now documents that behavior at the lookup site.
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/cli/run_log_archive.py, tournament_scheduler/cli/reporting.py
**Commit:** not committed
### 2026-07-28 — Add a shared active-run log directory resolver and route update/cancellation writers through it
**Done:** Added `tournament_scheduler/pipeline/run_log_paths.py` and routed tournament update/cancellation JSONL writers through the shared active export-folder resolver.
**Rationale:** Centralizing the Stage 4 output-file lookup prevents manual workflows from treating `.pipeline/logs/` as the canonical log directory after an export exists.
**Findings:** The first task's implementation touched downstream CLI/test/doc files as part of the same small issue #29 change set; plan drift was expected and is covered by subsequent tasks.
**Files:** tournament_scheduler/pipeline/run_log_paths.py, tournament_scheduler/pipeline/tournament_updater.py, tournament_scheduler/pipeline/cancellation_workflow.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
