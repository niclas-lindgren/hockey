# Plan: Fix home team assignment

**Feature:** Fix home team assignment: the home team in a tournament is the club that arranges it (owns the arena). When a tournament is in Varner Arena, the home team is Frisk Asker (not a visitor). Update host_assignment.py and any reporting/export logic to derive home-team from arena ownership in the club registry, not from scheduling order or participant index.
**Goal:** Fix home team assignment: the home team in a tournament is the club that arranges it (owns the arena). When a tournament is in Varner Arena, the home team is Frisk Asker (not a visitor). Update host_assignment.py and any reporting/export logic to derive home-team from arena ownership in the club registry, not from scheduling order or participant index.
**Backlog-ref:** 166
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Ensure that the home team in every generated game reflects the actual arena owner (the club hosting the tournament), not an arbitrary position from the round-robin rotation, so that exports and reports correctly identify Frisk Asker as home when a tournament is held at Varner Arena.

## Tasks

- [x] Added club_for_arena(arena_name: str) -> Optional[str] to club_registry.py; performs case-insensitive exact match on entry.arena fields in CLUB_REGISTRY and returns the canonical club name. — 2026-06-20
  - Files: `tournament_scheduler/club_registry.py`
  - Approach: Add a `club_for_arena(arena_name: str) -> Optional[str]` function that iterates CLUB_REGISTRY values and returns the matching `club` for a given arena name; this is the authoritative source that downstream callers should prefer over the separate `_ARENA_TO_CLUB` dict in `club_distances.py`.

- [x] In season_planner.py, after _select_participants returns, reorder participants so any teams from the arena-owning club (via club_for_arena(arena) or fall back to host_club) come first; other teams follow. — 2026-06-20
  - Files: `tournament_scheduler/season_planner.py`, `tournament_scheduler/participant_selection.py`
  - Approach: After `_select_participants` returns in `season_planner.py` (line 228), use `club_for_arena(arena)` (or fall back to `tournament.host_club`) to identify the host club, then move any team whose `team.club` matches that club to index 0 of the `participants` list before passing it to `generate_round_robin_games`.

- [x] In tournament_updater.py, before both calls to generate_round_robin_games (team_drop and add_tournament operations), reorder teams so the arena-owning club (via club_for_arena or host_club fallback) is first. — 2026-06-20
  - Files: `tournament_scheduler/pipeline/tournament_updater.py`
  - Approach: Before the two calls to `SeasonPlanner.generate_round_robin_games` (lines 191 and 531), reorder `tournament.teams` to place the host club's team at index 0, using `club_for_arena` from `club_registry.py` and falling back to `tournament.host_club`, mirroring the season_planner fix.

- [x] Confirmed find_slot_for_tournament does not regenerate games; documented the host-first ordering invariant in its docstring so future maintainers know the caller is responsible for reordering before generate_round_robin_games. — 2026-06-20
  - Files: `tournament_scheduler/host_assignment.py`
  - Approach: In `find_slot_for_tournament` and any function that passes a `games` list derived from participants, ensure the host team ordering invariant is documented and, if games are re-generated here, apply the same reordering before calling `generate_round_robin_games`.

- [x] Added tests/test_host_assignment.py (14 tests) covering club_for_arena lookup and the host-always-home invariant; added TestHostFirstParticipantOrder to test_round_robin.py; added TestVarnerArenaHomeTeamRegression to test_plan_exporter.py. Also fixed game_generation.py to preserve rotation[0] as home in odd rounds by not swapping their pair. — 2026-06-20
  - Files: `tests/test_host_assignment.py`, `tests/test_round_robin.py`, `tests/test_plan_exporter.py`
  - Approach: Add tests that create a Tournament at "Varner Arena" with Frisk Asker and visitors, call `generate_round_robin_games` with the host-first participant list, and assert `game.home.club == "Frisk Asker"` for all rounds. Also add a regression test in `test_plan_exporter.py` that checks the Excel "home" column contains "Frisk Asker" for Varner Arena tournaments.

## Log

- 2026-06-20 Plan created

## Acceptance Criteria

