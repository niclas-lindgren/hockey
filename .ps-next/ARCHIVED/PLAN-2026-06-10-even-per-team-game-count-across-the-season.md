# Plan: Even per-team game count across the season
**Goal:** Every team finishes the season with approximately the same number of games, no team is 'done' many weeks before others, and the output flags when the spread exceeds a configurable threshold.
**Created:** 2026-06-10
**Intent:** Fairness and retention — teams that play significantly fewer games or finish weeks before their peers have worse player development and club satisfaction. This validator is the final piece of basic fairness alongside the existing even-time-distribution (month balance) and even-invite-count logic.
**Backlog-ref:** 13

## Tasks
- [x] Add per-team game count tracking and spread validation to models/planner
  - Files: tournament_scheduler/models.py, tournament_scheduler/season_planner.py
  - Approach: Add `team_game_counts: Dict[str, int]` and `game_count_spread: int` to `SeasonPlan`. Compute in `build_plan()` by walking all `Tournament.games` across the season. Add `max_game_count_spread: int` parameter to `SeasonPlanner.__init__` (default from federation defaults, e.g. 2). Store spread-exceeded warnings on planner state similarly to `_club_load_warnings`. Also compute each team's last tournament date (`team_last_date`) for early-finish detection — flag if the gap between earliest and latest "last date" exceeds a configurable threshold (e.g. 60 days). Expose spread warnings via a `game_count_warnings` property.

- [x] Surface per-team game counts and spread warnings in Rich output
  - Files: tournament_scheduler/utils/rich_output.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/pipeline/stage3_planning.py
  - Approach: Add `print_game_count_table(plan, warnings)` to `TournamentOutput` — renders a Rich table with columns `Lag, Kamper totalt, Siste kampdato`. Call from `SeasonCommand._print_plan()` after `print_season_overview()`. Add spread-warning block (`print_game_count_warnings(warnings)`) that surfaces how many teams exceed the threshold and which teams have suspiciously early finish dates.

- [x] Surface per-team game counts in exported formats
  - Files: tournament_scheduler/csv/csv_exporter.py, tournament_scheduler/html/html_exporter.py
  - Approach: In the CSV overview (`_write_overview`), add columns for per-team game count info — either a new "team_game_counts" section in the overview or a new per-team CSV alongside the existing files. In the HTML exporter, add "Kamper per lag" section to the season overview page with a sortable table showing each team's game count and last tournament date.

- [x] Add tests for game count tracking, spread validation, and early-finish detection
  - Files: tests/test_season_planner.py
  - Approach: Extend `TestSeasonPlanner` with `test_team_game_counts_match_actual_games` (walk plan's games and verify counts match planner's `team_game_counts`), `test_game_count_spread_is_reasonable` (within max_game_count_spread when enough tournaments exist), `test_game_count_spread_threshold_triggers_warning`, `test_team_last_dates_tracked`. Use the existing `small_roster_planner_and_plan` fixture for scenarios where spread may be harder to keep tight.

## Notes
- The existing `_invite_counts` and `_opponent_history` track tournament invitations and actual matchups but NOT per-team game counts. A team could be invited to the same # of tournaments but play very different numbers of games within them (fewer teams in a tournament = fewer games per team). This validator closes that gap.
- The month-balance check (item 7, still open) checks tournament spread by month; this item checks per-team game counts and early-finish — they are complementary, not overlapping.
- `max_game_count_spread` should live in `federationDefaults` in the roster config file alongside `parallelGames` and `maxTeamsPerTournament`. Default: 2 games difference max.

## Acceptance Criteria
- [ ] A new `team_game_counts` dict is present on `SeasonPlan` after `build_plan()`, mapping each team's label to the number of round-robin games they play across the season.
- [ ] A `game_count_spread` int on `SeasonPlan` reports `max(team_game_counts.values()) - min(team_game_counts.values())`.
- [ ] `SeasonPlanner` accepts `max_game_count_spread` (default 2) and stores GameCountWarning entries when the spread exceeds it.
- [ ] Running `build_plan()` populates a per-team `last_game_date` dict, and `game_count_warnings` includes entries for teams whose last game is >60 days before the season end.
- [ ] `TournamentOutput.print_game_count_table()` renders a Rich table showing per-team game counts and last-game dates.
- [ ] The season command's Rich output shows game count warnings when the spread threshold is exceeded.
- [ ] Running the CSV exporter writes per-team game count data to a `team_game_counts` section in the overview output.
- [ ] Tests verify: game counts match actual games, spread validation catches violations, early-finish detection works.

