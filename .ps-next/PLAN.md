# PLAN

**Feature:** Verify tournament/match scheduling fairness: game counts per team are very skewed (e.g. Jar club gets only 13 games while Kongsberg gets 84). Investigate the matching/scheduling algorithm - it appears a club's total team count is being matched against other clubs' totals instead of pairing comparable teams within similar age groups, so each team should get a roughly similar number of games regardless of club size.

**Goal:** Verify tournament/match scheduling fairness: game counts per team are very skewed (e.g. Jar club gets only 13 games while Kongsberg gets 84). Investigate the matching/scheduling algorithm - it appears a club's total team count is being matched against other clubs' totals instead of pairing comparable teams within similar age groups, so each team should get a roughly similar number of games regardless of club size.

**Backlog-ref:** 45

**Constraints:** none

**Date:** 2026-06-11

**Intent:** A 6x per-team game-count skew (Jar ~13 games vs Kongsberg ~84) makes the season plan unfair to small-roster clubs; the root cause must be confirmed and fixed so each team gets a roughly even share of the season's games regardless of how many same-club teammates share its age group.

## Codebase Findings (carried from investigation)

- `tournament_scheduler/season_planner.py`: `_select_participants` (line 1010) and `_pick_least_recently_grouped` (line 1045) select at most `max_club_teams_per_tournament` (default 1, set in `__init__` ~line 141, configured via `cli/season_command.py` line 67) teams from a single club per tournament.
- `_record_grouping` (line 1138) increments `_invite_counts` per selected team **label**; `_pick_least_recently_grouped` seeds selection with the least-invited team (line 1069), balancing invitations across individual teams.
- `documentation/input.json`: Kongsberg has 1 team in U10 and 1 in U11 (2 teams total). Jar has 7 teams in U10 and 6 in U11 (13 teams total).
- `_next_age_group` (line 970) round-robins through age groups roughly evenly, so the number of tournaments per age group is roughly fixed regardless of how many teams that age group/club has.
- Because `max_club_teams_per_tournament=1`, each U10 tournament can invite only ONE Jar team out of Jar's 7 U10 teams, while Kongsberg's single U10 team is eligible (and selected) almost every time U10 is scheduled. The fixed per-age-group "club slot" gets divided across all of a club's same-age-group teams via `_invite_counts` — so each individual Jar U10 team gets roughly 1/7th the invitations of Kongsberg's sole U10 team, producing per-team game counts of ~13 (Jar) vs ~84 (Kongsberg).
- `_assign_hosts` (line 888) assigns **hosting** proportionally to total club team count (Hare quota) — this controls how many tournaments a club hosts, not how many of a club's teams get invited as participants, so it does not address this imbalance.
- `_compute_game_counts` (line 429) populates `_team_game_counts`/`game_count_spread`; `_scan_game_count_warnings` flags spread violations after the fact, but the underlying selection algorithm still produces the skew because spread-detection runs after selection rather than informing it.
- `Roster.by_age_group(age_group)`, `Roster.age_groups()`, `Roster.clubs()` helper methods exist in `tournament_scheduler/models.py` (lines 91-109) and can be used to compute per-club, per-age-group team counts.
- `tests/test_season_planner.py` has existing tests for selection/grouping logic to extend.

## Tasks

- [ ] Write a diagnostic test reproducing the per-team game-count skew with a Jar-vs-Kongsberg-shaped roster
  - Files: tests/test_season_planner.py
  - Approach: Add a test that builds a roster mirroring `documentation/input.json` (Jar: 7 U10 + 6 U11 teams; Kongsberg: 1 U10 + 1 U11 team, plus the other clubs), runs `SeasonPlanner.build_plan` over a representative season window, and asserts on `plan.team_game_counts` to show the skew between an individual Jar team and Kongsberg's team before any fix (this test should currently demonstrate the imbalance, e.g. via a documented `xfail` or an assertion capturing the ratio).

- [ ] Document the root cause inline in the selection code
  - Files: tournament_scheduler/season_planner.py
  - Approach: Add docstring/comment notes to `_select_participants`, `_pick_least_recently_grouped`, and `_record_grouping` explaining that `_invite_counts` balances per-team labels but does not account for how many same-club teammates share an age group, so a club's fixed per-tournament "slot" gets diluted across all its same-age-group teams — referencing this PLAN's findings for future readers.

