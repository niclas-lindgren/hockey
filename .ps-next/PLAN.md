# Plan: GitHub issue #47 — Påmeldte lag page
**Goal:** `make registered-teams` and `make registered-teams-publish` generate and safely publish a standalone public Påmeldte lag page from a SharePoint CSV export.
**Created:** 2026-07-30
**Intent:** Give RVV organizers a deterministic, privacy-safe registered-team overview that can be updated independently of the season-planning pipeline.

## Tasks
- [x] Add registered-team CSV parsing and validation
  - Files: tournament_scheduler/pipeline/registered_teams.py, tests/test_registered_teams.py
  - Approach: Create a focused module that reads UTF-8/UTF-8-BOM CSV, requires club/label/age_group, trims whitespace, detects duplicate normalized rows, ignores/report extra columns, optionally validates age groups from JSON config, and returns deterministic public payload plus private validation metadata.
- [x] Render standalone Påmeldte lag artifacts
  - Files: tournament_scheduler/pipeline/registered_teams.py, tests/test_registered_teams.py
  - Approach: Extend the module with artifact generation for registered-teams/pameldte-lag.html, registered-teams/pameldte-lag.json, and registered-teams/validation-report.json; render responsive Norwegian HTML without requiring JavaScript, with grouped age groups, counts, empty state, escaped values, and no extra/private CSV fields in public outputs.
- [x] Wire CLI, Make targets, and Pages publication staging
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/pipeline/registered_teams.py, tournament_scheduler/pipeline/pages_bundle.py, Makefile, tests/test_registered_teams_publish.py, tests/test_pages_bundle.py
  - Approach: Add `rvv-miniputt registered-teams` with generation and guarded `--publish --confirm-public` behavior mirroring the activity-calendar overlay-on-latest workflow; add public bundle allowlist for registered-teams artifacts and thin Make targets `registered-teams`/`registered-teams-publish`.
- [x] Document operator workflow and verify end-to-end behavior
  - Files: README.md, .ps-next/PLAN.md
  - Approach: Add the registered-team workflow to the operator command table and standalone content-update guidance, then run targeted pytest plus a broader quality gate and mechanical acceptance verification.

## Notes
Source: GitHub issue #47, "[P1] Generate and publish standalone \"Påmeldte lag\" HTML from SharePoint CSV".
The issue is related to #31/#39/#45/#46 but this plan must not depend on workbook generation, season-plan stages, or activity-calendar regeneration.
Follow the existing activity calendar pattern: Make stays thin; CLI/application code owns validation, rendering, staging, and publish safety.
Public artifacts must include only club, label, age_group, public counts, and generation metadata; source fingerprints/local paths belong only in validation-report.json.

## Acceptance Criteria
- [ ] run: make registered-teams CSV=/tmp/rvv-registered-teams-empty.csv ARGS='--export-dir /tmp/rvv-registered-teams-review --generated-at 2026-07-30T12:00:00Z --no-base-latest'
- [ ] run: python3 -m pytest tests/test_registered_teams.py tests/test_registered_teams_publish.py tests/test_pages_bundle.py
- [ ] Makefile contains registered-teams-publish target (grep: Makefile:registered-teams-publish)
- [ ] README.md contains Påmeldte lag operator guidance (grep: README.md:Påmeldte lag)
- [ ] CLI parser contains registered-teams command (grep: tournament_scheduler/cli/args.py:registered-teams)

## Log




### 2026-07-30 — Document operator workflow and verify end-to-end behavior
**Done:** Documented the Påmeldte lag Make/CLI workflow in README, updated prior task commit metadata in PLAN, and verified the Make preview command, targeted tests, grep checks, plan validation, safety scan, diff review, plan drift, and standard quality gate.
**Rationale:** The operator-facing README now presents this as a routine standalone content update and the final verification evidence is captured before archive.
**Findings:** The standalone Make preview generates the header-only empty state into the requested review directory without publishing.
**Files:** README.md, .ps-next/PLAN.md
**Commit:** a0098ee
### 2026-07-30 — Wire CLI, Make targets, and Pages publication staging
**Done:** Added the `registered-teams` CLI command, Make targets, staging-on-current-latest publication preparation, Pages bundle allowlisting for registered-teams public artifacts, and tests for CLI preview/staging/bundle privacy behavior.
**Rationale:** Mirroring the activity-calendar overlay flow preserves unrelated Pages files, keeps Make thin, and reuses the existing guarded operator publish path for confirmation, sanitization, idempotent publication, and verification.
**Findings:** `registered-teams/validation-report.json` is generated for local review but explicitly excluded from the public Pages bundle so source fingerprints and validation metadata are not published.
**Files:** tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/pipeline/registered_teams.py, tournament_scheduler/pipeline/pages_bundle.py, Makefile, tests/test_registered_teams_publish.py, tests/test_pages_bundle.py, .ps-next/PLAN.md
**Commit:** fae4b9c
### 2026-07-30 — Render standalone Påmeldte lag artifacts
**Done:** Added artifact generation for registered-teams/pameldte-lag.html, pameldte-lag.json, and validation-report.json with a responsive static Norwegian HTML page, counts/grouping, empty state, escaped values, and public/private data separation.
**Rationale:** The generator writes reviewable local artifacts first, with public JSON and HTML separated from the richer private validation report so publishing can later preserve privacy boundaries.
**Findings:** Validation-report.json intentionally contains source fingerprint metadata for local review; the public JSON/HTML exclude extra SharePoint fields.
**Files:** tournament_scheduler/pipeline/registered_teams.py, tests/test_registered_teams.py, .ps-next/PLAN.md
**Commit:** 9846b56
### 2026-07-30 — Add registered-team CSV parsing and validation
**Done:** Added a focused registered-team CSV parser/validator with UTF-8 BOM handling, whitespace normalization, duplicate detection, optional configured age-group validation, public payload generation, and private validation metadata.
**Rationale:** Keeping parsing and validation in a reusable Python module avoids Makefile logic and gives the CLI/publish tasks a single application entry point to call.
**Findings:** The repo already has registration workbook tooling, but this standalone page should stay independent and only project club/label/age_group.
**Files:** tournament_scheduler/pipeline/registered_teams.py (new), tests/test_registered_teams.py (new), .ps-next/PLAN.md
**Commit:** ab0fad1
<!-- pi-next appends entries here after each task -->
