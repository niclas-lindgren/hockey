# Plan: GitHub issue 27 arena overlap validation
**Goal:** Verify GitHub issue #27's arena-overlap protections are implemented, fill any gaps found, and close the issue when checks pass.
**Created:** 2026-07-29
**Intent:** The public season plan must never contain overlapping tournaments in the same arena, including long matchdays and overnight intervals.

## Tasks
- [x] Audit arena conflict implementation against issue #27
  - Files: tournament_scheduler/arena_conflicts.py, tournament_scheduler/host_assignment.py, tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/operator_action.py, tests/test_arena_conflicts.py, tests/test_season_planner.py, tests/test_stage4_export.py, tests/test_operator_action.py
  - Approach: Compare existing code and tests with each GitHub issue #27 acceptance criterion; add the smallest missing regression coverage if any criterion is not mechanically protected.
- [ ] Verify issue #27 and close it on GitHub
  - Files: .ps-next/PLAN.md
  - Approach: Run focused pytest coverage for arena conflict detection, planner overflow behavior, export blocking, and publish blocking; if all pass and the audit shows the issue is resolved, close GitHub issue #27 with a concise summary.

## Notes
Selected from GitHub via `/skill:pi-next auto github`: https://github.com/niclas-lindgren/hockey/issues/27 (`[P0] Prevent overlapping tournaments and block invalid publication`). Prior history shows related arena collision work landed, so first step is an acceptance audit before changing behavior.

## Acceptance Criteria
- [ ] `pytest -q tests/test_arena_conflicts.py tests/test_season_planner.py::TestSeasonPlanner::test_same_arena_third_tournament_after_latest_start_is_hard_collision tests/test_stage4_export.py tests/test_operator_action.py::TestPublishPagesExecutor::test_refuses_publish_when_planning_checkpoint_has_arena_conflict` passes.
- [ ] Issue #27 is closed on GitHub with evidence that interval conflicts, export blocking, and publish blocking are covered.

## Log

### 2026-07-29 — Audit arena conflict implementation against issue #27
**Done:** Audited issue #27 acceptance criteria against the current arena interval conflict detector, planner sequencing/reservation flow, Stage 4 export block, and Pages publish block. No behavioral gaps were found.
**Rationale:** The existing implementation already treats tournaments as full datetime intervals, reserves committed tournament occupancy during slot search, records sequence/slot failures as hard arena_day_collisions, derives final interval collisions before export, and blocks publishing when collisions remain.
**Findings:** Focused regression coverage passed: arena interval adjacency/overnight/details, third same-arena tournament overflow, Stage 4 overlap blocking, and publish refusal on arena_day_collisions.
**Files:** No source changes; .ps-next/PLAN.md updated for task log.
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
