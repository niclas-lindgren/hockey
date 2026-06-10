# Plan: Rules & decisions report
**Goal:** A separate section — CLI output and Excel sheet — that lists every constraint, hard rule, and automatic decision made by the scheduler, with a short Norwegian-language explanation of the rationale behind each one.
**Created:** 2026-06-10
**Intent:** Makes the scheduler output transparent and auditable for tournament organizers. Answers questions like "Hvorfor kan ikke to lag fra samme klubb møtes?", "Hvorfor blir noen lag invitert til flere turneringer?", "Hvordan velges arena?".
**Backlog-ref:** 25

## Tasks
- [x] Add `rules_report()` method to SeasonPlanner
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add a `rules_report() -> List[Dict[str, str]]` method that returns a list of rule entries, each with `regel` (constraint/rule name), `forklaring` (Norwegian explanation), and `kategori` (e.g. "Hard krav", "Automatisk avgjørelse", "Anbefaling"). Cover: (1) max_club_teams_per_tournament hard constraint, (2) division_skill_band adjacency, (3) max_hosting_deviation proportional hosting, (4) max_game_count_spread even game count, (5) parallelGames federation defaults, (6) maxTeamsPerTournament age-group configs, (7) _pick_least_recently_grouped heuristic, (8) date-spreading and month-load balancing, (9) arena assignment by hosting rotation, (10) age-group overlap collision avoidance. Read actual parameter values from the instance so the report reflects the active configuration.

- [x] Print rules report in CLI output
  - Files: tournament_scheduler/cli/season_command.py
  - Approach: After `_print_plan` and warnings, call `planner.rules_report()` and output a Rich-panel-based section titled "Regler og avgjørelser" using `TournamentOutput` or direct Rich table rendering. Each rule gets a one-line summary with its explanation.

- [x] Add "Regler og avgjørelser" sheet to Excel export
  - Files: tournament_scheduler/excel/plan_exporter.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: Pass the rules report through the pipeline (or regenerate from plan metadata). In `SeasonPlanExporter.export`, add a new worksheet "Regler og avgjørelser" with columns Regel, Forklaring, Kategori. Write the rules from a `rules_report` parameter (list of dicts).

- [x] Write tests
  - Files: tests/test_season_planner.py
  - Approach: Instantiate a SeasonPlanner with default config, call `rules_report()`, assert it returns a non-empty list and contains expected rule keys like "regel", "forklaring", "kategori". Verify at least one hard constraint and one automatic decision are present.

## Notes
- The report should be self-contained — no user action required to see it; it always prints after season generation.
- Keep the Norwegian text clear and accessible to non-technical tournament organizers.
- The Excel "Regler og avgjørelser" sheet follows the same styling conventions as the existing overview sheet (header styling, autosized columns).
- No PDF support needed — Excel and CLI output suffice.

## Acceptance Criteria
- [ ] `SeasonPlanner.rules_report()` returns a list of dicts with keys regel, forklaring, kategori. Runs without error.
- [ ] CLI output shows "Regler og avgjørelser" section with at least 8 rule entries after season generation.
- [ ] Excel export includes a "Regler og avgjørelser" sheet with Regel, Forklaring, Kategori headers.
- [ ] Tests pass: at least one test verifies rules_report() returns non-empty structured output.
- [ ] Existing tests continue to pass (no regressions).

## Log

### 2026-06-10 — Add rules_report() method to SeasonPlanner
**Done:** Added `rules_report() -> List[Dict[str, str]]` returning 11 structured entries: 3 hard constraints (max_club_teams, parallelGames, skill_band) and 8 automatic decisions (least-recently-grouped, date-spreading, proportional hosting, even game counts, age-group overlap, round-robin, safety filter, tournament count bounds). Each entry has `regel`, `forklaring` (Norwegian), `kategori`.
**Rationale:** Self-contained method reads active configuration, no side effects.
**Findings:** All 34 existing tests pass.
**Files:** tournament_scheduler/season_planner.py (+167)
**Commit:** not committed

<!-- pi-next appends entries here after each task -->
