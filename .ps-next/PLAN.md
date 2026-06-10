# Plan: Girls' cross-region expansion — roster config support for neighbor regions
**Goal:** The roster config can optionally list clubs/teams from neighboring regions (e.g. Oslo), and those teams are available for girls' age-group tournaments.
**Created:** 2026-06-10
**Intent:** The RVV region alone has too few JU10/JU11 teams for a meaningful season. By adding a `neighborClubs` section to the roster config, organizers can include Oslo-area clubs without changing any scheduling logic.
**Backlog-ref:** 14

## Tasks
- [x] Add optional `region` field to the `Team` model
  - Files: tournament_scheduler/models.py
  - Approach: Add `region: str = "RVV"` to the `Team` dataclass. Existing code that constructs `Team(club=..., label=..., age_group=...)` without `region` will default to `"RVV"`, so no other callers need changes.

- [x] Update `RosterLoader.from_dict()` to support a `neighborClubs` section
  - Files: tournament_scheduler/roster_loader.py
  - Approach: In the extended config format (where `clubs` key exists), also accept an optional `neighborClubs` key with the same structure (club name → age group → team labels). Parse them identically to `clubs` but set `region` to the club name for each team (e.g. `Team(..., region="Oslo")`). The scheduler receives the same flat `Roster` — no scheduler changes needed.

- [x] Add tests for `neighborClubs` parsing
  - Files: tests/test_roster_loader.py, tests/test_stage1_config.py
  - Approach: Test that `neighborClubs` produces `Team` objects with the correct `region`, that `clubs` (without neighborClubs) still defaults to `"RVV"`, that validation errors (unknown age groups, empty entries) apply equally to neighbor clubs, and that the flat format (no `clubs` key) ignores neighborClubs silently.

## Notes
- The scheduler (`season_planner.py`) does not need changes — it already operates on a flat list of `Team` objects per age group.
- The only model change is adding a `region` field with a default, so all existing `Team(...)` constructions continue to work.
- The `roster_loader.py` docstring and examples should be updated to show the new `neighborClubs` format.

## Acceptance Criteria
- [ ] `Team` model has an `region` field defaulting to `"RVV"`.
- [ ] A roster config with `neighborClubs` loads without error and produces `Team` objects whose `region` matches the club name.
- [ ] A roster config without `neighborClubs` (only `clubs`) loads identically to before, with all teams having `region="RVV"`.
- [ ] The flat (legacy) format without `clubs` key is unaffected.
- [ ] Malformed entries in `neighborClubs` (unknown age group, empty entry, etc.) produce Norwegian-language error messages.
- [ ] All existing tests pass.

## Log



### 2026-06-10 — Add tests for `neighborClubs` parsing
**Done:** true
**Rationale:** Added TestNeighborClubs class with 7 tests: valid neighborClubs, unchanged extended format without neighborClubs, empty neighborClubs ignored, flat format rejection, invalid age group, empty entry, non-dict neighborClubs.
**Findings:** All 25 roster_loader tests pass (7 new + 18 existing). Stage1 config tests also pass (36 total). No regressions.
**Files:** tests/test_roster_loader.py (+TestNeighborClubs with 7 tests)
**Commit:** not committed
### 2026-06-10 — Update `RosterLoader.from_dict()` to support a `neighborClubs` section
**Done:** true
**Rationale:** Extracted _parse_clubs_section helper and wired neighborClubs into from_dict(). Neighbor-club teams get region set to their club name. Flat format unaffected.
**Findings:** Stage 1 config validation/parsing needs no changes — the external roster file path goes through load_with_defaults() which now supports neighborClubs, and the inline team list format has no region field (Team defaults to "RVV").
**Files:** tournament_scheduler/roster_loader.py (refactored, +neighborClubs support)
**Commit:** not committed
### 2026-06-10 — Add optional `region` field to the `Team` model
**Done:** true
**Rationale:** Added region: str = "RVV" to Team dataclass. Default value preserves backward compatibility with all existing Team(...) constructions.
**Findings:** No existing Team construction sites needed changes — the default handles them all.
**Files:** tournament_scheduler/models.py (+region field on Team)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
