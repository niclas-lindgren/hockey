# Plan: Rename/reframe target_tournament_count as soft season-load/participation hint
**Goal:** `target_tournament_count` is understood as per-team participation target (not total tournaments), accepts a Norwegian alias `deltakelser_per_lag`, and all docs/validation/reports use clear language.
**Created:** 2026-06-15
**Intent:** The field name `target_tournament_count` confused organizers into thinking it meant "total number of tournaments to schedule" when it actually means "desired tournament participations per team." We keep backward compatibility but introduce a clearer Norwegian alias and soft semantics.
**Backlog-ref:** 98

## Tasks
- [x] Accept Norwegian alias `deltakelser_per_lag` in Stage 1 validation and parsing
  - Files: tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/input_workbook.py
  - Approach: In `validate_config`, accept both `target_tournament_count` and `deltakelser_per_lag` as valid field names in the raw config dict, validating either one. In `_parse_config`, accept both and store under the internal key `target_tournament_count`. In `stage1_config.py` `_build_config`, read both and prefer `deltakelser_per_lag` if present. Update the `Innstillinger` row docs docstring.

- [x] Rename the field in input.xlsx and update all documentation
  - Files: input.xlsx, docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-pipeline.md, README.md, .agents/skills/rvv/SKILL.md
  - Approach: Change the row key in `input.xlsx` from `target_tournament_count` to `deltakelser_per_lag`. Update each doc file to describe the field as "soft per-team participation target" in Norwegian, mention both the Norwegian workbook field name and the internal English key for backward compatibility.

- [x] Update planner rules report and docstrings to clarify soft participation semantics
  - Files: tournament_scheduler/season_planner.py
  - Approach: Update the `_rules_report` entry (around line 1144) and the `_target_tournaments_for_age_group` docstring (around line 1274) to say "myk målsetning om turneringsdeltakelser per lag" instead of "mål: cirka X turneringsdeltakelser per lag", and document the soft semantics: never create low-value tournaments just to hit the target.

- [x] Add an age-group feasibility warning when target cannot reasonably be met
  - Files: tournament_scheduler/season_planner.py
  - Approach: In `_scan_per_team_share_warnings` or a new `_scan_feasibility_warnings`, add a warning when an age group's computed tournament count cannot reasonably be met given the number of free dates available. E.g. if target_tournament_count * teams > free dates * capacity, emit a warning.

- [x] Update tests to cover the new `deltakelser_per_lag` field name and backward compatibility
  - Files: tests/test_stage1_config.py, tests/test_stage4_export.py, tests/test_season_planner.py
  - Approach: Add test cases that write `deltakelser_per_lag` to the Innstillinger sheet and verify the pipeline accepts it. Keep existing tests using `target_tournament_count` to ensure backward compatibility.

## Notes
- Internal config key stays `target_tournament_count` throughout all Python code — only the workbook UI field name changes.
- Stage 1 already passes `target_tournament_count` through to the planner checkpoint; no Stage 3/4 changes needed.
- The `input.xlsx` already exists at repo root; updating it via openpyxl is straightforward.
- The rules report in `season_planner.py` hardcodes `DEFAULT_TARGET_TOURNAMENT_COUNT` in its string — update to reference the actual configured value when available.

## Acceptance Criteria
- [ ] Running `rvv-miniputt run` with `deltakelser_per_lag=6` in `Innstillinger` produces the same plan as `target_tournament_count=6`.
- [ ] Running with `target_tournament_count` (old name) still works for backward compatibility.
- [ ] Running with `deltakelser_per_lag` and `target_tournament_count` both set uses `deltakelser_per_lag`.
- [ ] Running with an invalid value for either field produces a Norwegian validation error.
- [ ] All docs list the Norwegian field name `deltakelser_per_lag` as the recommended workbook key.
- [ ] The rules report and docstrings describe the value as a soft per-team participation target, not as total tournaments.
- [ ] An age group that cannot reasonably meet the target produces a warning (not a hard failure).

