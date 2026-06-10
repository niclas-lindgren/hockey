# Plan: Tournament start time and computed duration/end time
**Goal:** Add a `start_time` field per tournament (e.g. 09:00), compute its duration/end-time from a configurable per-age-group `round_length_minutes` × the number of rounds scheduled for that tournament's age group, and surface start/end time in season_plan.html, calendars.html, the Excel export, and the iCal export (DTSTART/DTEND).
**Created:** 2026-06-10
**Intent:** Organizers and families currently only see a tournament date with no time-of-day information, making it impossible to plan travel or schedule around tournaments without contacting the host club.
**Backlog-ref:** 48

## Tasks
- [x] Added FEDERATION_ROUND_LENGTH_DEFAULTS dict to season_config.py with per-age-group default round lengths (U7/U8: 8min, U9/U10/JU10/JU11: 10min, U11/U12/JU12/JU13: 12min), and added round_length_minutes parsing/validation to stage1_config.py mirroring the parallel_games pattern, with federation defaults as fallback for missing age groups. — 2026-06-10
  - Files: tournament_scheduler/season_config.py, tournament_scheduler/pipeline/stage1_config.py
  - Approach: Mirror the `FEDERATION_PARALLEL_GAMES_DEFAULTS` pattern in season_config.py (lines 39-50): add a `FEDERATION_ROUND_LENGTH_DEFAULTS: Dict[str, int]` dict with sensible per-age-group minute values (e.g. U7/U8: 8, U9/U10: 10, U11/U12: 12, JU10/JU11: 10, JU12/JU13: 12), then in stage1_config.py add `round_length_minutes` parsing/validation in `validate_config()` (lines 165-187) and `_parse_config()` (lines 275-280) following the same dict-of-int validation as `parallel_games`, falling back to the federation defaults when a key is absent.

