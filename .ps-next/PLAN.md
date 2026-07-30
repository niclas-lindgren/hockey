# Plan: GitHub issue #47 — Påmeldte lag SharePoint CSV page
**Goal:** Verify and finish the standalone generated Påmeldte lag HTML workflow from SharePoint CSV, including operator documentation and guarded publish behavior.
**Created:** 2026-07-30
**Intent:** Issue #47 is open and asks for a privacy-safe, independently publishable registered-team overview; the codebase already contains most of the implementation, so complete any missing documentation/coverage and verify the workflow end-to-end.

## Tasks
- [x] Document the standalone registered-team operator workflow
  - Files: docs/rvv-miniputt-pipeline.md, README.md, tests/test_registered_teams_publish.py
  - Approach: Add the `registered-teams` Make/CLI commands and public URL/path guidance to the operator pipeline docs, keeping README wording consistent; add or adjust lightweight regression coverage if the docs/help expectations are not locked down.
- [ ] Verify issue #47 behavior and fix any gaps found
  - Files: tournament_scheduler/pipeline/registered_teams.py, tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/pipeline/pages_bundle.py, Makefile, tests/test_registered_teams.py, tests/test_registered_teams_publish.py, tests/test_pages_bundle.py
  - Approach: Run targeted pytest coverage plus CLI/Make smoke checks for header-only CSV generation and non-publish preview; inspect artifacts for privacy-safe public JSON/HTML and private validation metadata; fix only regressions needed to satisfy issue #47.

## Notes
Selected from GitHub issue #47: https://github.com/niclas-lindgren/hockey/issues/47. Existing implementation includes `tournament_scheduler/pipeline/registered_teams.py`, CLI/Make entrypoints, Pages sanitizer allowlisting, README coverage, and tests. Do not run `/rvv-miniputt ...` through Bash; use `scripts/rvv-miniputt` or Python module entrypoints for CLI smoke checks. Keep publishing guarded; do not push to GitHub Pages during verification.

## Acceptance Criteria
- [ ] `make registered-teams CSV=<sharepoint-export.csv>` should run and create a local reviewable page without publishing.
- [ ] `make registered-teams-publish CSV=<sharepoint-export.csv> CONFIRM_PUBLIC=1` should run through the guarded Pages publishing path.
- [ ] The workflow should run independently of the season-plan pipeline and activity-calendar regeneration.
- [ ] The `club,label,age_group` SharePoint export should return actionable validation errors.
- [ ] The page should show teams grouped and counted clearly by age group and club.
- [ ] A header-only CSV should create a useful empty-state page.
- [ ] Public artifacts should remove personal or internal SharePoint fields.
- [ ] Registered-team staging should contain existing unrelated GitHub Pages files.
- [ ] Tests should cover validation, rendering, privacy, deterministic output, and guarded publication.
- [ ] `make help` and operator documentation should present this as a routine standalone content update.

## Log

### 2026-07-30 — Document the standalone registered-team operator workflow
**Done:** Added standalone Påmeldte lag Make/CLI commands and public WordPress URL guidance to the operator pipeline docs, and kept README/operator-doc coverage locked with a regression test.
**Rationale:** Issue #47 requires this workflow to be discoverable as a routine standalone content update with a stable public path; the implementation already existed but the pipeline docs lacked the Make target rows and URL.
**Findings:** `make help` already listed the registered-team targets; README already described the workflow but did not name the final public URL.
**Files:** README.md (+1/-1), docs/rvv-miniputt-pipeline.md (+15), tests/test_registered_teams_publish.py (+10)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
