# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Stage 1 checkpoints contain `input_fingerprint.sha256` and `effective_config_fingerprint.sha256` after a successful run. | PASS | `tests/test_stage1_config.py::TestRunStage1::test_run_stores_workbook_and_effective_config_fingerprints` asserts both SHA-256 metadata fields after `run()`. |
| `rvv-miniputt status` marks Stage 2, Stage 3, and Stage 4 checkpoints stale/failed when the current workbook fingerprint differs from the Stage 1 checkpoint metadata. | PASS | `tests/test_pipeline_state.py::TestPipelineState::test_input_workbook_fingerprint_change_invalidates_config_and_downstream` and `tests/test_rvv_cli_portability.py::test_status_marks_downstream_stale_when_input_workbook_fingerprint_changes` cover state mutation and rendered status output. |
| Targeted tests pass with `pytest tests/test_stage1_config.py tests/test_pipeline_state.py tests/test_rvv_cli_portability.py`. | PASS | Command completed with `58 passed`. |

Additional check: full `python3 -m pytest -q` was attempted and progressed without failures through 86% of the suite, but exceeded the 300s tool timeout during later unrelated tests.
