# PLAN: Fix 'Runde' column showing 0 for all games in season-plan exports

**Backlog-ref:** 49

**Date:** 2026-06-10

**Goal:** Fix 'Runde' column showing 0 for all games in season-plan exports — Game.round_number (added for backlog item #19) is correctly set during scheduling (season_planner.py:1189 / 1317), but `_game_to_dict()` in `tournament_scheduler/pipeline/stage3_planning.py` (lines 128-133) does not serialize `round_number` into the checkpoint dict, so when `stage4_export.py:237` reads it back via `g_dict.get("round_number", 0)` it always defaults to 0. Fix `_game_to_dict` to include `round_number` so the Excel/HTML 'Runde' column shows the correct round number.

**Constraints:** none

**Intent:** Backlog item #19 added `round_number` to the `Game` model and wired the Excel/HTML "Runde" column to display it, but the round-trip through the Stage 3 checkpoint dict was left incomplete, so every exported game shows "Runde 0" — this fix closes that gap.

## Tasks

- [x] Added `"round_number": g.round_number` to the dict returned by `_game_to_dict()` in stage3_planning.py, alongside home/away/parallel_slot. — 2026-06-10
  - Files: tournament_scheduler/pipeline/stage3_planning.py
  - Add `"round_number": g.round_number` to the dict returned by `_game_to_dict()` in `tournament_scheduler/pipeline/stage3_planning.py` (lines 128-133), alongside the existing `home`, `away`, and `parallel_slot` keys.
  - Acceptance: the dict returned by `_game_to_dict()` for a `Game` with `round_number=3` contains `"round_number": 3`.

- [ ] Verify the deserialization paths read the new key correctly
  - Files: tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage4_export.py
  - Check `stage3_planning.py:291` (`round_number=g.get("round_number", 0)`) and `stage4_export.py:237` (`round_number=int(g_dict.get("round_number", 0))`) — both already read `round_number` from the dict, so once `_game_to_dict()` writes it, these paths should pick it up without further changes; confirm no other reconstruction site (e.g. `tournament_scheduler/excel/plan_exporter.py`) needs a matching update.
  - Acceptance: after running Stage 3 then Stage 4 on a sample plan, reconstructed `Game` objects have `round_number` matching the value originally assigned by `season_planner.py` (not 0).

- [ ] Add/extend a regression test covering the round trip
  - Files: tests/test_stage3_planning.py, tests/test_stage4_export.py
  - In `tests/test_stage3_planning.py`, add a test asserting `_game_to_dict()` includes `round_number` for a `Game` with a non-zero `round_number`. In `tests/test_stage4_export.py`, add or extend a test that builds a checkpoint dict containing `"round_number"` for a game and asserts the reconstructed `Game.round_number` matches (not 0).
  - Acceptance: `pytest tests/test_stage3_planning.py tests/test_stage4_export.py` passes, including the new/updated test cases.

- [ ] Re-run the export pipeline and confirm the 'Runde' column is fixed end-to-end
  - Files: tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage4_export.py
  - Run the season-plan pipeline (or the relevant unit/integration test) on existing checkpoint data and confirm the Excel and HTML 'Runde' column now shows the correct per-game round numbers (matching `season_planner.py`'s assigned `round_number`, not all zeros).
  - Acceptance: the generated Excel/HTML output for a multi-round tournament shows distinct, non-zero round numbers in the 'Runde' column corresponding to each game's actual round.

## Acceptance Criteria

- After regenerating a season-plan export, the Excel and HTML 'Runde' column shows the correct round numbers for each game instead of 0 for every row.
- The dict returned by `_game_to_dict()` in `tournament_scheduler/pipeline/stage3_planning.py` contains a `round_number` key whose value matches the source `Game.round_number`.
- `stage4_export.py` reads back `round_number` from the Stage 3 checkpoint dict and reconstructed `Game` objects have a `round_number` matching the value originally set during scheduling, not the default of 0.
- Running `pytest tests/test_stage3_planning.py tests/test_stage4_export.py` passes, including new test cases that cover round_number serialization and deserialization.
- No other export format (CSV, iCal, Spond) regresses — existing tests for those exporters continue to pass.

## Log

(empty — filled in by build-worker after each task)

### 2026-06-10 — Added `"round_number": g.round_number` to the dict returned by `_game_to_dict()` in stage3_planning.py, alongside home/away/parallel_slot.
**Rationale:** none
**Findings:** Verified pytest tests/test_stage3_planning.py passes (4 tests).
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage3_planning.py (+1/-0)
**Commit:** [pending — fill after commit]
