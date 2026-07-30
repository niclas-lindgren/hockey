# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Stage 4 can run with an explicit build timestamp or `SOURCE_DATE_EPOCH` and writes stable `generated_at` metadata. | PASS | `tests/test_stage4_export.py::test_explicit_build_timestamp_controls_metadata_and_timestamped_directory` and `test_source_date_epoch_controls_stage4_build_timestamp` pass. |
| Two Stage 4 runs with identical inputs and build timestamp produce identical file bytes for JSON/HTML, ICS, report, and XLSX outputs where present. | PASS | `tests/test_stage4_export.py::test_same_build_timestamp_produces_identical_export_file_bytes` hashes the complete export tree across two runs and passes. |
| The public bundle fingerprint is identical for unchanged content and changes when a meaningful plan input changes. | PASS | `tests/test_stage4_export.py::test_public_bundle_fingerprint_is_stable_for_unchanged_export_content` passes using `build_public_bundle()` and `bundle_fingerprint()`. |
| XLSX/ZIP container metadata is normalized enough that workbook exports no longer drift solely because of write time. | PASS | The identical export-tree hash regression includes main, Spond, and per-club review `.xlsx` workbooks. |
| The reproducibility contract and intentional operational timestamp exceptions are documented. | PASS | `docs/rvv-miniputt-pipeline.md` now documents `SOURCE_DATE_EPOCH`, standalone `--build-timestamp`, stable `generated_at`, XLSX/ZIP normalization, public bundle fingerprints, and audit timestamp exceptions. |
| Relevant tests pass via `pytest tests/test_stage4_export.py`. | PASS | `pytest tests/test_stage4_export.py tests/test_pages_bundle.py tests/test_review_packets.py -q` -> 65 passed; `pytest tests/test_ical_exporter.py tests/test_stage4_export.py -q` -> 49 passed; standard gate `python3 -m pytest -q -m "not slow and not integration"` -> 1194 passed, 1 skipped, 26 deselected. |

## Notes

`pi_next_quality_gate(level="full")` / full pytest with slow+integration tests still fails in pre-existing canonical-real-roster tests because the current `input.xlsx` has an empty `Lag` roster (`teams` list empty), causing unrelated Stage 1/Stage 3/Jar U10 assertions to fail. The standard non-slow/non-integration gate passes after this implementation.
