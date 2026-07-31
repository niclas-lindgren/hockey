# Plan: Auto-publish routine content when canonical inputs change
**Goal:** Two path-triggered GitHub Actions workflows (activities and registrations) that regenerate and publish only their owned outputs, plus Power Automate integration docs.
**Created:** 2026-07-31
**Intent:** Remove the manual trigger requirement for routine content updates. When Power Automate or an operator commits an approved input snapshot, the matching workflow regenerates and publishes only the affected public content.
**Backlog-ref:** 49 (GitHub)

## Tasks
- [x] Create inputs/ directory structure with .gitkeep placeholders
  - Files: inputs/activities/.gitkeep, inputs/registrations/.gitkeep, inputs/season/.gitkeep
  - Approach: Create the canonical input directories referenced in the issue. Do not move or rename existing files — the Makefile defaults stay unchanged.

- [x] Create .github/workflows/activity-publish.yml
  - Files: .github/workflows/activity-publish.yml
  - Approach: Path-triggered on `inputs/activities/activities.xlsx`. Follow the established pattern from season-publish.yml: checkout, setup Python, install deps, validate (fingerprint + `scripts/check quick`), run `scripts/rvv-miniputt activities --input inputs/activities/activities.xlsx --publish --confirm-public`, upload artifacts on failure. Use concurrency group, least-privilege permissions, environment protection. Reference CI docs conventions.

- [x] Create registration-to-workbook sync module
  - Files: tournament_scheduler/pipeline/registration_sync.py, tests/test_registration_sync.py
  - Approach: Write a module that reads `inputs/registrations/registered-teams.csv`, validates it with the existing `build_registered_teams_payload`, then updates only the `Lag` sheet of `inputs/season/input.xlsx` (or root `input.xlsx` as fallback). Preserve all other sheets. Return a boolean indicating whether changes were made.

- [x] Create .github/workflows/registration-publish.yml
  - Files: .github/workflows/registration-publish.yml
  - Approach: Path-triggered on `inputs/registrations/registered-teams.csv`. Validate CSV, sync registration rows into the season workbook (via the new sync module), commit workbook update with `[bot]` message containing `[skip ci]` to prevent recursion, then run `scripts/rvv-miniputt registered-teams --csv inputs/registrations/registered-teams.csv --publish --confirm-public`. Use separate concurrency group, least-privilege permissions.

- [x] Create docs/power-automate-github-sync.md
  - Files: docs/power-automate-github-sync.md
  - Approach: Document the end-to-end flow for both activities (Teams → SharePoint → Power Automate → GitHub) and registrations (Microsoft Forms → Power Automate → SharePoint List → GitHub). Cover PAT setup, concurrency, content comparison, commit strategy, ownership, recovery. Follow the pragmatic guidance from the issue comments: prefer fine-grained PAT over GitHub App, document the simpler path first.

- [x] Extend tests for new GitHub Actions workflows
  - Files: tests/test_github_actions_operator_workflows.py
  - Approach: Add test functions for activity-publish.yml and registration-publish.yml following the existing test pattern. Verify: manual/workflow_dispatch support, path-trigger on push, canonical CLI delegation, permission boundaries, concurrency groups, artifact uploads, loop prevention markers, and absence of forbidden fragments (direct gh-pages, pipeline module calls).

## Notes
- The Makefile `aktivitetskalender-publish` and `registered-teams-publish` targets already exist and delegate to `scripts/rvv-miniputt`. The workflows will use the CLI directly for finer control over input paths.
- Existing season workflows (validate, review-bundle, publish, rollback) are unchanged and remain the browser-dispatched entrypoints for full season planning.
- The `inputs/` directory is new; no existing files are moved. The root `Årshjul for aktiviteter.xlsx` and `input.xlsx` stay where they are.
- Activity publish uses `rvv-miniputt activities --publish --confirm-public` which reuses the operator publish path (sanitization, approval gating, fingerprinting, verification).
- Registration publish uses `rvv-miniputt registered-teams --publish --confirm-public` which similarly reuses the operator publish path.
- Both workflows must serialize publication via concurrency groups since they write to the same gh-pages branch.
- The registration workflow commits workbook updates with `[skip ci]` in the commit message to prevent recursion.

