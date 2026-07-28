# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `TournamentUpdater.log_update()` and `CancellationWorkflow.log_cancellation()` write to the export-folder log when a Stage 4 export exists, not only to `.pipeline/logs`. | PASS | `tests/test_tournament_updater.py::TestCheckpointRoundTrip::test_log_update_writes_jsonl_entry` and `tests/test_cancellation_workflow.py::TestLogCancellation::test_log_writes_jsonl_entry` assert returned log paths are under the Stage 4 export folder despite a legacy `.pipeline/logs` file. |
| `rvv-miniputt logs list/show/stats` resolve the export-tree run log when both the export tree and `.pipeline/logs` contain the same run id. | PASS | `tests/test_pipeline_logs.py::test_logs_reporting_prefers_export_tree_over_legacy_workspace_logs` asserts list/show/stats use the export copy and ignore the conflicting legacy failure log. |
| Full runs keep `pipeline_run_*.log` and `run-*.jsonl` under the active timestamped export folder. | PASS | `_resolve_run_log_dir()` delegates to `resolve_active_run_log_dir()` with the timestamped export dir hint, and `tests/test_run_log_archive.py` verifies structured JSONL logs are copied into the latest export run dir and root. |
| The docs and tests describe the same canonical run-log location. | PASS | `docs/rvv-miniputt-pipeline.md` now states export tree is canonical and `.pipeline/logs/` is only a fallback; regression tests assert the same behavior. |

Checks run:
- `python3 -m pytest -q tests/test_tournament_updater.py::TestCheckpointRoundTrip::test_log_update_writes_jsonl_entry tests/test_cancellation_workflow.py::TestLogCancellation::test_log_writes_jsonl_entry tests/test_pipeline_logs.py tests/test_run_log_archive.py` — PASS (6 tests).
- `python3 -m py_compile tournament_scheduler/pipeline/run_log_paths.py tournament_scheduler/pipeline/tournament_updater.py tournament_scheduler/pipeline/cancellation_workflow.py tournament_scheduler/cli/pipeline_orchestrator.py tournament_scheduler/cli/run_log_archive.py tournament_scheduler/cli/reporting.py tests/test_pipeline_logs.py` — PASS.
- `python3 -m pytest -q -m "not slow and not integration"` — FAIL due unrelated existing `tests/test_stage2_scraping.py::TestUnifiedCache::test_stale_cache_triggers_rescrape` expecting `_run_outlook_scraper` to be called once but observing zero calls.
