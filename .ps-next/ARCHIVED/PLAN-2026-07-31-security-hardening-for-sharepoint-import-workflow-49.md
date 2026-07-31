# Plan: Security hardening for SharePoint import workflow (#49)
**Goal:** Hard-code the write destination, add trusted-author guard, and validate SharePoint identifiers so a trigger issue cannot write outside `inputs/activities/activities.xlsx`.
**Created:** 2026-07-31
**Intent:** Repository settings restrict issue creation to collaborators, but the workflow must enforce its own guards: trusted author, hard-coded destination, and identifier validation. Belt-and-suspenders.
**Backlog-ref:** 49 (GitHub)

## Tasks
- [ ] Harden .github/workflows/sharepoint-import.yml
  - Files: .github/workflows/sharepoint-import.yml, tests/test_github_actions_operator_workflows.py
  - Approach: (1) Add `author_association in (OWNER, MEMBER, COLLABORATOR)` to job `if:`. (2) Keep parsing `target_path` for contract validation but hard-code `CANONICAL_PATH = inputs/activities/activities.xlsx` in the download and commit steps. (3) Add optional `EXPECTED_DRIVE_ID` and `EXPECTED_DRIVE_ITEM_ID` env vars that, when set, validate the issue's values match. (4) Add tests: untrusted author skipped, wrong source rejected, wrong target_path rejected (contract validation), malicious path not written (hard-coded destination), identifier mismatch rejected.

## Notes
- The `target_path` field in the issue body is still parsed and validated (must be `inputs/activities/activities.xlsx`), but the actual write destination is hard-coded and ignores the parsed value.
- This is a focused security fix on the existing workflow. The activity-publish and registration-publish workflows are unchanged.
- Tests must verify the new `if:` condition includes author_association, and that the hard-coded path cannot be overridden.

## Acceptance Criteria
- [ ] Run the import workflow and confirm the job-level `if:` condition checks `author_association`.
- [ ] Show that the actual destination path is hard-coded and cannot be controlled by issue content.
- [ ] Show that a `target_path` other than `inputs/activities/activities.xlsx` is rejected at the contract validation step.
- [ ] Tests pass and cover untrusted author, wrong source, wrong target_path, malicious path, and identifier mismatch.

## Log
