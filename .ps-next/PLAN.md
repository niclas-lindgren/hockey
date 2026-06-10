# Plan: Multi-team club load distribution
**Goal:** When a club has multiple teams (e.g. Jar 1–7), the season planner avoids putting several of them in the same tournament, with a soft constraint and configurable tolerance.
**Created:** 2026-06-10
**Intent:** Reduce the burden on parent/volunteer groups when a single club fields many teams — their teams should be spread across different tournaments rather than clumped together.
**Backlog-ref:** 16

## Tasks
- [x] Add club-load soft constraint to `_pick_least_recently_grouped` and expose warnings
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add `max_club_teams_per_tournament` parameter to `SeasonPlanner.__init__` (default 2). In `_pick_least_recently_grouped()`, add club-load as a sorting penalty — teams from clubs that already have N teams in the current selection get pushed down. Harden `_select_participants` to pass date context when available (no change to the `build_plan` call). After building the plan, scan tournaments for club-load violations and expose them via a `club_load_warnings` property.

- [x] Wire max-club-teams config through CLI and roster config
  - Files: tournament_scheduler/cli/season_command.py, tournament_scheduler.py, tournament_scheduler/roster_loader.py (if federation defaults)
  - Approach: Read `maxClubTeamsPerTournament` from `federationDefaults` in the roster config file if present. Add `--max-club-teams` CLI flag as override. Pass the value to `SeasonPlanner.__init__`. Surface warnings in the console output.

## Notes
- The club-load constraint works at the participant-selection level: when building a tournament, prefer selecting teams from clubs that aren't yet over-represented in that tournament's participant set.
- Default tolerance is 2 teams per club per tournament — a club sending 2 teams to the same tournament is reasonable; 3+ is a burden.
- This is a soft constraint: if the alternative is leaving a tournament undersized, the constraint can be exceeded.
- The existing `_pick_least_recently_grouped` already sorts candidates by multiple criteria (repeat matchups, co-attendance, invite count). Club load is an additional tie-breaking factor.

## Acceptance Criteria
- [ ] Run `python3 -c 'from tournament_scheduler.season_planer import SeasonPlanner; assert hasattr(SeasonPlanner.__init__, "__code__")'` and confirm no error.
- [ ] `pytest` passes.
- [ ] A club with 5+ teams in the same age group has at most `max_club_teams_per_tournament` teams in any single tournament, assuming enough other clubs exist.
- [ ] Club load warnings are accessible via the `club_load_warnings` property after `build_plan`.

## Log


### 2026-06-10 — Wire max-club-teams config through CLI and roster config
**Done:** true
**Rationale:** Added --max-club-teams CLI flag. Wire maxClubTeamsPerTournament from federationDefaults in roster config. Pass to SeasonPlanner.__init__. Surface club-load warnings in both CLI (season_command.py) and interactive (tournament_scheduler_interactive.py) flows.
**Findings:** The config flows from federationDefaults.maxClubTeamsPerTournament in the roster JSON, overridable by --max-club-teams CLI flag. Warnings are displayed after the diversity summary in both CLI and interactive modes.
**Files:** tournament_scheduler.py (+2 lines), tournament_scheduler/cli/season_command.py (+import, +logic, +method), tournament_scheduler_interactive.py (+config extraction, +warning rendering)
**Commit:** not committed
### 2026-06-10 — Add club-load soft constraint to `_pick_least_recently_grouped` and expose warnings
**Done:** true
**Rationale:** Added max_club_teams_per_tournament param (default 2) to SeasonPlanner.__init__. Modified _pick_least_recently_grouped to penalize teams from clubs already at the limit. Added _scan_club_load_warnings() and club_load_warnings property. Verified with unit test.
**Findings:** The club-load penalty is a soft constraint: if all candidates exceed the limit, the best-worst is still chosen. The penalty factor of 100 * club_count outweighs typical repeat-matchup scores (which are small integers).
**Files:** tournament_scheduler/season_planner.py (expanded __init__, modified _pick_least_recently_grouped, added _scan_club_load_warnings, club_load_warnings property)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
