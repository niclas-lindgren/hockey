# Plan: Excel workbook input prototype
**Goal:** Evaluate JSON/CSV/Excel input options and add a small, tested Excel workbook input path that can supplement `input.json` without replacing its canonical JSON shape.
**Created:** 2026-06-15
**Intent:** Make RVV Miniputt configuration easier for organizers to edit while preserving validation, nested source/team settings, and pipeline compatibility.
**Backlog-ref:** 96

## Tasks
- [x] Document the input-format recommendation
  - Files: docs/rvv-miniputt-input-formats.md, README.md
  - Approach: Compare JSON, CSV, and Excel against organizer editability, validation, nested team/source settings, round-trip safety, and pipeline compatibility; recommend Excel as an import/export supplement backed by the canonical JSON schema, not an immediate replacement.
- [x] Add an Excel workbook reader for pipeline input
  - Files: tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage1_config.py, tests/test_stage1_config.py
  - Approach: Implement an openpyxl-based `.xlsx` reader that maps simple sheets (`Innstillinger`, `Aldersgrupper`, `Lag`, `Kilder`) into the existing raw config dict before existing validation; keep `input.json` behavior unchanged and cover success/error cases with pytest.
- [x] Surface workbook input support in CLI/docs
  - Files: tournament_scheduler/cli/rvv_cli.py, README.md, docs/rvv-miniputt-pipeline.md, tests/test_stage1_config.py
  - Approach: Update help/docs to say `--input` accepts `.json` or `.xlsx`, add a round-trip-ish test that `run()` accepts a workbook path and writes the normal Stage 1 checkpoint, and ensure documentation names JSON as the canonical interchange format.

## Notes
- `openspec/AGENTS.md` was referenced by project instructions but is not present in this checkout, so this plan follows the existing `.ps-next` workflow and current code patterns.
- Stage 1 currently hardcodes JSON loading through `_load_json`; downstream consumers expect the existing raw config dict shape, so the lowest-risk prototype is a workbook-to-dict adapter before validation.
- `openpyxl` is already a project dependency and is used by existing Excel exporters/tests.

## Acceptance Criteria
- [ ] `docs/rvv-miniputt-input-formats.md` contains a clear Excel vs CSV vs JSON recommendation.
- [ ] `pytest tests/test_stage1_config.py` passes.
- [ ] `python3 -m tournament_scheduler.pipeline.stage1_config --input input.json --work-dir /tmp/rvv-stage1-check` passes.
- [ ] Stage 1 accepts a `.xlsx` workbook with settings, age groups, teams, and sources and produces the same validated config shape as JSON.

## Log



### 2026-06-15 — Surface workbook input support in CLI/docs
**Done:** Updated CLI help and pipeline docs to advertise `.json`/`.xlsx` input support, documented workbook sheets, and strengthened the workbook Stage 1 test to assert the normal checkpoint shape.
**Rationale:** Users can now discover workbook support from the command help and docs while still seeing JSON described as the canonical interchange format.
**Findings:** This environment lacks a `python` executable, so the Stage 1 module acceptance command was run successfully with `python3`.
**Files:** tournament_scheduler/cli/rvv_cli.py, README.md, docs/rvv-miniputt-pipeline.md, tests/test_stage1_config.py, .ps-next/PLAN.md
**Commit:** not committed
### 2026-06-15 — Add an Excel workbook reader for pipeline input
**Done:** Added an openpyxl workbook adapter for `Innstillinger`, `Aldersgrupper`, `Lag`, and `Kilder` sheets, wired Stage 1 loading to accept `.xlsx`/`.xlsm`, and covered workbook success/missing-sheet behavior.
**Rationale:** Mapping Excel into the existing raw config dict reuses current validation and keeps the JSON-shaped schema canonical for downstream stages.
**Findings:** `load_effective_config()` also benefits from the adapter because it uses the same loader when the Stage 1 input path is a workbook.
**Files:** tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage1_config.py, tests/test_stage1_config.py, .ps-next/PLAN.md
**Commit:** not committed
### 2026-06-15 — Document the input-format recommendation
**Done:** Added a dedicated input-format comparison document and linked it from the README inputs section.
**Rationale:** Excel is recommended as an organizer-friendly supplement while JSON remains the canonical schema for compatibility and reproducible pipeline runs.
**Findings:** `openspec/AGENTS.md` is referenced by project instructions but is not present in this checkout; openpyxl is already used elsewhere in the project.
**Files:** README.md, docs/rvv-miniputt-input-formats.md, .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
