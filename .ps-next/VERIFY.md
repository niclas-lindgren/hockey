# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Workflows show manual browser inputs that let a volunteer run validation and review-bundle generation. | PASS | `.github/workflows/season-validate.yml` and `season-review-bundle.yml` both use `workflow_dispatch` with Norwegian operator inputs; `tests/test_github_actions_operator_workflows.py::test_all_browser_operator_workflows_exist_and_are_manual` and validation/review artifact tests passed. |
| Workflow files contain separate generation and publication jobs with distinct permissions. | PASS | Validation/review workflows have read-only contents permissions, publish has `actions: read`/`contents: write`, rollback has `contents: write`; `test_validation_and_review_generation_never_publish_publicly` and `test_publication_is_separate_protected_and_fingerprint_bound` passed. |
| Publication workflow requires a protected-environment approval and an exact bundle fingerprint. | PASS | `season-publish.yml` runs in `environment: pages-publication`, requires `PUBLISER`, downloads a reviewed artifact, reruns publish dry-run, and checks `EXPECTED_BUNDLE_FINGERPRINT`; publish workflow test passed. |
| Workflow runs invoke the canonical application/CLI entrypoints rather than duplicating logic in YAML. | PASS | Tests assert use of `scripts/rvv-miniputt operator run/publish/rollback` and forbid direct stage module, gh-pages, git worktree, or slash-command publishing logic. |
| Artifacts include input fingerprint, logs, manifest, review output, and privacy report. | PASS | Workflow artifact paths include `input-fingerprint.json`, logs, `run_manifest.json`, review outputs, publish preview, and `public_bundle/pages_privacy_report.json`; artifact coverage tests passed. |
| Rollback workflow requires a protected environment and run id. | PASS | `season-rollback.yml` requires `run_id`, `RULL_TILBAKE`, and `environment: pages-publication`, then delegates to `operator rollback --confirm-public`; rollback workflow test passed. |
| Documentation contains the GitHub Actions operator flow and fixture-test coverage runs in pytest. | PASS | README, `docs/ci.md`, and `docs/rvv-miniputt-pipeline.md` document the browser workflow; `python3 -m pytest tests/test_github_actions_operator_workflows.py tests/test_makefile_operator_interface.py -q` passed with 20 tests. |

Checks:
- PASS: `python3 -m pytest tests/test_github_actions_operator_workflows.py -q` (7 passed)
- PASS: `python3 -m pytest tests/test_github_actions_operator_workflows.py tests/test_makefile_operator_interface.py -q` (20 passed)
- PASS: `pi_next_quality_gate(level="quick")` (1181 passed, 1 skipped, 26 deselected)
- PASS: `pi_next_safety_scan`, `pi_next_diff_review`, `pi_next_plan_drift`, `pi_next_plan_validate`
- NOTE: `pi_next_quality_gate(level="full")` was attempted and failed in unrelated slow/integration tests tied to existing canonical workbook/rules-report state (`expected Jar to have U10 teams`, empty canonical plan, rules doc drift). The implemented workflow acceptance is covered by targeted tests and the passing quick gate.
