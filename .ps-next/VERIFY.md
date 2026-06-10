# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `Game` dataclass has a `round_number: int` field defaulting to 0. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `grep -c 'round_number' tournament_scheduler/season_planner.py` and confirm it returns > 0. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The Excel per-tournament sheet header says "Runde" instead of "Kamp #". | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The Excel per-tournament sheet shows `game.round_number` in the "Runde" column instead of sequential `1,2,3...`. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `pip check` passes (no dependency issues). | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `pytest` passes. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
