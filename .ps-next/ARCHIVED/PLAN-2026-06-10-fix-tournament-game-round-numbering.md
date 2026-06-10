# Plan: Fix tournament game round numbering
**Goal:** `generate_round_robin_games()` stores `round_number` on each `Game`, and the Excel exporter shows a "Runde" column instead of sequential "Kamp #" numbering.
**Created:** 2026-06-10
**Intent:** Parallel games in the same round should share the same round number instead of being numbered sequentially 1,2,3...N across all games.
**Backlog-ref:** 19

## Tasks
- [x] Add `round_number: int` field to `Game` dataclass and propagate through (de)serialization
  - Files: tournament_scheduler/models.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: Add `round_number: int = 0` to `Game` in models.py. In `stage3_planning.py` `_dict_to_tournament()`, add `round_number=g.get("round_number", 0)` to `Game(...)`. In `stage4_export.py` `_dict_to_plan()`, same — add `round_number=int(g_dict.get("round_number", 0))` to `Game(...)`.

- [x] Set `round_number` in `generate_round_robin_games()` when constructing `Game`
  - Files: tournament_scheduler/season_planner.py
  - Approach: In `generate_round_robin_games()`, at line ~673 where `Game(home=home, away=away, parallel_slot=...)` is constructed, add `round_number=round_index + 1`.

- [x] Update Excel exporter to show round numbers instead of sequential enumeration
  - Files: tournament_scheduler/excel/plan_exporter.py
  - Approach: Rename `_GAMES_HEADERS` from `["Kamp #", ...]` to `["Runde", ...]`. In `_write_tournament_sheet()`, replace the `enumerate(tournament.games, start=1)` that writes `game_number` with `game.round_number`. Keep the parallel_slot column as-is (it shows which of the parallel games in that round each row belongs to).

## Notes
- The `generate_round_robin_games()` method already has `round_index` available in its loop — it just wasn't stored on `Game`.
- The `_GAMES_HEADERS` are: `["Kamp #", "Hjemmelag", "Bortelag", "Parallellbane"]`. Changing "Kamp #" to "Runde" makes it clear the column now shows which round the game belongs to.
- The per-tournament sheet also shows `game.parallel_slot + 1` which tells which timeslot (1-based) within that round — this is complementary, not a replacement.
- CSV and HTML exporters don't enumerate games so no changes needed there.
- Tests: no existing tests for plan_exporter or generate_round_robin_games, so no test updates required.

## Acceptance Criteria
- [ ] `Game` dataclass has a `round_number: int` field defaulting to 0.
- [ ] Run `grep -c 'round_number' tournament_scheduler/season_planner.py` and confirm it returns > 0.
- [ ] The Excel per-tournament sheet header says "Runde" instead of "Kamp #".
- [ ] The Excel per-tournament sheet shows `game.round_number` in the "Runde" column instead of sequential `1,2,3...`.
- [ ] `pip check` passes (no dependency issues).
- [ ] `pytest` passes.

## Log



### 2026-06-10 — Update Excel exporter to show round numbers instead of sequential enumeration
**Done:** true
**Rationale:** Renamed "Kamp #" header to "Runde" and replaced enumerate() with game.round_number in the per-tournament sheet writer. Updated test helper to use SeasonPlanner.generate_round_robin_games for proper round_number values, and updated test assertions to check game.round_number instead of sequential counter.
**Findings:** The test helper _round_robin_games was previously generating all-pairs linearly without round information. Switching to the real SeasonPlanner.generate_round_robin_games ensures tests verify realistic data.
**Files:** tournament_scheduler/excel/plan_exporter.py (+2/-2), tests/test_plan_exporter.py (+3/-5)
**Commit:** not committed
### 2026-06-10 — Set `round_number` in `generate_round_robin_games()` when constructing `Game`
**Done:** true
**Rationale:** Added round_number=round_index + 1 to the Game constructor inside the round-robin loop. round_index was already available (0-based), so round_number is 1-based for human readability.
**Findings:** The loop iterates round_index from 0 to num_rounds-1. Using round_index + 1 gives 1-based round numbers that match what an exported sheet should show.
**Files:** tournament_scheduler/season_planner.py (+1 line in generate_round_robin_games)
**Commit:** not committed
### 2026-06-10 — Add `round_number: int` field to `Game` dataclass and propagate through (de)serialization
**Done:** true
**Rationale:** Added round_number: int = 0 field to Game model, and added round_number=g.get("round_number", 0) to both stage3_planning.py and stage4_export.py deserialization paths so the field survives checkpoint round-trips.
**Findings:** Game model is a simple dataclass; adding a default field is backward compatible. The two (de)serialization sites in pipeline/stage3_planning.py and pipeline/stage4_export.py both needed the same treatment.
**Files:** tournament_scheduler/models.py (+1 line), tournament_scheduler/pipeline/stage3_planning.py (+1 line), tournament_scheduler/pipeline/stage4_export.py (+1 line)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
