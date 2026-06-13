# Plan: Fairness acceptance gate for season plans
**Goal:** Build and surface a configurable fairness gate that evaluates real roster-based season-plan metrics and flags weak plans clearly.
**Created:** 2026-06-13
**Intent:** Give organizers a transparent pass/warn/fail view of the season plan's fairness before export.
**Backlog-ref:** 69

## Tasks
- [x] Add a structured fairness gate to the season planner and checkpoint format
  - Files: tournament_scheduler/models.py, tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage4_helpers.py
  - Approach: Compute roster-based gate metrics after build_plan (games per team, hosting burden, travel burden, opponent diversity, month balance, and same-weekend club load), compare them with configurable thresholds, and serialize the gate alongside the existing plan scores.

- [x] Expose fairness gate results in Excel/HTML exports and add regression coverage
  - Files: tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/excel/plan_exporter.py, tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/scores.html, tournament_scheduler/html/templates/metrics.html, tests/test_season_planner.py, tests/test_stage4_export.py
  - Approach: Render the gate status/metrics in the season overview workbook and HTML report, keep the existing scores visible, and add tests that verify the new gate rows/cards plus the warning/fail behavior for skewed plans.

## Notes
- Reuse the existing planner metrics and warnings where possible rather than inventing duplicate calculations.
- Keep serialization backward-compatible so older checkpoints still load with default gate values.
- The gate should be understandable in CLI/export output even when the plan only warns instead of hard-failing.

## Acceptance Criteria
- [ ] Generated plans include a serialized fairness gate with pass/warn/fail statuses for the requested metrics.
- [ ] Excel and HTML exports show the fairness gate results and existing score summaries.
- [ ] Regression tests cover both a healthy plan and at least one skewed plan that triggers warnings or failure.

## Log


### 2026-06-13 — Expose fairness gate results in Excel/HTML exports and add regression coverage
**Done:** Rendered the fairness gate in the Excel season overview workbook and the interactive HTML report, with regression tests covering both healthy and skewed plans.
**Rationale:** The exports now surface the gate summary, per-metric status, score, and detail alongside the existing season-plan scores so organizers can inspect fairness at a glance.
**Findings:** The HTML view uses the existing template fragments plus a fairness panel; the metrics template lives in the working tree but is ignored by git, so the export path still reads it correctly during tests.
**Files:** tournament_scheduler/excel/plan_exporter.py; tournament_scheduler/html/html_exporter.py; tournament_scheduler/html/templates/scores.html; tournament_scheduler/html/templates/styles.css; tournament_scheduler/html/templates/metrics.html; tests/test_season_planner.py; tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-13 — Add a structured fairness gate to the season planner and checkpoint format
**Done:** Added a structured fairness gate to the season plan and checkpoint payloads.
**Rationale:** The planner now computes roster-based gate metrics from the built plan (games, hosting burden, travel, diversity, month balance, same-weekend club load) with configurable thresholds and serializes them for later export.
**Findings:** Fairness thresholds can be overridden from input.json via fairness_thresholds; the gate depends on final plan scores, so it is computed after game counts are finalized.
**Files:** tournament_scheduler/models.py; tournament_scheduler/season_planner.py; tournament_scheduler/pipeline/stage1_helpers.py; tournament_scheduler/pipeline/stage3_helpers.py; tournament_scheduler/pipeline/stage3_planning.py; tournament_scheduler/pipeline/stage4_helpers.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
