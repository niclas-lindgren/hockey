# Plan: Skill-level divisions for team matchups
**Goal:** Teams can be assigned an optional skill level (1–10) in the roster config, and the scheduler favours matchups within adjacent skill levels to prevent lopsided games while remaining backward-compatible when no levels are set.
**Created:** 2026-06-10
**Intent:** Weak clubs (Skien etc.) get blown out 20-0 when matched against top teams. An optional per-team skill tier lets the scheduler prefer matchups within adjacent levels, improving retention without breaking the existing config format.
**Backlog-ref:** 12

## Tasks
- [x] Add `skill_level` field to Team model and serialisation
  - Files: tournament_scheduler/models.py, tournament_scheduler/pipeline/stage3_planning.py
  - Approach: Add `skill_level: Optional[int] = field(default=None, repr=False)` to `Team` dataclass. Update `_team_to_dict` to include `skillLevel` (camelCase for JSON), `_tournament_from_dict` to reconstruct it, and `_find_team` to preserve it.

- [x] Support skill_level in roster config parser (mixed string/object format)
  - Files: tournament_scheduler/roster_loader.py
  - Approach: In `_parse_clubs_section`, when iterating labels in an age-group list, accept either a plain string (legacy — no skill level) or a dict with `"label"` and optional `"skillLevel"` key. Pass `skill_level` through to `Team()` constructor. Update error messages to reflect both formats.

- [x] Add skill-level proximity penalty to _pick_least_recently_grouped
  - Files: tournament_scheduler/season_planner.py
  - Approach: Extract skill_levels from `self.roster.teams` as a `label → int` map (only teams with a non-None skill level). In the `club_penalty`-style sort key inside `_pick_least_recently_grouped`, add a `skill_penalty(team)` factor that computes the median skill level of already-selected teams and returns a large penalty when `|team.skill_level - median|` exceeds a configurable band (default 2). Teams without a skill level get penalty 0 (no filtering). Threshold `division_skill_band: int = 2` is a new `SeasonPlanner.__init__` parameter. Backward-compatible: when no team in the age group has a skill level, the penalty is always 0 and behaviour is identical to current.

- [x] Wire skill-level config through stage3_planning and season_command
  - Files: tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/cli/season_command.py
  - Approach: In `_build_roster`, skill_level is already part of the Team model so no extra wiring needed there. In `_make_planner`, read `config.get("divisionSkillBand", 2)` or equivalent from the Stage 1 config (which comes from input.json) and pass to `SeasonPlanner.__init__`. In `season_command.py`, extract `divisionSkillBand` from `federation_defaults` and pass to the planner. Done.

- [x] Tests for skill-level participant selection
  - Files: tests/test_season_planner.py
  - Approach: Add test class `TestSkillLevelDivisions` with:
    1. `test_teams_without_skill_level_are_grouped_normally` — plain string roster with no skill levels produces identical subset selection to current code.
    2. `test_teams_with_skill_level_prefer_adjacent_levels` — build a roster of 8 teams (4 high-skill, 4 low-skill), max 4 per tournament, verify that the first few tournaments pick within adjacent bands.
    3. `test_skill_penalty_is_soft_not_hard` — with only 4 high-skill + 1 low-skill team in an age group and max 4 teams, verify a low-skill team is still selected when necessary (soft constraint, not exclusion).
    4. `test_skill_level_serialized_in_plan_dict` — verify `_team_to_dict` includes `skillLevel` and `_tournament_from_dict` round-trips correctly.
    5. `test_roster_loader_accepts_mixed_string_object_format` — verify roster_loader accepts a mix of strings and `{"label":..., "skillLevel":N}` entries and rejects invalid ones.

## Notes
- Skill level is 1–10 inclusive, higher = more skilled. Only integer values are valid. None/unset = "unrated" = no filtering applied.
- The division band (default 2) means teams with skill levels within 2 of each other are considered "adjacent" (e.g. levels 3 and 5 are adjacent, but 3 and 6 are not). Configurable per season.
- The penalty is soft — if there aren't enough teams in a band to fill a tournament, the planner falls through to teams from other bands rather than creating an undersized tournament or failing.
- No changes to `_pick_spread_dates` or `_assign_hosts` — skill divisions only affect which teams are selected for a given tournament, not which weekends or arenas.

