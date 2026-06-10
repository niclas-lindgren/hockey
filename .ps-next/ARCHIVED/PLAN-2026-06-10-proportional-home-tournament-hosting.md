# Plan: Proportional home-tournament hosting
**Goal:** Clubs with more teams host proportionally more tournaments, surfaced as warnings when deviations exceed a threshold.
**Created:** 2026-06-10
**Intent:** A Jar with 7 teams hosting zero home tournaments while a single-team club hosts one is unfair and wears out the same parent group. The host assignment algorithm should distribute hosting duties proportionally to each club's team count.
**Backlog-ref:** 11

## Tasks
- [x] Modify `_assign_hosts` for proportional host assignment
  - Files: tournament_scheduler/season_planner.py
  - Approach: In `_assign_hosts`, compute per-club team counts from `self.roster`, derive proportional targets as `teams_in_club / total_teams * tournament_count`, then assign hosts greedily — always pick the club furthest below its proportional target. Keep the invariant that every club hosts at least once before any club hosts a second time (even for clubs with very few teams). Accept a `max_hosting_deviation` constructor parameter (default 1) to control how far from target is tolerated.

- [x] Add hosting-imbalance scanning and warnings
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/models.py
  - Approach: Add `_hosting_warnings: List[str]` and `hosting_warnings` property to `SeasonPlanner` (mirroring the `_club_load_warnings` / `club_load_warnings` pattern). After `build_plan`, scan actual hosting counts vs proportional targets and flag clubs that deviate by more than `max_hosting_deviation`. Store `hosting_deviation` on `SeasonPlan` for downstream use.

- [x] Wire warnings into CLI output
  - Files: tournament_scheduler/cli/season_command.py
  - Approach: Add `_print_hosting_warnings` method in `SeasonCommand` (following the `_print_club_load_warnings` pattern). Call it after `_print_club_load_warnings` in `run`.

- [x] Add tests for proportional hosting
  - Files: tests/test_season_planner.py
  - Approach: Add a `TestProportionalHosting` class with tests: (a) clubs with more teams host more tournaments, (b) clubs with equal team counts get equal hosting, (c) single-team clubs still host at least once, (d) warnings fire when hosting deviates from proportional target.

## Notes
- The current `_assign_hosts` uses a simple round-robin: every club hosts once before any repeats. This treats Jar (7 teams) the same as Skien (1 team).
- The existing `test_every_arena_hosts_at_least_one_tournament_before_any_repeats` test uses 6 clubs with 1 team each — all clubs have equal team counts, so proportional hosting == round-robin; this test should pass unchanged.
- The proportion is based on team counts in the roster, not club registry presence (a club in the registry but not in the roster has 0 teams and gets 0 hosting).
- Config parameter `max_hosting_deviation` (default 1) controls the warning threshold, same pattern as `max_game_count_spread`.

## Acceptance Criteria
- [ ] `test_clubs_with_more_teams_host_more_tournaments` passes — Jar (3 teams) hosts strictly more tournaments than Kongsberg (1 team).
- [ ] `test_every_club_hosts_at_least_once` passes — single-team clubs host at least one tournament.
- [ ] `test_equal_team_counts_get_equal_hosting` passes — clubs with equal team counts host within 1 of each other.
- [ ] A warning is surfaced when a club's actual hosting count deviates from its proportional target by more than `max_hosting_deviation`.
- [ ] Existing tests for even hosting (all clubs equal team counts) still pass with the new algorithm.

## Log




### 2026-06-10 — Add tests for proportional hosting
**Done:** Added TestProportionalHosting class with 6 tests covering proportional hosting, equal-team hosting, at-least-once hosting, and warnings
**Rationale:** Tests verify that clubs with more teams host proportionally more, equal team counts get equal hosting, single-team clubs host at least once, and warnings fire/are suppressed based on max_hosting_deviation.
**Findings:** All new tests pass alongside existing tests. The existing test_every_arena_hosts_at_least_one_tournament_before_any_repeats uses 6 clubs with 1 team each (equal counts → proportional == round-robin), so it passes unchanged.
**Files:** tests/test_season_planner.py (+TestProportionalHosting, 6 tests)
**Commit:** not committed
### 2026-06-10 — Wire warnings into CLI output
**Done:** Added _print_hosting_warnings to SeasonCommand and wired max_hosting_deviation through season_command.py and stage3_planning.py
**Rationale:** Follows the exact same pattern as _print_club_load_warnings. The config parameter flows through federation_defaults in the roster config, matching how maxGameCountSpread and divisionSkillBand are handled.
**Findings:** No backward-compatibility concerns — max_hosting_deviation defaults to 1 and is only read when present in config.
**Files:** tournament_scheduler/cli/season_command.py (+_print_hosting_warnings, +max_hosting_deviation), tournament_scheduler/pipeline/stage3_planning.py (+max_hosting_deviation param)
**Commit:** not committed
### 2026-06-10 — Add hosting-imbalance scanning and warnings
**Done:** Added _scan_hosting_warnings method, _hosting_warnings list, and hosting_warnings property to SeasonPlanner
**Rationale:** Follows the existing _club_load_warnings pattern. _scan_hosting_warnings compares actual hosting to proportional targets and appends warnings when deviation exceeds max_hosting_deviation.
**Findings:** Warnings are in Norwegian to match the interactive CLI conventions. The scan iterates all clubs and compares actual vs expected hosting counts.
**Files:** tournament_scheduler/season_planner.py (+_hosting_warnings, +hosting_warnings property, +_scan_hosting_warnings)
**Commit:** not committed
### 2026-06-10 — Modify `_assign_hosts` for proportional host assignment
**Done:** Implemented proportional host assignment using largest-remainder (Hare quota) and deficit-based greedy selection
**Rationale:** Replaced simple round-robin with proportional algorithm. Phase 1 ensures every club hosts at least once before repeats. Phase 2 assigns hosts proportionally by team count, picking the club furthest below its proportional target.
**Findings:** Largest-remainder method ensures integer targets sum exactly to tournament count. Existing tests with equal team counts pass unchanged since proportional == round-robin when all clubs have equal teams.
**Files:** tournament_scheduler/season_planner.py (+_assign_hosts rewrite, +max_hosting_deviation param)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
