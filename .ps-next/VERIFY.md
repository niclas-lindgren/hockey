# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `max_club_teams_per_tournament` defaults to `1` everywhere. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `_pick_least_recently_grouped` never selects a second team from the same club unless no other candidates exist. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `_select_participants` returns at most 1 team per club even on the small-roster fast path. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `generate_round_robin_games` skips any pair where `game.home.club == game.away.club`. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Existing tests continue to pass. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| New tests verify the hard-constraint behavior. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