## Acceptance Criteria
- [ ] A roster config with no skill_level fields produces identical tournament plans to the current code (backward compatible).
- [ ] When all teams in an age group have skill levels set, the first several tournaments in the plan select subsets whose skill levels stay within `division_skill_band` of each other.
- [ ] When the available skill-level pool is too small to fill a tournament, the scheduler falls back to teams from other skill levels rather than creating an undersized tournament.
- [ ] The roster loader accepts both plain strings and `{"label":"...", "skillLevel":N}` objects in team lists, and rejects malformed mixed entries with a clear Norwegian error message.
- [ ] Running `_team_to_dict` then `_tournament_from_dict` preserves the `skill_level` value for every team in the round-trip.

## Log





### 2026-06-10 — Tests for skill-level participant selection
**Done:** ✅ Added TestSkillLevelDivisions (5 tests) to test_season_planner.py and TestSkillLevelInRoster (9 tests) to test_roster_loader.py. Coverage: backward compat, clean separation, soft constraint, mixed unrated/rated teams, wide band disabling, config format validation. All 219 tests pass.
**Rationale:** Tests cover all acceptance criteria: backward compat, within-band grouping, soft fallback, unrated team handling, and roster config validation.
**Findings:** None.
**Files:** tests/test_season_planner.py (+120), tests/test_roster_loader.py (+80)
**Commit:** not committed
### 2026-06-10 — Wire skill-level config through stage3_planning and season_command
**Done:** ✅ stage3_planning.run() now reads divisionSkillBand from config (default 2) and passes it to _make_planner. season_command.py reads divisionSkillBand from federationDefaults in the roster config and passes to SeasonPlanner. All 44 existing tests pass.
**Rationale:** Minimal wiring — config flows through the same path as parallelGames and maxTeamsPerTournament. Default 2 means backward compatible when config doesn't specify divisionSkillBand.
**Findings:** None.
**Files:** tournament_scheduler/pipeline/stage3_planning.py (+3/-3), tournament_scheduler/cli/season_command.py (+2/-1)
**Commit:** not committed
### 2026-06-10 — Add skill-level proximity penalty to _pick_least_recently_grouped
**Done:** ✅ Added division_skill_band parameter (default 2) to SeasonPlanner.__init__. Added _team_skill_levels map from roster. Added skill_penalty() to _pick_least_recently_grouped sort key — prefers candidates within division_skill_band of selected set's median skill level. Teams without skill_level get no penalty (backward compatible). Verified with manual test: 8 teams (4 low/4 high) cleanly separate into skill-appropriate tournaments.
**Rationale:** Soft constraint in the sort key — teams from different skill bands are deprioritised, not excluded. When the pool in one band is too small, the scheduler falls back to other bands. Unrated teams (skill_level=None) are never penalised, fully backward-compatible.
**Findings:** The median-based approach works well: the first few tournaments reliably pick within the band, and once a band is exhausted the scheduler falls through to the next band. Verified with actual planner run.
**Files:** tournament_scheduler/season_planner.py (+30/-5)
**Commit:** not committed
### 2026-06-10 — Support skill_level in roster config parser (mixed string/object format)
**Done:** ✅ Roster config parser now accepts mixed format: plain strings (no skill level) or dicts with {"label": "...", "skillLevel": N}. Validates skillLevel as int 1-10. Extended format and neighborClubs both supported. All existing tests pass.
**Rationale:** Backward-compatible extension: plain strings keep working identically. Dict format allows specifying skillLevel without breaking any existing configs.
**Findings:** None.
**Files:** tournament_scheduler/roster_loader.py (+34/-11)
**Commit:** not committed
### 2026-06-10 — Add `skill_level` field to Team model and serialisation
**Done:** ✅ Added Optional[int] skill_level field to Team dataclass. Updated _team_to_dict to include skillLevel in serialised output (camelCase, omitted when None). Updated _tournament_from_dict to reconstruct skill_level from dict. All 32 existing tests pass.
**Rationale:** Simple dataclass field + conditional serialisation. skillLevel in camelCase in JSON follows existing convention (parallelGames, maxTeamsPerTournament, etc.). skill_level=None is the default making this fully backward-compatible.
**Findings:** None — straightforward field addition.
**Files:** tournament_scheduler/models.py (+1), tournament_scheduler/pipeline/stage3_planning.py (+4/-2)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