## Log





### 2026-06-15 — Update tests to cover the new `deltakelser_per_lag` field name and backward compatibility
**Done:** ✅ Update tests to cover the new `deltakelser_per_lag` field name and backward compatibility
**Rationale:** Added 3 tests in test_stage1_config.py: deltakelser_per_lag_accepted, deltakelser_per_lag_takes_priority (both old and new), deltakelser_per_lag_invalid_rejected. Added run_accepts_deltakelser_per_lag_in_workbook for the full workbook → stage 1 pipeline path. Updated _write_input_workbook helper to write deltakelser_per_lag. Added feasibility warning tests in test_season_planner.py.
**Findings:** _make_valid_raw() doesn't include target_tournament_count by default, so tests must use .pop() with default. _write_input_workbook needed updating to support the new field name.
**Files:** tests/test_stage1_config.py (+25/-2), tests/test_season_planner.py (+30/-1)
**Commit:** not committed
### 2026-06-15 — Add an age-group feasibility warning when target cannot reasonably be met
**Done:** ✅ Add an age-group feasibility warning when target cannot reasonably be met
**Rationale:** Added `_feasibility_warnings` list attribute, `_scan_feasibility_warnings` method called from `build_plan`, and `feasibility_warnings` property. When an age group has too few teams (below MIN_TEAMS_PER_TOURNAMENT) or the target tournament count exceeds available free dates, a Norwegian warning is emitted.
**Findings:** Existing `month_load_warnings` was missing its `@property` decorator (bug fix). The feasibility warnings are collected separately from other warnings and exposed as a list of Norwegian strings.
**Files:** tournament_scheduler/season_planner.py (+53/-1)
**Commit:** not committed
### 2026-06-15 — Update planner rules report and docstrings to clarify soft participation semantics
**Done:** ✅ Update planner rules report and docstrings to clarify soft participation semantics
**Rationale:** Updated the rules report rule text to use "Mykt mål" language and reference the actual configured value (not just the default), with explanation that planner prefers fewer better tournaments. Updated docstrings for _target_tournaments_for_age_group and _default_target_count to describe the soft target semantics.
**Findings:** The rules report used to hardcode DEFAULT_TARGET_TOURNAMENT_COUNT in its string even when the user had configured a different value. Now it uses self.target_tournament_count or falls back to the default.
**Files:** tournament_scheduler/season_planner.py (+15/-5)
**Commit:** not committed
### 2026-06-15 — Rename the field in input.xlsx and update all documentation
**Done:** ✅ Rename the field in input.xlsx and update all documentation
**Rationale:** Updated input.xlsx to use `deltakelser_per_lag` as the field name. Updated docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-pipeline.md, and README.md to describe the Norwegian field name and mention backward compatibility.
**Findings:** SKILL.md doesn't mention the field, so no change needed there. Docs now consistently recommend `deltakelser_per_lag` and mention `target_tournament_count` works for backward compat.
**Files:** input.xlsx, docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-pipeline.md, README.md
**Commit:** not committed
### 2026-06-15 — Accept Norwegian alias `deltakelser_per_lag` in Stage 1 validation and parsing
**Done:** ✅ Accept Norwegian alias `deltakelser_per_lag` in Stage 1 validation and parsing
**Rationale:** Added `deltakelser_per_lag` as an accepted field name alongside `target_tournament_count` in validate_config, _parse_config, stage1_config._build_config, and input_workbook docstring. If both are present, `deltakelser_per_lag` wins. Internal key remains `target_tournament_count`.
**Findings:** The workbook Innstillinger sheet reads fields via key-value pairs; the key name is what organizers type. No changes needed in downstream stages since the internal config key stays unchanged.
**Files:** tournament_scheduler/pipeline/stage1_helpers.py (+12/-5), tournament_scheduler/pipeline/stage1_config.py (+3/-1), tournament_scheduler/pipeline/input_workbook.py (+2/-1)
**Commit:** not committed
