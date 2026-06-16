# Plan: Split SeasonPlanner into a thin facade
**Goal:** `tournament_scheduler/season_planner.py` is reduced to orchestration/state helpers while the planning logic lives in focused modules, and the existing test suite still passes.
**Created:** 2026-06-16
**Intent:** Finish the ongoing SOLID/refactor work by removing the remaining helper-heavy implementation from the facade module and making the extraction easier to maintain.
**Backlog-ref:** 104

## Tasks
- [x] Rewrite `season_planner.py` as a thin orchestration facade
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/participant_selection.py, tournament_scheduler/host_assignment.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/game_generation.py, tournament_scheduler/warnings.py, tournament_scheduler/rules_report.py
  - Approach: keep constructor, public build_plan flow, properties, and the small state utilities required by tests/manual adjustment workflows; remove duplicated helper bodies from SeasonPlanner and rely on the extracted modules plus the compatibility aliases at the bottom of the file. Preserve public behavior and avoid circular imports.
- [x] Add regression coverage for the refactored planner surface
  - Files: tests/test_season_planner.py
  - Approach: add a small smoke test that exercises the facade via the extracted helpers (import/build-plan/score utilities) so the refactor is pinned down without changing the user-facing behavior.

## Notes
The helper modules already exist; this plan is about finishing the cleanup so the class reads like an orchestrator instead of a second copy of the algorithms.

## Acceptance Criteria
- [ ] `pytest` passes without changes to existing planner behavior.
- [ ] `season_planner.py` no longer contains the duplicated helper implementations for participant selection, host assignment, fairness scoring, game generation, rules reporting, or warning scans.
- [ ] Show that `SeasonPlanner` exposes the same planner surface used by the CLI, exports, and tests.

## Log


### 2026-06-16 — Add regression coverage for the refactored planner surface
**Done:** Added a smoke test that imports the extracted helper modules first, then verifies the facade still builds reports and delegates through the split modules.
**Rationale:** This pins down the new module boundaries and catches circular-import regressions or missing facade shims without altering planner behavior.
**Findings:** Import order matters for refactors like this; the smoke test now exercises the extracted helper modules before constructing SeasonPlanner, which is the main failure mode we wanted to guard against.
**Files:** tests/test_season_planner.py, .ps-next/PLAN.md, .ps-next/VERIFY.md, .ps-next/HISTORY.md
**Commit:** not committed
### 2026-06-16 — Rewrite `season_planner.py` as a thin orchestration facade
**Done:** SeasonPlanner is now a thin orchestrator: the duplicated planner helper bodies were removed from `tournament_scheduler/season_planner.py`, the remaining shared logic is delegated to the focused modules, and the rules report implementation now lives in `tournament_scheduler/rules_report.py`.
**Rationale:** The refactor finishes the prior extraction work without changing planner behavior, reducing the main module to orchestration/state helpers and keeping the public surface stable for CLI, exports, and tests.
**Findings:** The helper modules were already in place and mostly compatible; the only missing pieces were the remaining facade properties/methods (`game_count_warnings`, `hosting_warnings`, etc.) plus the rules-report implementation and a small import-order regression test. Existing season-planner tests cover the refactor well once those compatibility shims are restored.
**Files:** tournament_scheduler/season_planner.py, tournament_scheduler/rules_report.py, tests/test_season_planner.py, .ps-next/PLAN.md, .ps-next/VERIFY.md, .ps-next/HISTORY.md, .ps-next/BACKLOG.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
