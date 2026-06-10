# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Run `python3 -c 'from tournament_scheduler.club_distances import distance, furthest_traveling_team; assert callable(distance); assert callable(furthest_traveling_team)'` and confirm no error. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `pytest` and confirm all existing tests still pass. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `python3 -c 'from tournament_scheduler.models import Tournament; from tournament_scheduler.club_distances import furthest_traveling_team; t = Tournament(date=None, arena="Kongsberghallen", age_group="U10"); assert furthest_traveling_team(t) is None'` and confirm empty tournament returns None. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `python3 -c 'from tournament_scheduler.club_distances import distance; assert distance("Kongsberg", "Jar") > 50'` and confirm distance lookup returns a reasonable value. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `python3 -c 'from tournament_scheduler.club_distances import furthest_traveling_team; from tournament_scheduler.models import Team, Tournament; t = Tournament(date=None, arena="Kongsberghallen", age_group="U10", teams=[Team(club="Jar", label="Jar 1", age_group="U10"), Team(club="Kongsberg", label="Kongsberg U10", age_group="U10")]); result = furthest_traveling_team(t); assert result is not None and result[0].label == "Jar 1"'` and confirm furthest-traveling logic picks the team farthest from the host. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
