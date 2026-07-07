# Plan: Propagate workbook-level planning settings
**Goal:** Workbook-level participation and hosting-day settings are treated as supported inputs and reach Stage 3 planning.
**Created:** 2026-07-07
**Intent:** Operators can set global planning knobs in `input.xlsx` without noisy unknown-field warnings or silently ignored constraints.
**Backlog-ref:** 208

## Tasks
- [x] Wire workbook-level scalar settings into effective config and Stage 3
  - Files: tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage3_planning.py, tests/test_stage1_config.py, tests/test_stage3_planning.py
  - Approach: Treat `deltakelser_per_lag` as the Norwegian alias for global `target_tournament_count`, preserve `target_tournament_count`/`max_hosting_days_per_month` in `load_effective_config`, add them to the Stage 1 supported-key set so they are not warned as unknown, and pass both values into `_make_planner` from Stage 3. Add regression tests for no unknown-field warning, effective-config propagation, and Stage 3 planner handoff.
- [x] Document supported workbook-level settings
  - Files: docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-rules-report.md
  - Approach: Update the workbook docs from “ignored/reserved” to “supported”, explain the alias and Stage 3 effect, and add the monthly hosting-day knob to the rules/guardrails description.

## Notes
- `load_effective_config` currently merges only selected workbook fields and omits global `target_tournament_count` and `max_hosting_days_per_month`.
- `stage1_helpers._parse_config` warns for workbook scalar keys not in its supported-key allowlist, so intentional settings from `Innstillinger` are logged as ignored today.
- `stage3_planning.run` already reads per-age targets, but passes `target_tournament_count=None` and `max_hosting_days_per_month=None` to the planner even though `SeasonPlanner` supports both.
- Project docs require reviewing rules/input docs when scheduling logic changes.

## Acceptance Criteria
- [ ] `load_effective_config` returns `target_tournament_count` when `target_tournament_count` or `deltakelser_per_lag` is set in `Innstillinger`.
- [ ] `load_effective_config` returns `max_hosting_days_per_month` when set in `Innstillinger`.
- [ ] Stage 1 no longer logs supported `deltakelser_per_lag`, `target_tournament_count`, or `max_hosting_days_per_month` rows as ignored unknown fields.
- [ ] Stage 3 passes both global settings into `SeasonPlanner` via `_make_planner`.
- [ ] Relevant tests pass: `run: pytest tests/test_stage1_config.py`

## Log


### 2026-07-07 — Document supported workbook-level settings
**Done:** Updated input-format and rules-report docs to describe `deltakelser_per_lag` / `target_tournament_count` and `max_hosting_days_per_month` as supported workbook-level planning settings.
**Rationale:** Scheduling behavior changed from ignored scalar rows to active Stage 3 inputs, so operator-facing docs and rule descriptions need to match.
**Findings:** Docs previously explicitly described both settings as ignored/reserved; those statements are now removed.
**Files:** docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-rules-report.md
**Commit:** not committed
### 2026-07-07 — Wire workbook-level scalar settings into effective config and Stage 3
**Done:** Workbook-level `deltakelser_per_lag` is normalized to `target_tournament_count`, `target_tournament_count` and `max_hosting_days_per_month` are included in `load_effective_config`, and Stage 3 passes both values into `_make_planner`.
**Rationale:** These fields are intentional operator-facing planning inputs, so they should be canonicalized once, omitted from unknown-field warnings, and handed to the existing `SeasonPlanner` knobs.
**Findings:** `stage3_planning.run` already had support for per-age targets but explicitly passed `None` for the global target and monthly hosting-day cap. Full `pi_next_quality_gate quick` runs the whole pytest suite and failed in this repo; targeted regression checks passed.
**Files:** tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage3_planning.py, tests/test_stage1_config.py, tests/test_stage3_planning.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
