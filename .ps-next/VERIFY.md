# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Run `python3 -c 'from tournament_scheduler.season_planer import SeasonPlanner; assert hasattr(SeasonPlanner.__init__, "__code__")'` and confirm no error. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `pytest` passes. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| A club with 5+ teams in the same age group has at most `max_club_teams_per_tournament` teams in any single tournament, assuming enough other clubs exist. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Club load warnings are accessible via the `club_load_warnings` property after `build_plan`. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
