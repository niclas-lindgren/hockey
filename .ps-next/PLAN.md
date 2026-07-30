# Plan: GitHub Actions season operation workflows
**Goal:** Add browser-based GitHub Actions entrypoints for routine RVV Miniputt validation, review-bundle generation, approved publication, and rollback without bypassing existing CLI safeguards.
**Created:** 2026-07-30
**Intent:** Club volunteers should be able to run routine season operations from GitHub's browser UI while generation, publishing, and rollback remain separate, auditable, and permission-gated.

## Tasks
- [x] Add manual GitHub Actions workflows for validation, review bundle generation, publication, and rollback
  - Files: .github/workflows/season-validate.yml, .github/workflows/season-review-bundle.yml, .github/workflows/season-publish.yml, .github/workflows/season-rollback.yml
  - Approach: Use workflow_dispatch inputs with Norwegian descriptions, least-privilege permissions, concurrency, Python setup, dependency install, canonical scripts/rvv-miniputt or Make targets, artifact upload, and no hidden publish in validation/generation. Put actual publish/rollback behind protected environments and explicit confirm inputs.
- [ ] Add workflow regression tests
  - Files: tests/test_github_actions_operator_workflows.py
  - Approach: Parse the workflow YAML files, assert workflow_dispatch inputs, permission boundaries, canonical CLI entrypoints, artifact uploads, separation of generation from publication, protected publish/rollback environments, explicit confirmation/fingerprint/run-id safeguards, and absence of dangerous ad-hoc commands.
- [ ] Document the browser-based operations flow
  - Files: docs/ci.md, docs/rvv-miniputt-pipeline.md, README.md
  - Approach: Describe who uses each workflow, inputs, artifacts, approval separation, protected environments, and the equivalent local CLI/Make commands. Link the docs prominently from the existing operator sections.
- [ ] Run checks and archive
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

### 2026-07-30 — Add manual GitHub Actions workflows for validation, review bundle generation, publication, and rollback
**Done:** Added four workflow_dispatch workflows for validation, review-bundle generation, protected publication, and protected rollback using the canonical scripts/rvv-miniputt operator commands.
**Rationale:** Kept GitHub Actions as thin browser adapters over existing operator capabilities so scheduling, sanitization, publishing, and rollback policy remain in application code.
**Findings:** Publish workflow downloads the approved review artifact and verifies the provided bundle_fingerprint before running the confirmed publish path; validation/review workflows never pass --confirm-public.
**Files:** .github/workflows/season-validate.yml; .github/workflows/season-review-bundle.yml; .github/workflows/season-publish.yml; .github/workflows/season-rollback.yml; .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
