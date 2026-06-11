# PLAN

**Feature:** Residual per-team game-count skew remains after backlog item 45's fix: for the real roster, Jar's 7 U10 teams get ~13-18 games each while Kongsberg's sole U10 team gets ~25 (spread 17, vs configured max_game_count_spread2). Three investigations confirmed this is structural: _max_club_teams_for's proportional cap (ceil(club_teams/total_teams_in_age_group * maxTeamsPerTournament)) gives Jar only 3-of-6 slots per tournament for its 7 teams while Kongsberg's 1 team gets its 1 slot almost every tournament. Fully closing the gap requires either increasing maxTeamsPerTournament for age groups with high team-count ratios, or a season-wide deficit-based allocation model that doesn't rely on a fixed per-tournament per-club cap. The new per_team_share_warnings diagnostic (added by item 45) already surfaces this skew in CLI/Excel output.

**Goal:** Residual per-team game-count skew remains after backlog item 45's fix: for the real roster, Jar's 7 U10 teams get ~13-18 games each while Kongsberg's sole U10 team gets ~25 (spread 17, vs configured max_game_count_spread2). Three investigations confirmed this is structural: _max_club_teams_for's proportional cap (ceil(club_teams/total_teams_in_age_group * maxTeamsPerTournament)) gives Jar only 3-of-6 slots per tournament for its 7 teams while Kongsberg's 1 team gets its 1 slot almost every tournament. Fully closing the gap requires either increasing maxTeamsPerTournament for age groups with high team-count ratios, or a season-wide deficit-based allocation model that doesn't rely on a fixed per-tournament per-club cap. The new per_team_share_warnings diagnostic (added by item 45) already surfaces this skew in CLI/Excel output.

**Backlog-ref:** 58

**Constraints:** none

**Date:** 2026-06-11

**Intent:** Reduce the structural game-count skew between clubs with many same-age-group teams (Jar) and clubs with a single team (Kongsberg) so the season plan more closely meets the configured max_game_count_spread, building on the per_team_share_warnings diagnostic added by backlog item 45.

## Tasks

- [x] Added a _deficit_score(team, age_group) helper plus _expected_average_for and a new _running_game_counts dict (maintained incrementally in _record_grouping) that tracks each team's game count during selection, before _team_game_counts is computed. _pick_least_recently_grouped's seed-selection now sorts by deficit first. — 2026-06-11
  - Files: `tournament_scheduler/season_planner.py`
  - Approach: Add a small helper method (e.g. `_deficit_score(team, age_group)`) that computes `expected_average_for(age_group) - _team_game_counts.get(team.label, 0)`, reusing the same `expected = sum(counts) / len(counts)` calculation pattern from `_scan_per_team_share_warnings`, and call this helper from `_pick_least_recently_grouped` and `_select_participants` so the deficit metric stays consistent across selection and diagnostics.

