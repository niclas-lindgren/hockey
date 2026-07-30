# Plan: GitHub #31 SharePoint registration import
**Goal:** Add a deterministic SharePoint registration import workflow that validates reviewed exports and safely creates updated input workbooks.
**Created:** 2026-07-30
**Intent:** Club operators need a repeatable path from reviewed SharePoint registrations to the pipeline's controlled `input.xlsx` snapshot without manual copy/paste or leaking private registration data.

## Tasks
- [x] Add registration import domain module
  - Files: tournament_scheduler/registrations.py, tests/test_registrations.py
  - Approach: Search existing workbook-loading patterns, then implement CSV/XLSX parsing, column/status validation, duplicate/ambiguity checks, active-team normalization, dry-run diff generation, workbook `Lag` sheet replacement, provenance audit writing, and focused pytest coverage with temporary workbooks.
- [x] Wire registration commands into the RVV CLI
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tests/test_rvv_cli_portability.py
  - Approach: Add `registrations validate` and `registrations export` subcommands that call the domain module, validate required CLI arguments, preserve exit codes, support `--dry-run`, and print concise Norwegian summaries without exposing contact/comment fields by default.
- [ ] Document the SharePoint export workflow
  - Files: docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-pipeline.md, README.md
  - Approach: Document expected SharePoint CSV/XLSX columns, status handling, dry-run/export commands, audit artifacts, privacy behavior, and link the workflow from operator-facing docs.
- [ ] Run verification and archive the plan
  - Files: tests/test_registrations.py, tests/test_rvv_cli_portability.py, .ps-next/VERIFY.md
  - Approach: Run targeted tests for registrations and CLI portability, run the pi-next quality gate where feasible, verify acceptance criteria, and archive/record the completed GitHub issue plan.

## Notes
Selected GitHub issue: https://github.com/niclas-lindgren/hockey/issues/31 `[P1] Export reviewed SharePoint registrations into input.xlsx`.

The implementation must preserve non-`Lag` workbook sheets and treat SharePoint as the reviewed operational source. Only approved/current registrations should become active team rows; rejected, withdrawn, duplicate, incomplete, or ambiguous records are reported and excluded or blocked according to deterministic rules. Personal contact/comment fields should be parsed only for diagnostics/audit metadata and never copied into the public pipeline workbook by default.

Existing workbook conventions live in `tournament_scheduler/pipeline/input_workbook.py` and Stage 1 expects `Lag` columns such as `club`, `label`, and `age_group`.

## Acceptance Criteria
- [ ] `pytest tests/test_registrations.py tests/test_rvv_cli_portability.py` passes.
- [ ] `scripts/rvv-miniputt registrations validate <csv-or-xlsx> --input input.xlsx` validates required columns, statuses, duplicates, clubs, and age groups without writing output.
- [ ] `scripts/rvv-miniputt registrations export <csv-or-xlsx> --input input.xlsx --output input.updated.xlsx --dry-run` shows additions, removals, changes, unchanged rows, and rejected records without creating the output workbook.
- [ ] Non-dry-run export writes an updated workbook with only the `Lag` sheet replaced and writes a provenance/audit artifact containing source fingerprint and included SharePoint IDs.
- [ ] Personal contact/comment fields from the registration export are not written into the generated workbook.
- [ ] README and RVV docs describe the Power Automate → SharePoint List → reviewed export → `input.xlsx` workflow.

## Log


### 2026-07-30 — Wire registration commands into the RVV CLI
**Done:** Added `rvv-miniputt registrations validate` and `rvv-miniputt registrations export` parser/dispatcher wiring. Commands call the shared registration module, preserve nonzero exits on validation errors, support `--dry-run`, and render concise Norwegian summaries that omit contact/comment details. Added CLI parser and subprocess coverage.
**Rationale:** The CLI remains a thin adapter over the new registration domain module, so future browser/GitHub Actions/operator surfaces can reuse the same deterministic import policy.
**Findings:** The existing `scripts/rvv-miniputt` launcher works for the new command through the Python CLI parser; focused subprocess tests cover validate/export behavior and privacy-safe summaries.
**Files:** tournament_scheduler/cli/args.py (+registrations subcommands), tournament_scheduler/cli/rvv_cli.py (+_cmd_registrations), tests/test_rvv_cli_portability.py (+CLI coverage). Targeted check: pytest tests/test_registrations.py tests/test_rvv_cli_portability.py (16 passed).
**Commit:** not committed
### 2026-07-30 — Add registration import domain module
**Done:** Implemented a deterministic registration import domain module with CSV/XLSX parsing, SharePoint-ID/status validation, active/rejected row separation, duplicate and controlled-value checks, dry-run diffing, Lag-sheet replacement, audit JSON output, and CLI-safe summary formatting. Added focused pytest coverage for CSV/XLSX validation, dry-run diffs, workbook preservation/privacy, duplicates, unknown statuses/values, and missing columns.
**Rationale:** Keeping parsing, validation, diffing, workbook mutation, and audit generation in a transport-independent module lets CLI/GitHub Actions/desktop adapters share one deterministic registration workflow without duplicating policy.
**Findings:** Existing input workbook parsing already exposes controlled clubs, age groups, and Lag rows through load_workbook_config, so the importer can validate registrations against current controlled workbook state and replace only the Lag worksheet.
**Files:** tournament_scheduler/registrations.py (new), tests/test_registrations.py (new). Targeted check: pytest tests/test_registrations.py (7 passed).
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
