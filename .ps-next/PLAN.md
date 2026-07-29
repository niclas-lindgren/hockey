# Plan: Makefile non-LLM operator interface
**Goal:** Implement GitHub issue #39 by making the root Makefile a complete, guarded, self-documenting thin adapter for deterministic and explicitly human-controlled workflows.
**Created:** 2026-07-29
**Intent:** Human operators should discover and run the supported portable RVV workflow without copying commands from scattered docs or bypassing safety gates.

## Tasks
- [x] Add canonical check/release adapters and expand the Makefile menu
  - Files: Makefile, scripts/check, scripts/release, tests/test_makefile_operator_interface.py
  - Approach: Replace raw tag publishing with guarded `scripts/release`, add `scripts/check` as the canonical verification entrypoint, set `.DEFAULT_GOAL := help`, add grouped phony targets for setup/checking, planning, human decisions, publishing/recovery, desktop/build/cleanup/release, validate required variables/confirmations in recipes, preserve `ARGS` forwarding, and add faked-command tests for help, delegation, safeguards, quoting, and exit-code preservation.
- [x] Document Make targets alongside direct CLI equivalents
  - Files: README.md, docs/rvv-miniputt-pipeline.md, tests/test_makefile_operator_interface.py
  - Approach: Update operator docs to present `make` as the concise human menu while keeping direct `scripts/rvv-miniputt` equivalents; document intentionally excluded LLM-only commands and mutation warnings; add drift tests that documented targets exist in the Makefile/help output.
- [x] Wire CI docs/workflow to the canonical check command where practical
  - Files: .github/workflows/ci.yml, docs/ci.md, scripts/check, tests/test_makefile_operator_interface.py
  - Approach: Update CI/documentation so the canonical `scripts/check` command is visible as the local equivalent; add phase selectors to `scripts/check` if needed so matrix jobs can call the canonical entrypoint without duplicating shell command sequences; add assertions that `make check` delegates only to `scripts/check` and CI/docs mention the canonical entrypoint.

## Notes
- Source issue: https://github.com/niclas-lindgren/hockey/issues/39 (`[P2] Expand Makefile into a complete non-LLM operator interface`).
- Related issues #36 and #37 are still open, so this plan includes lightweight `scripts/check` and guarded `scripts/release` rather than pointing Make at missing commands.
- Make recipes must remain adapters; canonical behavior stays in `scripts/rvv-miniputt`, Python CLI, repository scripts, npm scripts, and the new scripts.
- Pre-existing dirty worktree note: untracked `Årshjul for aktiviteter.xlsx` was present before this plan and should not be touched or committed.

## Acceptance Criteria
- [ ] `make help` lists grouped setup, planning, human-decision, publication/recovery, desktop, cleanup, and release targets.
- [ ] Make targets delegate to canonical scripts/CLI commands and no default/all/normal run target publishes publicly.
- [ ] Publish, rollback, release, and cleanup targets return clear errors when required variables or confirmations are missing.
- [ ] Human answers with spaces/special shell characters are passed as one CLI argument in tests.
- [ ] `make check` delegates to `scripts/check`, and `make release`/`make release-dry-run` delegate to guarded `scripts/release`.
- [ ] README/operator docs contain the Make workflow and direct command equivalents.
- [ ] Automated tests cover Makefile help/delegation/safeguards/documentation drift without publishing, pushing tags, or deleting real build/user data.
- [ ] run: pytest tests/test_makefile_operator_interface.py

## Log



### 2026-07-29 — Wire CI docs/workflow to the canonical check command where practical
**Done:** Extended scripts/check with named phase selectors, updated CI jobs to call scripts/check phases instead of raw pytest command sequences for the split status checks, and updated CI docs/tests to describe and guard the canonical entrypoint relationship.
**Rationale:** This keeps GitHub's visible matrix checks while moving the underlying command ownership into scripts/check, with make check remaining the local full-suite adapter.
**Findings:** Targeted pytest tests/test_makefile_operator_interface.py passed: 13 passed. Quick pi-next quality gate passed: 1168 passed, 1 skipped, 26 deselected.
**Files:** .github/workflows/ci.yml (-raw pytest runs, +scripts/check phase runs), docs/ci.md, scripts/check (+phase selectors), tests/test_makefile_operator_interface.py
**Commit:** not committed
### 2026-07-29 — Document Make targets alongside direct CLI equivalents
**Done:** Updated README and pipeline guide to introduce `make help` as the non-LLM human operator menu, map Make targets to direct scripts/rvv-miniputt or scripts/release equivalents, document mutation warnings, and note that harness-only features stay intentionally excluded from Make. Added a doc drift regression test.
**Rationale:** Operators can now use Make for discoverability while documentation preserves the canonical direct CLI path for scripts and harnesses.
**Findings:** Targeted pytest tests/test_makefile_operator_interface.py passed: 12 passed. Quick pi-next quality gate passed: 1167 passed, 1 skipped, 26 deselected.
**Files:** README.md (+28), docs/rvv-miniputt-pipeline.md (+32/-2), tests/test_makefile_operator_interface.py (+36)
**Commit:** not committed
### 2026-07-29 — Add canonical check/release adapters and expand the Makefile menu
**Done:** Expanded Makefile into grouped help/default operator menu with deterministic targets for setup/checks, planning, questions, Pages preview/publish/recovery, desktop packaging/cleanup, and guarded release. Added scripts/check and scripts/release as canonical adapters for related open issues #36/#37, and regression tests that fake CLI calls to verify delegation, safeguards, argument handling, and failure masking.
**Rationale:** Make remains a thin adapter over scripts/rvv-miniputt, repository scripts, npm, and the guarded release/check scripts while exposing a discoverable non-LLM workflow to humans.
**Findings:** Targeted pytest tests/test_makefile_operator_interface.py passed: 11 passed. Quick pi-next quality gate passed: 1166 passed, 1 skipped, 26 deselected.
**Files:** Makefile (rewritten), scripts/check (new), scripts/release (new), tests/test_makefile_operator_interface.py (new)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
