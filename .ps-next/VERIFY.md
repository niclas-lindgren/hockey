# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `test_season_planner.py` passes a test asserting a team with target=2 is invited to at most 2 tournaments. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `test_stage1_config.py` passes a test asserting input.xlsx with per-team `target_tournament_count` column parses correctly. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| HTML and Excel reports show per-team target vs actual tournament participations. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Existing input.xlsx files without the column work unchanged (all existing tests pass). | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Per-team target field survives Stage 3→4 checkpoint round-trip (serialize + deserialize returns same value). | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| SeasonPlanner produces a valid plan when one team has target=2 and others have target=6 in the same age group. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