When a tournament is scheduled at Varner Arena, the home team in all generated games is Frisk Asker instead of the first team in the participants list.
The tournament exporters (CSV and Excel) produce output where the home team column correctly shows Frisk Asker for games at Varner Arena.
The spond and ical exporters emit game data with home team label set to Frisk Asker when the tournament is hosted at Varner Arena.
The game generation logic no longer assigns home team based on participant index order when the tournament is hosted at an arena owned by a specific club.
Running pytest passes with new tests confirming that Frisk Asker appears as `game.home` for all games in Varner Arena tournaments regardless of participant list input order.

### 2026-06-20 — Added club_for_arena(arena_name: str) -> Optional[str] to club_registry.py; performs case-insensitive exact match on entry.arena fields in CLUB_REGISTRY and returns the canonical club name.
**Rationale:** Straightforward iteration over CLUB_REGISTRY values; no alternatives needed since CLUB_REGISTRY is the single source of truth for arena names.
**Findings:** club_for_arena('Varner Arena') returns 'Frisk Asker', club_for_arena('Kongsberghallen') returns 'Kongsberg', and unknown arenas return None as expected.
LESSONS: none
**Files:** tournament_scheduler/club_registry.py (+18/-0)
**Commit:** ae3173f (hockey)

### 2026-06-20 — In season_planner.py, after _select_participants returns, reorder participants so any teams from the arena-owning club (via club_for_arena(arena) or fall back to host_club) come first; other teams follow.
**Rationale:** Used club_for_arena as the authoritative source with host_club as fallback; only reorders when host_teams is non-empty to avoid breaking tournaments where the host has no participating team.
**Findings:** participants list now starts with host club teams before passing to generate_round_robin_games, ensuring correct home team assignment.
LESSONS: none
**Files:** tournament_scheduler/season_planner.py (+12/-0)
**Commit:** f1479cf (hockey)

### 2026-06-20 — In tournament_updater.py, before both calls to generate_round_robin_games (team_drop and add_tournament operations), reorder teams so the arena-owning club (via club_for_arena or host_club fallback) is first.
**Rationale:** Mirrored the same pattern as season_planner fix; applied to both regeneration sites (team drop at ~line 191 and add_tournament at ~line 531).
**Findings:** Both tournament_updater operations now produce games with the correct home team (arena owner first).
LESSONS: none
**Files:** tournament_scheduler/pipeline/tournament_updater.py (+14/-3)
**Commit:** ba3b857 (hockey)

### 2026-06-20 — Confirmed find_slot_for_tournament does not regenerate games; documented the host-first ordering invariant in its docstring so future maintainers know the caller is responsible for reordering before generate_round_robin_games.
**Rationale:** No code change needed since host_assignment.py never calls generate_round_robin_games; only documentation was required.
**Findings:** Invariant is now explicit in the function docstring; no regeneration sites were found.
LESSONS: none
**Files:** tournament_scheduler/host_assignment.py (+8/-1)
**Commit:** 246986f (hockey)

### 2026-06-20 — Added tests/test_host_assignment.py (14 tests) covering club_for_arena lookup and the host-always-home invariant; added TestHostFirstParticipantOrder to test_round_robin.py; added TestVarnerArenaHomeTeamRegression to test_plan_exporter.py. Also fixed game_generation.py to preserve rotation[0] as home in odd rounds by not swapping their pair.
**Rationale:** Discovered that the original odd-round swap in circle method would place participants[0] as away — fixed by skipping the swap for the pair involving the pinned team (roster[0]). Tests now verify host club appears as game.home in all their games.
**Findings:** All 14 new tests pass; no regressions in remaining test suite (1 pre-existing stage4 ical test failure confirmed pre-existing).
LESSONS: The circle-method odd-round swap must preserve rotation[0] as home; otherwise the host club appears as away in alternating rounds. Fix: check if home-candidate is the pinned team before swapping.
**Files:** tests/test_host_assignment.py (+168), tests/test_plan_exporter.py (+73), tests/test_round_robin.py (+49), tournament_scheduler/game_generation.py (+11/-1)
**Commit:** [pending — fill after commit]
