# Plan: Prevent same-arena same-day double-booking
**Goal:** The season planner never assigns two tournaments to the same arena on the same day when that would double-book the ice, and it reports any unavoidable conflicts clearly.
**Created:** 2026-06-16
**Intent:** Avoid host/arena collisions across age groups so overlapping tournaments cannot be scheduled into the same hall at the same time.
**Backlog-ref:** 120

## Tasks
- [ ] Enforce arena/day uniqueness during host assignment
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py, tournament_scheduler/models.py, tournament_scheduler/participant_selection.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/warnings.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/utils/rich_output.py, tournament_scheduler/html/renderers/review.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/pipeline/stage4_helpers.py, tournament_scheduler/pipeline/tournament_updater.py, tests/test_season_planner.py, tests/test_stage3_planning.py, tests/test_stage4_export.py
  - Approach: Track already-assigned `(arena, date)` pairs while building the plan, prefer alternate host clubs/arenas when a collision would occur, spread new age groups away from already-used dates when possible, and record unavoidable collisions on the planner/plan so the rest of the pipeline can inspect them.
- [ ] Surface arena collision warnings in reports and regression tests
  - Files: tournament_scheduler/warnings.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/utils/rich_output.py, tournament_scheduler/html/renderers/review.py, tests/test_season_planner.py, tests/test_stage3_planning.py, tests/test_stage4_export.py
  - Approach: Add a structured warning list or plan field for same-arena same-day collisions, print it in CLI/rich output, include it in the HTML review summary and fairness gate, and add tests covering both the no-collision happy path and an unavoidable-collision fallback.

## Notes
- Current planner already avoids overlapping age groups on the same date when possible, but it does not yet treat arena/day as a hard scheduling constraint.
- RVV clubs generally map one club to one arena, so same-arena collisions usually mean the same hall would be double-booked.
- Keep the reporting Norwegian-language and consistent with existing warning styles.

## Acceptance Criteria
- [ ] `SeasonPlanner.build_plan()` returns no duplicate `(arena, date)` tournament assignments in the normal happy-path roster/tests.
- [ ] Any unavoidable arena/day collision is exposed in planner metadata and printed as a warning in the CLI/reporting path.
- [ ] Targeted season-planner and export tests pass.

## Log
<!-- pi-next appends entries here after each task -->
