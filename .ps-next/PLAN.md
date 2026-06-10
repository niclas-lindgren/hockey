# PLAN

**Feature:** Time-of-day-aware arena slot finding for tournaments — depends on #48 (computed tournament duration per age group). Currently `find_available_dates` in `season_planner.py` only checks whole-day conflicts via `club_registry`, where each club has exactly one arena and calendar. Once #48 provides the required total duration for a tournament (round length × rounds for its age group), extend the scheduler to: (1) parse hour-level booking data from each arena's ice calendar (already scraped) to find actual free timeslots within a candidate date that fit the required duration, (2) if the preferred/host arena (e.g. Varner) has no free slot of sufficient length on that date, check other clubs'/arenas' calendars for the same date as fallback hosts, (3) among arenas with a fitting slot, pick the one offering the most optimal time-of-day (e.g. avoiding very early/late slots) while still respecting existing fairness constraints — proportional hosting per club team count (#11), travel distance (#46), and even per-team game spread. May require extending `club_registry`/`ClubCalendarSource` to support multiple arenas per club/region and exposing per-slot (not just per-day) availability from the calendar scrapers.

**Goal:** Time-of-day-aware arena slot finding for tournaments — depends on #48 (computed tournament duration per age group). Currently `find_available_dates` in `season_planner.py` only checks whole-day conflicts via `club_registry`, where each club has exactly one arena and calendar. Once #48 provides the required total duration for a tournament (round length × rounds for its age group), extend the scheduler to: (1) parse hour-level booking data from each arena's ice calendar (already scraped) to find actual free timeslots within a candidate date that fit the required duration, (2) if the preferred/host arena (e.g. Varner) has no free slot of sufficient length on that date, check other clubs'/arenas' calendars for the same date as fallback hosts, (3) among arenas with a fitting slot, pick the one offering the most optimal time-of-day (e.g. avoiding very early/late slots) while still respecting existing fairness constraints — proportional hosting per club team count (#11), travel distance (#46), and even per-team game spread. May require extending `club_registry`/`ClubCalendarSource` to support multiple arenas per club/region and exposing per-slot (not just per-day) availability from the calendar scrapers.

**Backlog-ref:** 51

**Constraints:** none

**Date:** 2026-06-10

**Intent:** Replace the fixed 09:00 start time and whole-day-only availability checks with real per-arena hour-level slot finding, so generated tournaments are scheduled at arenas and times that are actually free for the duration #48 computes, with sensible fallback hosts when the preferred arena is busy.

## Tasks