- [x] Added an optional start_time field (HH:MM string) to the Tournament dataclass plus duration_minutes(round_length) and end_time(round_length) helper methods that compute total duration from round_length * max round_number and the resulting end time via datetime/timedelta arithmetic. — 2026-06-10
  - Files: tournament_scheduler/models.py
  - Approach: Add `start_time: Optional[str] = None` (HH:MM string, e.g. "09:00") to the Tournament dataclass (around lines 131-139). Add a helper method or property (e.g. `duration_minutes(round_length: int) -> int` returning `round_length * len({g.round_number for g in self.games})` or `round_length * max(round_numbers, default=0)`, and `end_time(round_length: int) -> Optional[str]` that adds `duration_minutes` to `start_time` using `datetime`/`timedelta` and returns an HH:MM string, or None if `start_time` is unset.

- [x] Added round_length_for_age_group param to SeasonPlanner.__init__, set a DEFAULT_TOURNAMENT_START_TIME ("09:00") on each generated Tournament, and threaded round_length_minutes config through stage3_planning.py (_build_round_length, _make_planner) alongside parallel_games. Also added start_time to tournament serialization (_tournament_to_dict/_tournament_from_dict). — 2026-06-10
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/stage3_planning.py
  - Approach: When tournaments are constructed in season_planner.py (where `parallel_games` is currently consumed, around lines 120/229-230/518-519), set a default `start_time` (e.g. "09:00", configurable later) on each Tournament, and pass the resolved `round_length_minutes` config through stage3_planning.py (line 213, alongside how `parallel_games` is passed) so the planner has access to the per-age-group round length for duration calculations.

- [x] Added round_length_for_age_group param to ICalExporter and two helper methods (_tournament_start_datetime, _tournament_end_datetime) that derive DTSTART from tournament.start_time (falling back to start_hour) and DTEND from Tournament.duration_minutes()/end_time() driven by per-age-group round_length_minutes, falling back to the existing game_duration_minutes-based calculation when start_time or round length is unavailable. Applied to per-game events, the cancelled-tournament event, and the per-tournament summary event. — 2026-06-10
  - Files: tournament_scheduler/ical/ical_exporter.py
  - Approach: Replace the fixed `self.start_hour`/`self.game_duration_minutes` logic at lines 137-148 — build `dt_start` from `tournament.date` plus `tournament.start_time` (parsed HH:MM, falling back to `self.start_hour` if `start_time` is None for backward compatibility), and compute `dt_end` using the tournament's `end_time()`/`duration_minutes()` (driven by the per-age-group `round_length_minutes` passed into the exporter) instead of the flat `game_duration_minutes` constant.

- [x] Added "Starttid" and "Sluttid" columns to _OVERVIEW_HEADERS, added an optional round_length_for_age_group param to export()/_write_overview_sheet(), and appended tournament.start_time and the computed end time (via Tournament.end_time(round_length)) to each overview row, falling back to empty strings when unavailable. Updated test_overview_rows_match_plan_tournaments for the new columns. — 2026-06-10
  - Files: tournament_scheduler/excel/plan_exporter.py
  - Approach: Extend `_OVERVIEW_HEADERS` (line 37) with "Starttid" and "Sluttid" columns, and in `_write_overview_sheet` (lines 96-110) append `tournament.start_time or ""` and the computed end time string (via the Tournament model's `end_time()` using the resolved `round_length_minutes` for `tournament.age_group`) for each row.

- [ ] Surface start/end time in season_plan.html and calendars.html
  - Files: tournament_scheduler/pipeline/calendar_viewer.py, tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/styles.css
  - Approach: Locate where tournament cards/date blocks are rendered (the `.tournament-date` markup referenced in styles.css) in calendar_viewer.py and html_exporter.py, and add a small time-range element (e.g. "09:00–10:30") computed from `tournament.start_time` and the model's `end_time()` helper using the per-age-group `round_length_minutes`; add minimal supporting CSS rules alongside the existing `.tournament-date` styles.

- [ ] Add/update tests for round-length config, duration computation, and exports
  - Files: tests/test_season_planner.py, tests/test_models.py
  - Approach: Add a test verifying `round_length_minutes` is loaded/validated with federation defaults (mirroring existing `parallel_games` tests), and tests for the Tournament model's `duration_minutes`/`end_time` helpers across different age groups and round counts (including the no-`start_time` backward-compatible case returning None).

## Notes
- No prior plan covers start_time/duration; this is new ground beyond the existing `parallel_games`, `round_number`, and iCal/Excel export work already in HISTORY.
- Keep `start_time` optional/backward-compatible: existing tournaments without a start_time should not break exports (iCal falls back to its current fixed `self.start_hour` behavior, Excel/HTML show blank time columns).
- Federation default round lengths should be documented similarly to the `FEDERATION_PARALLEL_GAMES_DEFAULTS` comment block in season_config.py.

## Acceptance Criteria
- [ ] `tournament_scheduler/season_config.py` contains a `FEDERATION_ROUND_LENGTH_DEFAULTS` dict with an entry for every age group present in `FEDERATION_PARALLEL_GAMES_DEFAULTS`.
- [ ] The `Tournament` dataclass in `tournament_scheduler/models.py` has a `start_time` field and a duration/end-time helper that returns a computed HH:MM end time when `start_time` and round length are provided, and returns `None` when `start_time` is not set.
- [ ] `tournament_scheduler/ical/ical_exporter.py` produces VEVENTs with DTSTART set from `tournament.start_time` (when set) and DTEND set from the computed end time, falling back to the existing fixed-hour behavior when `start_time` is not set.
- [ ] The Excel overview sheet produced by `tournament_scheduler/excel/plan_exporter.py` contains "Starttid" and "Sluttid" columns with non-empty values for tournaments that have a `start_time`.
- [ ] Running `pytest` passes, including new tests covering `round_length_minutes` config validation and the Tournament duration/end-time computation.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-10 — Added FEDERATION_ROUND_LENGTH_DEFAULTS dict to season_config.py with per-age-group default round lengths (U7/U8: 8min, U9/U10/JU10/JU11: 10min, U11/U12/JU12/JU13: 12min), and added round_length_minutes parsing/validation to stage1_config.py mirroring the parallel_games pattern, with federation defaults as fallback for missing age groups.
**Rationale:** Mirrored the existing FEDERATION_PARALLEL_GAMES_DEFAULTS pattern for consistency with the codebase's existing config validation and merging conventions.
**Findings:** Added FEDERATION_ROUND_LENGTH_DEFAULTS dict, round_length_minutes validation in validate_config(), and merged round_length_minutes dict (defaults overridden by user config) into the parsed config output. Full test suite: 277 passed, 2 pre-existing failures in test_stage2_scraping.py unrelated to this change (confirmed failing on unmodified code too).
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage1_config.py (+29), tournament_scheduler/season_config.py (+18)
**Commit:** 67044b4 (hockey)

### 2026-06-10 — Added an optional start_time field (HH:MM string) to the Tournament dataclass plus duration_minutes(round_length) and end_time(round_length) helper methods that compute total duration from round_length * max round_number and the resulting end time via datetime/timedelta arithmetic.
**Rationale:** Followed the approach exactly as specified in the plan; kept start_time optional for backward compatibility, returning None from end_time when unset.
**Findings:** Tournament model now exposes start_time, duration_minutes(), and end_time(). Full test suite: 278 passed, 1 pre-existing flaky failure in test_stage2_scraping.py unrelated to this change.
LESSONS: none
**Files:** tournament_scheduler/models.py (+25/-1)
**Commit:** 7c1357a (hockey)

### 2026-06-10 — Added round_length_for_age_group param to SeasonPlanner.__init__, set a DEFAULT_TOURNAMENT_START_TIME ("09:00") on each generated Tournament, and threaded round_length_minutes config through stage3_planning.py (_build_round_length, _make_planner) alongside parallel_games. Also added start_time to tournament serialization (_tournament_to_dict/_tournament_from_dict).
**Rationale:** Followed the plan's approach of mirroring how parallel_games is passed through; added start_time to (de)serialization so the field round-trips through the pipeline checkpoint, since duration/end-time consumers downstream will need it.
**Findings:** SeasonPlanner now stores round_length_for_age_group and assigns start_time09:00 to every generated Tournament; stage3_planning passes round_length_minutes config through. Full test suite: 278 passed, 1 pre-existing failure in test_stage2_scraping.py unrelated to this change.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage3_planning.py (+18/-1), tournament_scheduler/season_planner.py (+10)
**Commit:** 09c48f9 (hockey)

### 2026-06-10 — Added round_length_for_age_group param to ICalExporter and two helper methods (_tournament_start_datetime, _tournament_end_datetime) that derive DTSTART from tournament.start_time (falling back to start_hour) and DTEND from Tournament.duration_minutes()/end_time() driven by per-age-group round_length_minutes, falling back to the existing game_duration_minutes-based calculation when start_time or round length is unavailable. Applied to per-game events, the cancelled-tournament event, and the per-tournament summary event.
**Rationale:** Centralized the start/end datetime computation into two helper methods to avoid duplicating fallback logic across the three event-generation code paths (per-game, cancelled, summary).
**Findings:** ICalExporter now derives event times from tournament.start_time and round_length_minutes when available, with full backward-compatible fallback to the prior start_hour/game_duration_minutes behavior. Full test suite: 278 passed, 1 pre-existing failure in test_stage2_scraping.py unrelated to this change.
LESSONS: ICalExporter call sites (stage4_export.py, cli/season_command.py) do not yet pass round_length_for_age_group — they will use the start_hour/game_duration_minutes fallback until wired up.
**Files:** tournament_scheduler/ical/ical_exporter.py (+72/-33)
**Commit:** 3ee1797 (hockey)

### 2026-06-10 — Added "Starttid" and "Sluttid" columns to _OVERVIEW_HEADERS, added an optional round_length_for_age_group param to export()/_write_overview_sheet(), and appended tournament.start_time and the computed end time (via Tournament.end_time(round_length)) to each overview row, falling back to empty strings when unavailable. Updated test_overview_rows_match_plan_tournaments for the new columns.
**Rationale:** Made round_length_for_age_group an optional kwarg defaulting to {} for backward compatibility with existing call sites in stage4_export.py and cli/season_command.py.
**Findings:** Excel overview sheet now has 9 columns (added Starttid/Sluttid). Full test suite: 278 passed, 1 pre-existing failure in test_stage2_scraping.py unrelated to this change.
LESSONS: SeasonPlanExporter.export() and ICalExporter both now accept an optional round_length_for_age_group kwarg defaulting to {}/None — existing call sites (stage4_export.py, cli/season_command.py) don't pass it yet and will see empty Sluttid / fallback iCal times until wired up.
**Files:** tests/test_plan_exporter.py (+5/-1), tournament_scheduler/excel/plan_exporter.py (+27/-4)
**Commit:** [pending — fill after commit]
