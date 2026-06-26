# Plan: Sync RVV Miniputt planning docs
**Goal:** The RVV Miniputt rules report and input-format guide both describe the current scheduler behavior and workbook schema.
**Created:** 2026-06-26
**Intent:** Keep the operator-facing docs aligned with the season-planning logic so planners can rely on the documented constraints and workbook fields.
**Backlog-ref:** 3

## Tasks
- [x] Refresh the rules report to match current planner behavior
  - Files: docs/rvv-miniputt-rules-report.md, tournament_scheduler/rules_report.py
  - Approach: Rewrite the policy / implementation / warning tables so they include age-group-aware hosting, per-age participation targets, pre/post-Christmas split planning, weekend-balance / overlap handling, and the repair / backtracking pass. Keep the report grounded in code, not aspirational wording.
- [x] Update the workbook input-format guide to document the current sheets and config keys
  - Files: docs/rvv-miniputt-input-formats.md
  - Approach: Expand the workbook section to cover the current sheet set and the meaningful `Innstillinger` rows, including split targets, date preferences, and the other scalar knobs now accepted by Stage 1 / the planner. Clarify which values are required, optional, or ignored by Stage 1.

## Notes
The current docs still describe an older version of the planner. Code inspection shows split before/after-Christmas targets, age-group-aware hosting, weekend-balance guardrails, and a repair/refinement pass in the planning pipeline.

## Acceptance Criteria
- [ ] The rules report mentions age-group-aware hosting, split targets, weekend-balance / repair behavior, and the current fairness / warning categories.
- [ ] The input-format guide lists the current workbook sheets and the real `Innstillinger` / age-group fields supported by the pipeline.
- [ ] Both docs read coherently with the current codebase and do not claim unsupported JSON-root input.

## Log


### 2026-06-26 — Update the workbook input-format guide to document the current sheets and config keys
**Done:** Expanded docs/rvv-miniputt-input-formats.md to describe the current workbook sheets, the split age-group targets, per-team target overrides, date preferences, and which `Innstillinger` rows are required, optional, or currently ignored by Stage 1.
**Rationale:** The input-format guide had drifted behind the workbook schema and no longer reflected the actual operator-facing fields or the current split-target behavior.
**Findings:** The workbook now treats `Aldersgrupper` as the main place for parallel-games, round-length, and before/after-Christmas targets; `Lag` supports per-team target overrides; `Datopreferanser` is optional; and extra scalar rows in `Innstillinger` are not yet wired into the standard Stage 1 path.
**Files:** docs/rvv-miniputt-input-formats.md
**Commit:** not committed
### 2026-06-26 — Refresh the rules report to match current planner behavior
**Done:** Updated docs/rvv-miniputt-rules-report.md to reflect the current planner behavior, including age-group-aware hosting, split before/after-Christmas targets, weekend/holiday hosting balance, the global optimization pass, and the repair/backtracking pass.
**Rationale:** The report had drifted from the code and omitted planner behaviors that now materially affect how seasons are planned and reviewed.
**Findings:** The planner now balances hosting per age group, supports split participation targets around Christmas, tracks weekend/holiday hosting streaks, and performs a hill-climbing repair pass after the greedy date placement.
**Files:** docs/rvv-miniputt-rules-report.md, tournament_scheduler/rules_report.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
