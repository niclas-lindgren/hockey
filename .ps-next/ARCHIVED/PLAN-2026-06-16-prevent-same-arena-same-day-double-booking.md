# Plan: Prevent same-arena same-day double-booking
**Goal:** The season planner never assigns two tournaments to the same arena on the same day when that would double-book the ice, and it reports any unavoidable conflicts clearly.
**Created:** 2026-06-16
**Intent:** Avoid host/arena collisions across age groups so overlapping tournaments cannot be scheduled into the same hall at the same time.
**Backlog-ref:** 120

## Tasks
- [x] Enforce arena/day uniqueness during host assignment
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py, tournament_scheduler/models.py, tournament_scheduler/participant_selection.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/warnings.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/utils/rich_output.py, tournament_scheduler/html/renderers/review.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/pipeline/stage4_helpers.py, tournament_scheduler/pipeline/tournament_updater.py, tests/test_season_planner.py, tests/test_stage3_planning.py, tests/test_stage4_export.py
  - Approach: Track already-assigned `(arena, date)` pairs while building the plan, prefer alternate host clubs/arenas when a collision would occur, spread new age groups away from already-used dates when possible, and record unavoidable collisions on the planner/plan so the rest of the pipeline can inspect them.
- [x] Surface arena collision warnings in reports and regression tests
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


### 2026-06-16 — Surface arena collision warnings in reports and regression tests
**Done:** Added serialized arena/day collision metadata plus console and HTML reporting, and covered both the happy path and an unavoidable single-arena fallback in regression tests.
**Rationale:** Operators need the collision state visible in exports, CLI output, and review summaries, not just enforced internally.
**Findings:** The fairness gate only failed once the new collision metric was wired into the shared fairness builder; stage3/stage4 round-trips also needed the new plan field.
**Files:** tournament_scheduler/warnings.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/utils/rich_output.py, tournament_scheduler/html/renderers/review.py, tests/test_season_planner.py, tests/test_stage3_planning.py, tests/test_stage4_export.py
**Commit:** 44987f4
### 2026-06-16 — Enforce arena/day uniqueness during host assignment
**Done:** Host assignment now avoids reusing the same arena on the same date when another eligible club is available, and date spreading now prefers unused dates so same-day double-booking is avoided in the normal plan.
**Rationale:** A hard arena/day constraint needed both date-selection pressure and host-assignment fallback logic to keep the planner from double-booking ice when alternatives exist.
**Findings:** Same-day collisions were being introduced by cross-age-group host selection even with plenty of free weekends; pushing new age groups off already-used dates fixed the fairness regression while preserving unavoidable-collision reporting.
**Files:** tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py, tournament_scheduler/models.py, tournament_scheduler/participant_selection.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/pipeline/stage4_helpers.py, tournament_scheduler/pipeline/tournament_updater.py
**Commit:** 44987f4
<!-- pi-next appends entries here after each task -->