## Log




### 2026-06-10 — Add tests for game count tracking, spread validation, and early-finish detection
**Done:** true
**Rationale:** Added 13 tests covering: game counts match actual games, last-game dates match latest tournament, spread is non-negative and equals max-min, spread warnings fire when threshold exceeded, no spread warnings with lenient threshold, early-finish warnings with tight threshold, fields present on SeasonPlan, invited teams included in counts, warning property returns correctly-structured data. All 206 tests pass.
**Findings:** Key test design insights: (1) With equal team counts per age group (1 team/club) all teams get equal game counts — spread is 0. (2) To create spread, use more teams than max per tournament (e.g. 6 teams with max 3). (3) Different age groups with different parallel-games configs naturally have different game counts (e.g. 15 vs 20), which is legitimate behavior — the threshold is a project policy choice.
**Files:** tests/test_season_planner.py (+182)
**Commit:** not committed
### 2026-06-10 — Surface per-team game counts in exported formats
**Done:** true
**Rationale:** Added per-team game count data to CSV export (new season_plan_team_counts.csv) and HTML export (collapsible "Kamper per lag" section with sortable table, spread badge in score bar). Both use the same team_game_counts data computed by SeasonPlanner. All 196 tests pass.
**Findings:** The HTML exports required adding both template HTML for the collapsible table and JavaScript to render it dynamically from an embedded JSON blob. The CSV export uses a separate file (season_plan_team_counts.csv) to avoid bloating the overview file. The spread is shown both as a badge in the score bar and in the table footer.
**Files:** tournament_scheduler/csv/csv_exporter.py (+40), tournament_scheduler/html/html_exporter.py (+69)
**Commit:** not committed
### 2026-06-10 — Surface per-team game counts and spread warnings in Rich output
**Done:** true
**Rationale:** Added TournamentOutput.print_game_count_table() — renders a Rich table with team label, total games, and last-game date, sorted by count descending. Added TournamentOutput.print_game_count_warnings() — renders spread warnings (per-team game count spread exceeds threshold) and early-finish warnings (teams whose last game is >60 days before season end). Wired both into SeasonCommand._print_plan(). All 196 tests pass.
**Findings:** The game count table sorts teams by game count descending so the most-loaded teams are at the top. The caption shows the aggregate spread (min/max). Spread warnings highlight teams at both extremes (>threshold); early-finish warnings highlight teams whose last game is suspiciously early.
**Files:** tournament_scheduler/utils/rich_output.py (+77), tournament_scheduler/cli/season_command.py (+7)
**Commit:** not committed
### 2026-06-10 — Add per-team game count tracking and spread validation to models/planner
**Done:** true
**Rationale:** Added team_game_counts, game_count_spread, team_last_game_dates fields to SeasonPlan model. Added _compute_game_counts method to SeasonPlanner that walks all Tournament.games across the season. Added max_game_count_spread and max_early_finish_gap_days parameters to SeasonPlanner.__init__. Added _scan_game_count_warnings for spread and early-finish detection. Updated pipeline serialization (stage3, stage4) and CLI season_command to pass the new config through. All 196 tests pass.
**Findings:** The existing _invite_counts tracked tournament invitations but not actual game counts — a team invited to fewer tournaments with more participants could end up with equal or greater game count. The new _compute_game_counts fills this gap. Early-finish detection compares each team's last game date against the season end date; when the gap exceeds max_early_finish_gap_days (default 60), the team is flagged.
**Files:** tournament_scheduler/models.py (+9), tournament_scheduler/season_planner.py (+100), tournament_scheduler/pipeline/stage3_planning.py (+5), tournament_scheduler/pipeline/stage4_export.py (+5), tournament_scheduler/cli/season_command.py (+2)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
