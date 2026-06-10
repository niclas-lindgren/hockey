# Plan: No same-club matchups constraint
**Goal:** Teams from the same club are never scheduled against each other in the same tournament — enforced as a hard constraint at participant-selection time and with a safety filter in the round-robin generator.
**Created:** 2026-06-10
**Intent:** Multiple respondents flagged that intra-club games should never happen. The scheduler currently has a soft penalty (`max_club_teams_per_tournament=2`, penalty-based) which can still produce intra-club matchups. This makes it a true hard constraint.
**Backlog-ref:** 10

## Tasks
- [ ] Change default and harden participant-selection filter
  - Files: tournament_scheduler/season_planner.py
  - Approach: (a) Change `max_club_teams_per_tournament` default from `2` to `1`. (b) In `_pick_least_recently_grouped`, replace the soft club-penalty with a hard filter that excludes teams from clubs already represented in the selected set; if the filtered list is empty, fall back to the soft penalty to avoid deadlock. (c) In `_select_participants` when returning the entire age-group roster (small-group fast path), also cap at 1 team per club. (d) Update all docstrings from "soft limit" to "hard constraint."

- [ ] Add safety filter in round-robin generator
  - Files: tournament_scheduler/season_planner.py
  - Approach: In `generate_round_robin_games`, filter out any pair where both teams share the same `.club`. This is a belt-and-suspenders guard in case the participant-selection ever lets intra-club teams through.

- [ ] Update CLI/warning output and federation defaults
  - Files: tournament_scheduler/cli/season_command.py
  - Approach: (a) Update the default fallback in `season_command.py` from `2` to `1`. (b) Change `_print_club_load_warnings` to report club-load violations as errors (hard constraint broken) rather than warnings (soft limit exceeded). (c) Update the Norwegian output text to reflect "hard krav" language.

- [ ] Write tests
  - Files: tests/test_season_planner.py
  - Approach: (a) Test `_pick_least_recently_grouped` with multiple teams from the same club — verify only 1 team per club is selected. (b) Test `generate_round_robin_games` with teams from the same club — verify no intra-club games are generated. (c) Test `_select_participants` small-roster fast path with same-club teams.

## Notes
- The soft-club-load warnings system (`_scan_club_load_warnings`, `club_load_warnings`) is kept for backward compatibility but should never fire after this change if the hard constraint works correctly.
- The CLI's `--max-club-teams` flag and federation config key remain for flexibility but both default to `1`.
- This is purely backend logic; no UI/CLI changes needed beyond warning output.

## Acceptance Criteria
- [ ] `max_club_teams_per_tournament` defaults to `1` everywhere.
- [ ] `_pick_least_recently_grouped` never selects a second team from the same club unless no other candidates exist.
- [ ] `_select_participants` returns at most 1 team per club even on the small-roster fast path.
- [ ] `generate_round_robin_games` skips any pair where `game.home.club == game.away.club`.
- [ ] Existing tests continue to pass.
- [ ] New tests verify the hard-constraint behavior.

## Log
<!-- pi-next appends entries here after each task -->