- [x] Added club_for_source_name() to club_registry.py to map Stage 1 source names to CLUB_REGISTRY club names, and a new _group_events_by_club() helper in stage2_scraping.py that groups serialized per-source events into a Dict[str, List[CalendarEvent dict]] keyed by club name, written to the checkpoint as 'events_by_club' alongside the existing flat 'sources' list. — 2026-06-10
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`, `tournament_scheduler/club_registry.py`
  - Acceptance: `stage2_scraping.py` produces (or returns alongside the flat event list) a `Dict[str, List[CalendarEvent]]` keyed by club name (using `CLUB_REGISTRY` club names), so downstream code can look up "all events for Frisk Asker's Varner Arena" without re-filtering a flat list; existing flat-list consumers continue to work unchanged.

- [x] Extracted TimeSlotChecker._find_available_slots into a new tournament_scheduler/utils/slot_finder.py module with find_available_slots(events, check_date, required_minutes, earliest_start, latest_start) parameterized by required duration in minutes; TimeSlotChecker now delegates to this shared function with unchanged behavior. — 2026-06-10
  - Files: `tournament_scheduler/conflict_checkers/timeslot_checker.py`, new `tournament_scheduler/utils/slot_finder.py`
  - Acceptance: A new `find_available_slots(events: List[CalendarEvent], check_date: date, required_minutes: int, earliest_start="09:00", latest_start="20:00") -> List[Tuple[str,str]]` function (or class) is extracted/generalized from `TimeSlotChecker._find_available_slots`, parameterized by required duration in minutes (not just hours) so it can consume `Tournament.duration_minutes(round_length)` directly; `TimeSlotChecker` is refactored to call this shared function so behavior is unchanged for existing callers.

- [x] Added arenas_for_date_search(host_club) to club_registry.py, returning the host club's known ClubCalendarSource entry first followed by all other clubs with known calendar sources, in CLUB_REGISTRY order, for use as fallback hosts during slot finding. — 2026-06-10
  - Files: `tournament_scheduler/club_registry.py`
  - Acceptance: `club_registry.py` exposes a function (e.g. `arenas_for_date_search(host_club: str) -> List[ClubCalendarSource]`) returning the host club's own entry first followed by other known clubs' entries (fallback candidates), without requiring a structural rewrite of `CLUB_REGISTRY` to support multiple arenas per club (single-arena-per-club model is preserved per club entry).

- [ ] Implement `find_arena_slot_for_date` in the scheduler combining duration + fallback + time-of-day scoring
  - Files: `tournament_scheduler/scheduler.py`, `tournament_scheduler/utils/slot_finder.py`
  - Approach: New method `TournamentScheduler.find_arena_slot_for_date(check_date: date, host_club: str, required_minutes: int, events_by_club: Dict[str, List[CalendarEvent]]) -> Optional[Tuple[str, str, str]]` (returns `(host_club_used, start_HH:MM, end_HH:MM)`). Tries the host club's arena first via `find_available_slots`; if no slot of `required_minutes` fits, iterates `club_registry.arenas_for_date_search(host_club)` fallback candidates in order. Among all arenas with a fitting slot, scores each candidate slot's start time against an "optimal window" (e.g. closest to 11:00, penalizing slots starting before ~10:00 or after ~16:00) and picks the best-scoring (host-arena ties broken in favor of the original host).
  - Acceptance: Calling `find_arena_slot_for_date` with a host club whose arena is fully booked on a date, but where another known club's arena has a fitting gap, returns that other club as `host_club_used` with valid `start_HH:MM`/`end_HH:MM` strings; calling it when the host arena has a fitting slot returns the host arena's slot without checking fallbacks unless that slot scores worse than a fallback's.

- [ ] Wire slot-aware host/time selection into `SeasonPlanner.build_plan`
  - Files: `tournament_scheduler/season_planner.py`
  - Approach: After `_assign_hosts(chosen_dates)` produces `host_assignments`, for each `(tournament_date, host_club)` compute `required_minutes` from `round_length_for_age_group.get(age_group)` × number of rounds (estimate rounds from `_max_teams_for`/participant count via `generate_round_robin_games`, consistent with how `Tournament.duration_minutes` is computed post-hoc) and call `scheduler.find_arena_slot_for_date(...)`. If a fallback host is selected, use that club's arena/host_club for the `Tournament` and adjust `arena_counts`/hosting bookkeeping accordingly (still counted toward `_assign_hosts`'s proportional totals via the originally assigned host_club where reasonable — document the tradeoff). Set `Tournament.start_time` to the selected slot's start time instead of `DEFAULT_TOURNAMENT_START_TIME`.
  - Acceptance: `SeasonPlanner.build_plan()` produces `Tournament` objects whose `start_time` reflects the actual computed free slot (not always `"09:00"`) when calendar events constrain the date, and falls back to `DEFAULT_TOURNAMENT_START_TIME` when no calendar data is available for any candidate arena (preserving current behavior for clubs with `skip=True`/unknown sources).

- [ ] Surface slot/host-fallback decisions in exports and rules report
  - Files: `tournament_scheduler/season_planner.py`, `tournament_scheduler/pipeline/stage4_export.py`
  - Approach: Extend the existing rules/decisions report (from the prior "rules-decisions-report" feature) with an entry explaining the time-of-day slot-finding rule and any fallback-host substitutions made (date, original host, fallback host, reason); ensure Excel/iCal/HTML exports already keyed off `Tournament.start_time`/`end_time(round_length)` (#48) automatically reflect the new computed times with no further export-layer changes needed beyond verification.
  - Acceptance: When `SeasonPlanner` substitutes a fallback host for a date, the rules/decisions report (CLI output and Excel sheet) contains a Norwegian-language line naming the original host, the fallback host, and the date; exporters produce Excel/iCal/HTML output reflecting the slot-derived `start_time` without additional per-exporter code changes.

- [ ] Add tests for per-arena slot finding, fallback hosting, and time-of-day scoring
  - Files: `tests/test_slot_finder.py` (new), `tests/test_scheduler.py`, `tests/test_season_planner.py`
  - Approach: Unit-test `find_available_slots` with synthetic `CalendarEvent` lists (fully booked day, single gap, multiple gaps) asserting correct `(start,end)` tuples for given `required_minutes`; test `TournamentScheduler.find_arena_slot_for_date` for host-has-slot, host-fully-booked-fallback-succeeds, and no-arena-has-slot cases; test `SeasonPlanner.build_plan` end-to-end with mocked `events_by_club` producing tournaments with non-default `start_time` and a fallback-host substitution recorded.
  - Acceptance: `pytest tests/test_slot_finder.py tests/test_scheduler.py tests/test_season_planner.py` passes, including new tests covering fully-booked-host-with-fallback and no-arena-available scenarios.

## Acceptance Criteria

- `find_available_slots` returns hour-level `(start, end)` time slot tuples per arena that fit the required tournament duration, derived from each arena's `CalendarEvent` list.
- When the host arena has no slot of sufficient length on a candidate date, `find_arena_slot_for_date` returns a fallback club/arena that does have a fitting slot, or reports that none is available.
- `SeasonPlanner.build_plan()` produces `Tournament.start_time` values that reflect the actual computed free slot rather than always defaulting to `"09:00"`, while still passing `_scan_hosting_warnings` and `_scan_game_count_warnings` checks.
- Running `pytest tests/test_slot_finder.py tests/test_scheduler.py tests/test_season_planner.py` exits with code 0 and the new fallback-host and no-slot-available test cases pass.
- The rules/decisions report output contains a line naming the original host, the fallback host, and the date whenever a fallback-host substitution occurs.

## Log

(no entries yet)

### 2026-06-10 — Added club_for_source_name() to club_registry.py to map Stage 1 source names to CLUB_REGISTRY club names, and a new _group_events_by_club() helper in stage2_scraping.py that groups serialized per-source events into a Dict[str, List[CalendarEvent dict]] keyed by club name, written to the checkpoint as 'events_by_club' alongside the existing flat 'sources' list.
**Rationale:** Matching is done by exact club name first, then case-insensitive prefix match (handles legacy source names like 'Kongsberg ishall' / 'Skien ishall' which append the hall name to the club name).
**Findings:** Verified mapping and grouping logic with a manual smoke test; full pytest suite passes (288 passed, 1 skipped) except one pre-existing unrelated failure (test_zero_events_blocks_source) that fails identically on main before this change.
LESSONS: none
**Files:** tournament_scheduler/club_registry.py (+21), tournament_scheduler/pipeline/stage2_scraping.py (+31)
**Commit:** e2fb65b (hockey)

### 2026-06-10 — Extracted TimeSlotChecker._find_available_slots into a new tournament_scheduler/utils/slot_finder.py module with find_available_slots(events, check_date, required_minutes, earliest_start, latest_start) parameterized by required duration in minutes; TimeSlotChecker now delegates to this shared function with unchanged behavior.
**Rationale:** Kept the function signature general (plain list of event-like objects with date/datetime/duration_hours) so the season planner can call it directly with Tournament.duration_minutes(round_length) without depending on the checker class.
**Findings:** Full pytest suite passes (288 passed, 1 skipped) except the same pre-existing unrelated failure (test_zero_events_blocks_source) seen before this change.
LESSONS: none
**Files:** tournament_scheduler/conflict_checkers/timeslot_checker.py (+8/-73), tournament_scheduler/utils/slot_finder.py (+132 new file)
**Commit:** 169e013 (hockey)

### 2026-06-10 — Added arenas_for_date_search(host_club) to club_registry.py, returning the host club's known ClubCalendarSource entry first followed by all other clubs with known calendar sources, in CLUB_REGISTRY order, for use as fallback hosts during slot finding.
**Rationale:** Preserved the single-arena-per-club model as specified -- no structural rewrite of CLUB_REGISTRY needed; clubs with skipTrue or no source are simply omitted from the candidate list.
**Findings:** Verified ordering with a manual smoke test (host first, host's own entry omitted from the fallback tail); full pytest suite passes (288 passed, 1 skipped) except the same pre-existing unrelated failure (test_zero_events_blocks_source).
LESSONS: none
**Files:** tournament_scheduler/club_registry.py (+35)
**Commit:** [pending — fill after commit]
