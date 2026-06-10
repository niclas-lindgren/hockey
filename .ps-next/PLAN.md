# Plan: Uneven team count support with bye rounds
**Goal:** The scheduler handles odd team counts end-to-end: the heuristic allows odd-sized subsets, bye information is visible in all exports.
**Created:** 2026-06-10
**Intent:** When an age group has an odd number of teams, the round-robin already works (circle method with None as bye placeholder). But the `_max_teams_for` heuristic always returns even numbers, so odd-sized subsets are never selected via `_pick_least_recently_grouped`. Furthermore, bye rounds are invisible in exports — organizers need to see which team sits out each round.
**Backlog-ref:** 36

## Tasks
- [x] Modify `_max_teams_for` heuristic to allow odd team counts
  - Files: tournament_scheduler/season_planner.py
  - Approach: Change the fallback formula from `max(4, min(DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games - 1, parallel_games * 3))` to `max(4, min(DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games, parallel_games * 3))` — removing the `- 1` that forces evenness for pg=2 and pg=3. The round-robin generator already handles odd counts correctly.

- [x] Add `bye_teams` computed method on `Tournament` model
  - Files: tournament_scheduler/models.py
  - Approach: Add a `@property` or method `get_bye_rounds() -> Dict[int, List[str]]` that, for each round, finds participating teams that appear in no games for that round. These are the teams with a bye. Return `{round_number: [team_label, ...], ...}`.

- [x] Show bye rows in Excel per-tournament game sheets
  - Files: tournament_scheduler/excel/plan_exporter.py
  - Approach: After the game rows in `_write_tournament_sheet`, append bye rows when the tournament has an odd number of teams. Format: `[round_number, "(Pause)", team_label, ""]` for each team with a bye that round. The "Kamp-tabell" section already lists rounds — bye rows fit naturally alongside game rows.

- [x] Include bye rows in CSV games export
  - Files: tournament_scheduler/csv/csv_exporter.py
  - Approach: In `_write_games`, append rows with `home="(Pause)"` and `away=team_label` for each bye. Keep date/arena/age_group consistent.

- [ ] Show bye info in HTML report tournament cards
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: In the tournament card rendering (JavaScript template), add a "Pause denne runden" line for each bye. The JSON serialization already includes games, so the JS can compute byes client-side from the games array.

## Notes
- The round-robin `generate_round_robin_games` already handles odd team counts via circle method with `None` placeholder — no changes needed there.
- Tests in `tests/test_round_robin.py` already verify odd-n behavior (n=5, 7 pass).
- The `_pick_least_recently_grouped` accepts any `count` — it works with odd values already.
- `_select_participants` uses all teams when `len(candidates) <= max_teams`, so odd-sized whole-age-group rosters already work. Only the subset-picking path was affected.
- The `SpondExporter` and `ICalExporter` don't need bye support since they're calendar-level, not game-level.
- Input config `maxTeamsPerTournament` already overrides the heuristic — users can already set odd values there.

## Acceptance Criteria
- [ ] grep: `max(4, min(DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games, parallel_games * 3))` found in season_planner.py (no `- 1`)
- [ ] grep: `get_bye_rounds` found in models.py, returns correct dict for odd-sized tournaments
- [ ] grep: plan_exporter.py contains `Pause` and writes bye rows after game rows for odd-sized tournaments
- [ ] run: grep -c 'Pause' export/season_plan.csv returns > 0 when a tournament has odd team count
- [ ] grep: html_exporter.py contains bye/pause rendering logic in tournament card generation
- [ ] Existing tests pass (run: pytest tests/test_round_robin.py tests/test_season_planner.py)

## Log




### 2026-06-10 — Include bye rows in CSV games export
**Done:** Add bye rows to `_write_games` in CsvExporter: after regular game rows, append `[date, arena, age_group, "(Pause)", team_label, ""]` for each bye.
**Rationale:** Consistent with Excel format: "(Pause)" as home, bye team as away, empty parallel_slot. Keeps the same CSV column structure.
**Findings:** Verified 5 bye rows exported for 5-team tournament. All 50 existing tests pass.
**Files:** tournament_scheduler/csv/csv_exporter.py (+12)
**Commit:** not committed
### 2026-06-10 — Show bye rows in Excel per-tournament game sheets
**Done:** Append bye rows after game rows in `_write_tournament_sheet`: `[round_number, "(Pause)", team_label, ""]` for each team with a bye. Only runs when tournament.get_bye_rounds() is non-empty.
**Rationale:** Bye rows fit naturally alongside game rows — they share the same column structure (Runde/Hjemmelag/Bortelag/Parallellbane), with "(Pause)" as home and the bye team as away.
**Findings:** Verified with ad-hoc test: 5-team tournament exports 5 bye rows (one per round). All 50 existing tests pass.
**Files:** tournament_scheduler/excel/plan_exporter.py (+7)
**Commit:** not committed
### 2026-06-10 — Add `bye_teams` computed method on `Tournament` model
**Done:** Add `get_bye_rounds() -> Dict[int, List[str]]` method on Tournament that detects which teams have a bye in each round when the team count is odd.
**Rationale:** Simple computation from existing games list: for each round, find participating teams not appearing as home/away in any game. No model changes needed beyond this method.
**Findings:** Method correctly identifies 1 bye per round for 5-team tournaments. Even-sized tournaments return empty dict. Verified with ad-hoc test.
**Files:** tournament_scheduler/models.py (+22)
**Commit:** not committed
### 2026-06-10 — Modify `_max_teams_for` heuristic to allow odd team counts
**Done:** Remove `- 1` from fallback heuristic so `_max_teams_for` can return odd values when parallel_games is 3 (now 9 instead of 8) or for other configs.
**Rationale:** The `- 1` in `DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games - 1` was forcing evenness for pg=2 (6) and pg=3 (8). Removing it allows pg=3 to return 9, pg=4 to return 10, etc. The round-robin generator already handles odd counts via the circle method with None as bye placeholder.
**Findings:** All 44 existing tests pass. The `generate_round_robin_games` already handles odd n (tests cover n=5,7). Only the participant-selection heuristic was blocking odd subsets.
**Files:** tournament_scheduler/season_planner.py (+1/-1)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