## Acceptance Criteria
- [ ] Changing only `inputs/activities/activities.xlsx` automatically regenerates and publishes only activity-calendar-owned outputs.
- [ ] Changing only `inputs/registrations/registered-teams.csv` automatically updates registration-owned workbook rows and publishes Påmeldte lag outputs.
- [ ] Neither workflow runs full season-plan generation.
- [ ] Unrelated Pages content is preserved.
- [ ] Failed validation never changes the public site.
- [ ] Concurrent publication attempts are serialized safely.
- [ ] Generated workbook commits do not cause recursive workflow loops.
- [ ] Identical inputs do not create unnecessary commits or publications.
- [ ] Failure artifacts are sufficient for a volunteer to diagnose and retry.
- [ ] Both workflows contain `workflow_dispatch` with the same input parameters as their path triggers.
- [ ] `docs/power-automate-github-sync.md` exists and contains setup, security, ownership, and recovery sections.
- [ ] Tests pass and verify valid changes, invalid inputs, unchanged inputs, concurrent publication, and loop prevention.

## Log






### 2026-07-31 — Extend tests for new GitHub Actions workflows
**Done:** Extended tests/test_github_actions_operator_workflows.py with 6 new test functions covering both new workflow files: path triggers, CLI delegation, concurrency groups, loop prevention, artifact uploads, and absence of full season planning.
**Rationale:** Tests validate the same invariants as browser operator workflows: CLI delegation, permission boundaries, artifact completeness, and absence of direct gh-pages/pipeline module calls.
**Findings:** YAML multi-line commit message in registration-publish.yml caused parser errors; fixed by using multiple -m flags. PyYAML's 1.1 boolean handling requires checking both on key forms.
**Files:** tests/test_github_actions_operator_workflows.py (extended)
**Commit:** not committed
### 2026-07-31 — Create docs/power-automate-github-sync.md
**Done:** Created docs/power-automate-github-sync.md with end-to-end integration docs for both activity and registration flows, PAT setup, Power Automate steps, concurrency, ownership, recovery, and security.
**Rationale:** Single document covers both flows coherently. Recovery paths include both manual workflow dispatch and direct make commands.
**Findings:** Issue comments explicitly recommended fine-grained PAT over GitHub App for simplicity. Concurrency group shared between both routine workflows. [skip ci] in commit messages prevents recursive triggers.
**Files:** docs/power-automate-github-sync.md (new)
**Commit:** not committed
### 2026-07-31 — Create .github/workflows/registration-publish.yml
**Done:** Created .github/workflows/registration-publish.yml with path trigger on inputs/registrations/registered-teams.csv, CSV validation, workbook sync step with [skip ci] commit, and publish delegation.
**Rationale:** Two-phase design: workbook update commits to main with loop prevention, then Pages publish goes to gh-pages. If sync fails, publish is skipped.
**Findings:** Workbook sync uses Python inline script with GITHUB_OUTPUT for downstream step gating. Commit uses [skip ci] to prevent recursive triggers. Path filter on inputs/registrations/registered-teams.csv ensures workbook commits don't re-trigger.
**Files:** .github/workflows/registration-publish.yml (new)
**Commit:** not committed
### 2026-07-31 — Create registration-to-workbook sync module
**Done:** Created tournament_scheduler/pipeline/registration_sync.py with sync_registered_teams_to_workbook() and tests/test_registration_sync.py with 12 tests covering no-change, new/add/remove/update, dry-run, and error paths.
**Rationale:** Clean separation: sync module only writes the Lag sheet, preserving all other sheets. Semantic comparison (casefolded keys) prevents unnecessary commits.
**Findings:** Openpyxl validates file format by extension — temp file must end with .xlsx. RegisteredTeamsValidationError wraps to RegistrationSyncError for uniform caller handling.
**Files:** tournament_scheduler/pipeline/registration_sync.py (new), tests/test_registration_sync.py (new)
**Commit:** not committed
### 2026-07-31 — Create .github/workflows/activity-publish.yml
**Done:** Created .github/workflows/activity-publish.yml with path trigger on inputs/activities/activities.xlsx, workflow_dispatch support, input fingerprinting, canonical check delegation, and failure artifact uploads.
**Rationale:** Single invocation is simpler and the CLI already handles the full fetch→prepare→publish flow. Input validation happens via the CLI's own checks and the earlier scripts/check quick step.
**Findings:** activities subcommand supports --publish --confirm-public --json but not --log-level; used single invocation pattern since cmd_activities handles fetch→prepare→publish chain internally. Shared routine-publish concurrency group with registration workflow.
**Files:** .github/workflows/activity-publish.yml (new)
**Commit:** not committed
### 2026-07-31 — Create inputs/ directory structure with .gitkeep placeholders
**Done:** Created inputs/activities/.gitkeep, inputs/registrations/.gitkeep, inputs/season/.gitkeep
**Rationale:** Establishes the canonical input directory layout referenced in issue #49 without moving or renaming any existing files.
**Findings:** No existing inputs/ directory existed. Root-level files (input.xlsx, Årshjul for aktiviteter.xlsx) remain untouched.
**Files:** 3 new .gitkeep files in inputs/ subdirectories
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