- [x] Replaced the hard per-club cap filter in _pick_least_recently_grouped's hard_filtered step and the _select_participants small-roster fast path (formerly _cap_per_club) with a deficit-aware version: an over-cap candidate is excluded only if some under-cap candidate has an equal-or-larger _deficit_score; otherwise it stays eligible with a scaled club_penalty of (club_count - max_club + 1) * 50. Added a _club_cap_overrides counter incremented whenever an over-cap team is actually selected. — 2026-06-11
  - Files: `tournament_scheduler/season_planner.py`
  - Approach: In `_pick_least_recently_grouped` (~lines 1276-1295), the current `hard_filtered` step excludes any candidate whose club already has `_max_club_teams_for(age_group, club)` teams in `selected`, with a fallback to `remaining` plus a `club_penalty` only when `hard_filtered` is empty — but `hard_filtered` is rarely empty (other clubs' teams are usually available), so an over-cap sibling from a many-team club like Jar stays excluded even when it has the largest deficit in the whole age group. Change the filter so an over-cap candidate is excluded only if at least one under-cap candidate in `remaining` has a deficit score (`_deficit_score`, from the previous task) >= the over-cap candidate's deficit; otherwise the over-cap candidate stays eligible but is sorted using `club_penalty` scaled by how far its club is over `_max_club_teams_for` (e.g. `(club_count - max_club + 1) * 50`), so it is only chosen over an under-cap, lower-deficit candidate when its own deficit is large enough to outweigh the penalty. Apply the same deficit-aware override to the equivalent hard pre-filter in `_select_participants` (~lines 1117-1155). Goal: same-club pairings beyond `_max_club_teams_for` happen only when no under-cap sibling needs the slot more, and stay as rare/small as possible.

- [ ] Update per_team_share_warnings and add a club-cap-override counter
  - Files: `tournament_scheduler/season_planner.py`
  - Approach: Re-verify `_scan_per_team_share_warnings` (around line 539-567) still correctly computes `expected = sum(counts) / len(counts)` and flags `abs(actual - expected) > max_game_count_spread` after the deficit-aware selection change; adjust the warning message/identifier if needed so it reflects the new (reduced but possibly still nonzero) skew accurately for both CLI and Excel consumers. Additionally, add a small counter/diagnostic (e.g. on the planner instance, surfaced alongside `per_team_share_warnings`) that records how many times the deficit-aware override let a club exceed `_max_club_teams_for` in a tournament, so operators can confirm same-club pairings beyond the proportional cap stayed minimal.

- [ ] Add real-roster regression tests for reduced U10 spread and minimal cap overrides
  - Files: `tests/test_season_planner.py`
  - Approach: Add new test case(s) using the `documentation/input.json` real roster that run a full `build_plan`/season generation for U10, then assert (1) the Jar-vs-Kongsberg `team_game_counts` spread is measurably reduced compared to the previously documented 13-18 vs ~25 (spread 17) baseline — either now within `max_game_count_spread` or, if a structural floor remains, the new (smaller) bound is documented and `per_team_share_warnings` reflects it; and (2) the new club-cap-override counter is small relative to the total number of tournaments (i.e. same-club pairings beyond `_max_club_teams_for` remain the exception, not the norm).

- [ ] Document the deficit-aware club-cap override behavior
  - Files: `README.md`
  - Approach: Add a short section to `README.md` describing the deficit-aware override: when a team from a club at its `_max_club_teams_for` cap has a larger game-count deficit than every available under-cap candidate, it can still be selected (with a same-club penalty applied), so a club fielding many same-age-group teams (e.g. Jar) isn't structurally starved of games — and explain that this is intended to make multiple same-club teams per tournament rare, occurring only when needed to keep per-team game counts balanced. Follow the existing documentation style/conventions used elsewhere in `README.md`.

## Acceptance Criteria

- The season planner outputs balanced game counts across all teams within the same age group when multiple teams exist for that age group.
- The system produces per-team share warnings that report when game count spreads exceed the configured max_game_count_spread threshold.
- Running pytest tests/test_season_planner.py exits with code 0 and the new real-roster regression test(s) pass, confirming the Jar-vs-Kongsberg U10 spread is reduced compared to the previously documented baseline of 13-18 vs ~25.
- The team selection logic in _pick_least_recently_grouped returns teams ordered such that teams furthest below the age-group's expected average game count are not starved relative to over-served teams, even when that requires exceeding _max_club_teams_for for a club.
- The new club-cap-override counter shows that same-club pairings beyond _max_club_teams_for remain rare (small relative to the total number of tournaments), confirming the cap is bypassed only when needed to reduce a deficit.
- README.md contains a documented description of the deficit-aware club-cap override behavior.

## Log

- 2026-06-11: Revised plan based on user feedback — replaced the per-age-group max_teams_per_tournament override (Task 3) with a deficit-aware soft override of _max_club_teams_for, since same-club pairings are likely inevitable for clubs with many same-age-group teams (Jar) but should be minimized rather than forbidden. Updated tasks 4-6 and acceptance criteria accordingly.

### 2026-06-11 — Added a _deficit_score(team, age_group) helper plus _expected_average_for and a new _running_game_counts dict (maintained incrementally in _record_grouping) that tracks each team's game count during selection, before _team_game_counts is computed. _pick_least_recently_grouped's seed-selection now sorts by deficit first.
**Rationale:** _team_game_counts is only populated after build_plan finishes, so it could not be used live during selection as the plan literally described; introduced _running_game_counts as a live proxy updated per tournament (participants-1 games each) and based _deficit_score/_expected_average_for on that instead, mirroring _scan_per_team_share_warnings's averaging pattern.
**Findings:** Deficit-aware seed selection alone already reduced Kongsberg U11's deviation from the U10/U11 age-group average below max_game_count_spread, so it is no longer flagged in per_team_share_warnings; updated test_jar_vs_kongsberg_team_counts_skew_is_bounded accordingly. All 52 tests pass.
LESSONS: _team_game_counts is empty during selection (only populated post-build_plan) — any deficit signal used during selection must be based on a running/incremental counter (_running_game_counts), not _team_game_counts directly.
**Files:** tournament_scheduler/season_planner.py (+56/-2), tests/test_season_planner.py (+13/-... )
**Commit:** 38bd4bc (hockey)

### 2026-06-11 — Replaced the hard per-club cap filter in _pick_least_recently_grouped's hard_filtered step and the _select_participants small-roster fast path (formerly _cap_per_club) with a deficit-aware version: an over-cap candidate is excluded only if some under-cap candidate has an equal-or-larger _deficit_score; otherwise it stays eligible with a scaled club_penalty of (club_count - max_club + 1) * 50. Added a _club_cap_overrides counter incremented whenever an over-cap team is actually selected.
**Rationale:** Implemented a shared one-shot helper _cap_per_club_deficit_aware for the small-roster fast path mirroring the iterative override in _pick_least_recently_grouped, since the two code paths have different shapes (one-shot list filter vs greedy loop). Removed the now-unused module-level _cap_per_club function.
**Findings:** All 52 season_planner tests and the full pytest suite (330 passed, 1 skipped) pass; the only failure (test_stage2_scraping.py::test_zero_events_blocks_source) is a pre-existing unrelated checkpoint-file test failure confirmed via git stash.
LESSONS: none
**Files:** tournament_scheduler/season_planner.py (+101/-38)
**Commit:** [pending — fill after commit]
