# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Run `SeasonPlanner.__init__` with `deficit_cap_expansion=1` parameter and verify it is stored | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `_max_club_teams_for` and verify it returns a higher cap when deficit spread exceeds `max_game_count_spread` | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `_pick_least_recently_grouped` sort and show deficit score multiplied by 1000 as primary key | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run new test `test_game_count_spread_improves_with_deficit_cap_expansion` and verify normalized spread < 0.5 | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run all existing tests in `test_season_planner.py` and `test_stage3_planning.py` without failures | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Update fairness gate normalized spread to use `max_possible_spread` denominator | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
