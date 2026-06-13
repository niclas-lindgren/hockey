# Plan: Derive tournament capacity from parallel games
**Goal:** SeasonPlanner no longer uses a separate max-teams limit; each age group's tournament capacity comes from its parallel-games setting, and odd participant counts are handled with byes/rest rounds.
**Created:** 2026-06-13
**Intent:** Keep tournament sizing aligned with the actual rink capacity per round so we stop over-constraining season plans with a redundant participant cap.

## Tasks
- [x] Rework participant-capacity selection to derive from parallel-games only
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/cli/season_command.py
  - Approach: replace the explicit max-teams decision path with a capacity computed from parallel games (and the existing round-robin bye support), remove the explicit max-teams wording from rules/report text, and keep odd-sized participant sets valid when they fit the derived capacity.
- [x] Update regression coverage for derived capacity and rest rounds
  - Files: tests/test_season_planner.py
  - Approach: replace the old max-teams-based assertions with tests that prove a 2-parallel-game tournament can accept 5 teams, that a 6-team roster is trimmed to the derived capacity, and that odd-sized tournaments still generate byes/rest rounds correctly.

## Notes
The current code still accepts `maxTeamsPerTournament` in config/plumbing, but this task should stop it from controlling season-plan sizing. Preserve backwards-compatible parsing if possible, but don't let it override the derived capacity.

## Acceptance Criteria
- [ ] run: pytest -q tests/test_season_planner.py -k 'parallel_games_define_tournament_capacity_and_bye_rounds'
- [ ] run: bash -lc '! rg -n "max_teams_per_tournament_for_age_group\\.get\\(|return explicit" tournament_scheduler/season_planner.py tournament_scheduler/cli/season_command.py tournament_scheduler/pipeline/stage3_helpers.py'
- [ ] run: pytest -q tests/test_season_planner.py

## Log


### 2026-06-13 — Update regression coverage for derived capacity and rest rounds
**Done:** Added regression tests for parity-aware tournament sizing, including an odd 5-team U10 roster that produces bye rounds and coverage that the legacy max-teams cap no longer controls selection.
**Rationale:** The updated tests lock down the new derived-capacity behavior and the bye/rest round handling required by the backlog item.
**Findings:** A balanced even roster now stays even-sized, while odd rosters can expand by one participant and still generate byes. The old max-teams-based expectations were updated to match the new capacity rule.
**Files:** tests/test_season_planner.py
**Commit:** not committed
### 2026-06-13 — Rework participant-capacity selection to derive from parallel-games only
**Done:** Derived tournament sizing from parallel games instead of the legacy max-teams config, and updated the season command to stop passing that legacy cap into the planner.
**Rationale:** Tournament capacity now comes from the actual rink concurrency per round, with the planner allowing an extra bye/rest slot only when the roster size is odd.
**Findings:** The old maxTeamsPerTournament value was only still present as legacy plumbing. The planner now uses parallel-games-based capacity for selection and reporting; odd rosters can still be scheduled with a bye round.
**Files:** tournament_scheduler/season_planner.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/pipeline/stage3_helpers.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
