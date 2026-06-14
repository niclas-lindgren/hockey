# Plan: Make input.json the single age-group source
**Goal:** Season export and filter UIs use only the age groups declared in `input.json`, without legacy derived-age-group plumbing or `maxTeamsPerTournament` concepts leaking back in.
**Created:** 2026-06-14
**Intent:** Keep the pipeline’s visible age-group set aligned with the canonical config file so reports, filters, and planning all read from the same source of truth.
**Backlog-ref:** 80

## Tasks
- [x] Remove derived age-group fallback from the effective config path
  - Files: tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: stop emitting `derived_age_groups` from Stage 1, preserve only explicit `age_groups` from `input.json` in the merged config, and have Stage 4 use that explicit list for HTML/report filtering with a safe fallback only when the input truly omits age groups.
- [x] Add regression coverage for input-driven age-group filters
  - Files: tests/test_stage1_config.py, tests/test_stage4_export.py
  - Approach: add tests proving Stage 1 no longer injects derived age groups when the input already supplies them, and that the HTML export’s age-group filters match the explicit `input.json` list instead of any plan-derived list.

## Notes
- `input.json` is already the canonical pipeline input; the remaining work here is to remove the last legacy age-group fallback path and lock it down with tests.
- Keep the change narrow: no planner logic changes are expected unless tests reveal a hidden dependency.

## Acceptance Criteria
- [ ] run: pytest -q tests/test_stage1_config.py tests/test_stage4_export.py
- [ ] run: bash -lc '! rg -n "derived_age_groups|maxTeamsPerTournament|max_teams_per_tournament" tournament_scheduler tests'
- [ ] run: pytest -q tests/test_stage1_config.py tests/test_stage4_export.py -k "age_group"

## Log


### 2026-06-14 — Add regression coverage for input-driven age-group filters
**Done:** Added tests covering the new explicit age-group signal from `input.json`, plus a fallback case when the input omits the field.
**Rationale:** These regressions lock in the intended source-of-truth behavior and prevent the old checkpoint-derived age-group fallback from coming back unnoticed.
**Findings:** Stage 1 now exposes whether age groups came from the input file, and the HTML export tests verify both explicit-filter and fallback scenarios.
**Files:** tests/test_stage1_config.py; tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-14 — Remove derived age-group fallback from the effective config path
**Done:** Removed the Stage 1 derived-age-group plumbing and made Stage 4 explicitly prefer `input.json` age groups, with a fallback only when the input truly omits them.
**Rationale:** This keeps the visible age-group set anchored in the canonical input file instead of a checkpoint-derived shadow value, while preserving legacy fallback behavior when no age-group list is supplied.
**Findings:** `derived_age_groups` was only still flowing through the Stage 1 merge/export path, not the planner itself. The HTML export now gets an explicit `age_groups_from_input` signal so it can distinguish configured filters from plan-derived fallback.
**Files:** tournament_scheduler/pipeline/stage1_helpers.py; tournament_scheduler/pipeline/stage1_config.py; tournament_scheduler/pipeline/stage4_export.py; tests/test_stage1_config.py; tests/test_stage4_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
