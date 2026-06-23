# Plan: Age-group participation targets by season half
**Goal:** input.xlsx can set deltakelser_per_lag per age group, split into før jul / etter jul, and the planner uses those targets consistently.
**Created:** 2026-06-23
**Intent:** Let organizers tune participation goals per age group and season half instead of one global target that fits poorly across the whole year.
**Backlog-ref:** 199

## Tasks
- [x] Parse per-age-group target participation settings from the workbook
  - Files: tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage1_config.py, tests/test_stage1_config.py, docs/rvv-miniputt-input-formats.md, README.md
  - Approach: add optional Aldersgrupper columns for age-group participation targets (total + before/after Christmas), validate them in Norwegian, carry the structured values through Stage 1/load_effective_config, and document the new workbook schema with regression tests.
- [x] Make season planning honor the age-group split targets before and after Christmas
  - Files: tournament_scheduler/participant_selection.py, tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/testing/canonical_input.py, tests/test_season_planner.py
  - Approach: thread the per-age-group season-half targets into the planner, split the season window around the Christmas break, and use the configured counts when choosing date buckets so each age group can get distinct før jul / etter jul tournament targets.

## Notes
The existing global `deltakelser_per_lag` remains as the fallback for older workbooks. Keep the Norwegian workbook terminology primary and preserve backward compatibility for the legacy English key where it already exists.

## Acceptance Criteria
- [ ] Update `input.xlsx` handling to accept participation targets per age group with separate before-Christmas and after-Christmas values.
- [ ] Reject malformed target counts and return the parsed per-age-group target structure in the checkpoint/effective config.
- [ ] Return split-target schedules for the configured age groups, and make the test suite pass for both workbook parsing and planner behavior.

## Log


### 2026-06-23 — Make season planning honor the age-group split targets before and after Christmas
**Done:** Season planning now recognizes split age-group targets and biases date placement across the Christmas break accordingly.
**Rationale:** The planner can now derive separate before/after counts from the expanded workbook config, split the season window, and schedule tournaments in the intended half-season buckets while preserving the existing planning flow for non-split inputs.
**Findings:** Age-group target totals now influence per-age tournament counts; split targets are carried through Stage 3 and the canonical test planner; focused season-planner tests confirm the before/after Christmas split behavior.
**Files:** tournament_scheduler/participant_selection.py, tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/testing/canonical_input.py, tests/test_season_planner.py
**Commit:** not committed
### 2026-06-23 — Parse per-age-group target participation settings from the workbook
**Done:** Added workbook support for per-age-group participation targets and split before/after-Christmas fields.
**Rationale:** The input parser now understands the expanded Aldersgrupper schema and preserves the normalized target structure for downstream use.
**Findings:** Workbook rows can now carry total + before/after Christmas target values; validation rejects inconsistent split totals; the Stage 1 checkpoint/effective config now retain the parsed mapping.
**Files:** README.md, docs/rvv-miniputt-input-formats.md, tests/test_stage1_config.py, tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage1_helpers.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
