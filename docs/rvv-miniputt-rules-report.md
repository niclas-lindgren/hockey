# RVV Miniputt rules report

This is a review/discussion snapshot of the current season-planning logic.
It is based on the planner code, not on the marketing/docs wording, so it calls out where a rule is truly hard, soft, automatic, or only a warning.

## HARD rules

| Rule | What it does |
|---|---|
| Minimum 3 teams per tournament | Age groups with fewer than 3 teams are skipped. |
| Round-robin format | Every invited team plays every other invited team once. |
| Base per-club cap | Each tournament has a minimum club cap (`max_club_teams_per_tournament`). The effective cap can be expanded later by fairness logic. |
| No same-club matches | Games between teams from the same club are skipped. |
| Parallel-game capacity | Tournament size is capped by the configured number of parallel games for the age group. Federation defaults apply when the workbook does not override them. |

## SOFT rules / heuristics

| Rule | What it does |
|---|---|
| Skill-band preference | Teams with `skill_level` are preferred within `±divisionSkillBand` of the selected group median. This is a scoring penalty, not a strict exclusion. |
| Minimize repeat matchups | The planner prefers team combinations that have not already been grouped together. |
| Spread tournaments across the season | Dates are chosen in spaced buckets so the season is not clustered. |
| Proportional home-hosting | Clubs with more teams should host more often. |
| Balanced games per team | The planner tries to keep total games per team close together. |
| Balanced per-age-group share | Teams that drift too far from the age-group average are flagged. |
| Avoid overlapping age groups on the same date | Age groups that share players are given a strong penalty if they land on the same date. |
| Participation target | `deltakelser_per_lag` / `target_tournament_count` is a soft target, not a quota. |

## AUTOMATIC decisions / implementation rules

| Rule | What it does |
|---|---|
| Club-cap expansion | The base per-club limit can expand proportionally when a club has a larger share of teams in the age group. |
| Deficit-aware overrides | A team can exceed the normal club cap if its deficit is worse than the remaining alternatives. |
| Start time selection | If hall calendar data exists, the planner looks for a suitable slot and prefers a start time near 11:00. |
| Same-arena sequencing | When multiple tournaments share an arena and day, start times are sequenced with a buffer. |
| Round-robin home/away alternation | Home and away are alternated by round when games are generated. |

## WARNINGS / diagnostics

These do not block planning, but they surface problems for review:

- club-load warnings when a club exceeds its per-tournament share in an age group
- hosting warnings when home-tournament distribution deviates too much from proportional fairness
- game-count warnings when team game counts spread too far or teams finish too early
- per-team share warnings when a team is too far from age-group expectations
- feasibility warnings when the season window likely cannot satisfy the participation target
- same-arena / same-day collision warnings for overlapping bookings
- fallback host substitutions when the preferred host cannot fit the hall slot

## Important discussion point

The code currently labels the skill-band rule as "hard", but the implementation is soft: it only adds a penalty during participant selection.
That is worth confirming in review.

## Primary source files

- `tournament_scheduler/rules_report.py`
- `tournament_scheduler/participant_selection.py`
- `tournament_scheduler/warnings.py`
- `tournament_scheduler/season_planner.py`
- `tournament_scheduler/models.py`
- `tournament_scheduler/season_config.py`
