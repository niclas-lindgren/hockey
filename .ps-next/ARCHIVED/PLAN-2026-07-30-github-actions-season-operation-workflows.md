# Plan: GitHub Actions season operation workflows
**Goal:** Add browser-based GitHub Actions entrypoints for routine RVV Miniputt validation, review-bundle generation, approved publication, and rollback without bypassing existing CLI safeguards.
**Created:** 2026-07-30
**Intent:** Club volunteers should be able to run routine season operations from GitHub's browser UI while generation, publishing, and rollback remain separate, auditable, and permission-gated.

## Tasks
- [x] Add manual GitHub Actions workflows for validation, review bundle generation, publication, and rollback
  - Files: .github/workflows/season-validate.yml, .github/workflows/season-review-bundle.yml, .github/workflows/season-publish.yml, .github/workflows/season-rollback.yml
  - Approach: Use workflow_dispatch inputs with Norwegian descriptions, least-privilege permissions, concurrency, Python setup, dependency install, canonical scripts/rvv-miniputt or Make targets, artifact upload, and no hidden publish in validation/generation. Put actual publish/rollback behind protected environments and explicit confirm inputs.
- [x] Add workflow regression tests
  - Files: tests/test_github_actions_operator_workflows.py
  - Approach: Parse the workflow YAML files, assert workflow_dispatch inputs, permission boundaries, canonical CLI entrypoints, artifact uploads, separation of generation from publication, protected publish/rollback environments, explicit confirmation/fingerprint/run-id safeguards, and absence of dangerous ad-hoc commands.
- [x] Document the browser-based operations flow
  - Files: docs/ci.md, docs/rvv-miniputt-pipeline.md, README.md
  - Approach: Describe who uses each workflow, inputs, artifacts, approval separation, protected environments, and the equivalent local CLI/Make commands. Link the docs prominently from the existing operator sections.
- [x] Run checks and archive
  - Files: .ps-next/PLAN.md, .ps-next/VERIFY.md
  - Approach: Run targeted workflow tests, quick quality gate where feasible, pi-next safety/diff/drift scans, then verify acceptance criteria and archive the plan.

## Notes
Selected GitHub issue: #45 "[P1] Add browser-based GitHub Actions workflows for routine season operation".
Existing canonical entrypoints are `scripts/rvv-miniputt`, `make operator-run`, `make publish-preview`, `make publish CONFIRM_PUBLIC=1`, and `make rollback RUN_ID=<id> CONFIRM_PUBLIC=1`; workflows must wrap these rather than duplicating scheduling/publishing logic in YAML.
Do not touch the user's untracked `Årshjul for aktiviteter.xlsx` file.

## Acceptance Criteria
- [ ] Workflows show manual browser inputs that let a volunteer run validation and review-bundle generation.
- [ ] Workflow files contain separate generation and publication jobs with distinct permissions.
- [ ] Publication workflow requires a protected-environment approval and an exact bundle fingerprint.
- [ ] Workflow runs invoke the canonical application/CLI entrypoints rather than duplicating logic in YAML.
- [ ] Artifacts include input fingerprint, logs, manifest, review output, and privacy report.
- [ ] Rollback workflow requires a protected environment and run id.
- [ ] Documentation contains the GitHub Actions operator flow and fixture-test coverage runs in pytest.

## Log




### 2026-07-30 — Run checks and archive
**Done:** Ran targeted workflow/docs tests and the quick Python quality gate, then ran pi-next safety, diff-review, drift, and plan-structure checks.
**Rationale:** The quick gate exercises the full non-slow/non-integration suite, and targeted tests cover the new workflow contract without requiring live GitHub Actions or public publishing.
**Findings:** Quality gate passed: 1181 passed, 1 skipped, 26 deselected. Targeted tests passed: 20 passed. Safety scan, diff review, plan drift, and PLAN validation passed.
**Files:** .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-30 — Document the browser-based operations flow
**Done:** Documented the manual GitHub Actions operator flow in README, CI docs, and the pipeline guide, including workflow purposes, artifacts, permission boundaries, protected publishing, rollback, and equivalent CLI/Make delegation.
**Rationale:** Operators need one discoverable browser path while maintainers need CI documentation explaining why these workflows are operational entrypoints rather than PR checks.
**Findings:** No separate operator-handbook file exists yet, so the flow is linked from the current README/operator and pipeline docs.
**Files:** README.md; docs/ci.md; docs/rvv-miniputt-pipeline.md; .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-30 — Add workflow regression tests
**Done:** Added pytest regression coverage that parses all four season-operation workflows and asserts manual dispatch, permission boundaries, canonical CLI delegation, artifact contents, publish fingerprint checks, protected environments, rollback safeguards, and forbidden direct publishing patterns.
**Rationale:** Static workflow tests catch drift without needing to run live GitHub Actions or publish Pages during CI.
**Findings:** PyYAML parses the GitHub Actions `on` key as boolean True in this environment, so the helper supports both representations.
**Files:** tests/test_github_actions_operator_workflows.py; .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-30 — Add manual GitHub Actions workflows for validation, review bundle generation, publication, and rollback
**Done:** Added four workflow_dispatch workflows for validation, review-bundle generation, protected publication, and protected rollback using the canonical scripts/rvv-miniputt operator commands.
**Rationale:** Kept GitHub Actions as thin browser adapters over existing operator capabilities so scheduling, sanitization, publishing, and rollback policy remain in application code.
**Findings:** Publish workflow downloads the approved review artifact and verifies the provided bundle_fingerprint before running the confirmed publish path; validation/review workflows never pass --confirm-public.
**Files:** .github/workflows/season-validate.yml; .github/workflows/season-review-bundle.yml; .github/workflows/season-publish.yml; .github/workflows/season-rollback.yml; .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