- [x] Added a normalized invite-count helper '_normalized_invite_count' that multiplies each team's raw invite count by the number of same-club teams in the same age group, and used it as the tie-break key (replacing the raw _invite_counts lookup) in both the seed-team selection and the candidate sort in _pick_least_recently_grouped. — 2026-06-11
  - Files: tournament_scheduler/season_planner.py
  - Approach: In `_pick_least_recently_grouped`, normalize the seeding/tie-break key derived from `_invite_counts` by the number of same-club teams in that team's age group (e.g. compare `invite_count * num_club_teams_in_age_group` or an equivalent normalized "expected share" metric) so a Jar U10 team with 6 siblings is prioritized roughly 7x more often than Kongsberg's sole U10 team for the same number of raw invites, equalizing each team's expected per-season invitation count.

- [x] Added '_scan_per_team_share_warnings', a new scan method computing each age group's average game count and flagging teams whose actual count deviates by more than max_game_count_spread, exposed via a new 'per_team_share_warnings' property and called from build_plan. — 2026-06-11
  - Files: tournament_scheduler/season_planner.py
  - Approach: Extend `_scan_game_count_warnings` (or add a new `_scan_per_team_share_warnings` method following the same pattern) to compute, for each team, an "expected" game count derived from its club/age-group team count and flag teams whose actual `_team_game_counts` deviates from this expectation beyond `max_game_count_spread`, surfacing club name and age group in the warning tuple.

- [ ] Surface the new per-team-share warnings in CLI/Excel output
  - Files: tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/cli/season_command.py
  - Approach: Follow the existing pattern used for `club_load_warnings`/`month_load_warnings` to print the new per-team-share warnings via Rich console output and include them in the Excel "rules and decisions" report sheet.

- [ ] Add regression tests covering the fix and the new warning
  - Files: tests/test_season_planner.py
  - Approach: Update the diagnostic test from task 1 to assert the fix resolves the skew (game counts for Jar U10 teams and Kongsberg's U10 team fall within `max_game_count_spread` of each other), and add a new test that constructs a deliberately skewed roster and asserts the new per-team-share warning is emitted with the correct club/age-group identifiers.

- [ ] Verify end-to-end with the real roster and confirm the spread is resolved
  - Files: tournament_scheduler/season_planner.py, tests/test_season_planner.py
  - Approach: Run `SeasonPlanner.build_plan` against the real `documentation/input.json` roster (covering the 2026-09-01 to 2027-04-30 season window from `input.json`), print/assert `plan.team_game_counts` for Jar's U10 teams vs Kongsberg's U10 team, and confirm `plan.game_count_spread` is within `max_game_count_spread` and no per-team-share warnings are emitted for this roster.

## Acceptance Criteria

- Running `pytest tests/test_season_planner.py` exits with code 0 and all tests pass, including the new Jar-vs-Kongsberg game-count tests.
- After the fix, `plan.team_game_counts` for the real `documentation/input.json` roster has each individual Jar U10 team's game count within `max_game_count_spread` of Kongsberg's U10 team's game count (no team is left at ~13 while another is at ~84).
- `tournament_scheduler/season_planner.py` contains a new or extended warning-scanning method that reports per-team game-count deviations relative to a club/age-group-normalized expectation, including the affected club and age group.
- The CLI output (via `cli/season_command.py`) and the Excel "rules and decisions" report (via `pipeline/stage4_export.py`) display the new per-team-share warnings when game counts are skewed beyond the configured threshold.
- `_pick_least_recently_grouped` in `season_planner.py` normalizes its selection priority by the number of same-club teams sharing a team's age group, so a club fielding many teams in one age group no longer dilutes each individual team's invitation share relative to a club fielding a single team in that age group.

## Log

- [2026-06-11] Plan created from backlog item 45.

### 2026-06-11 — Added a normalized invite-count helper '_normalized_invite_count' that multiplies each team's raw invite count by the number of same-club teams in the same age group, and used it as the tie-break key (replacing the raw _invite_counts lookup) in both the seed-team selection and the candidate sort in _pick_least_recently_grouped.
**Rationale:** none
**Findings:** All 75 season/planner-related tests pass; full suite has 1 pre-existing unrelated failure (test_zero_events_blocks_source) confirmed present before this change too.
LESSONS: none
**Files:** tournament_scheduler/season_planner.py (+38/-2)
**Commit:** 8cdd5a5 (hockey)

### 2026-06-11 — Added '_scan_per_team_share_warnings', a new scan method computing each age group's average game count and flagging teams whose actual count deviates by more than max_game_count_spread, exposed via a new 'per_team_share_warnings' property and called from build_plan.
**Rationale:** none
**Findings:** All 49 season_planner tests pass; new method follows the existing _scan_*_warnings pattern (club_load, hosting, month_load).
LESSONS: none
**Files:** tournament_scheduler/season_planner.py (+61)
**Commit:** [pending — fill after commit]
