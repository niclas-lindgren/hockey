# Plan: New club calendar scrapers (Holmen, Jutul, Jar, Ringerike, Frisk Asker)
**Goal:** New club calendar scrapers (Holmen, Jutul, Jar, Ringerike, Frisk Asker) — extend `tournament_scheduler/data_sources/` with scrapers/configs for each new club's calendar (Outlook/Playwright or iCal as appropriate), reusing `fetch_events` and the existing on-disk cache, and wire each into the calendar-source selection in both CLI entry points.
**Created:** 2026-06-08
**Intent:** Expand calendar coverage to all RVV clubs needed for season scheduling so conflict checks include every relevant arena.
**Backlog-ref:** 3

## Tasks
- [x] Added tournament_scheduler/data_sources/calendar_source_factory.py with build_calendar_source(entry, cache) that maps CalendarSourceKind to scraper instances (OUTLOOK -> IceHallCalendar+OutlookCalendarScraper, ICAL -> IceHallCalendar+ICalScraper), returning None for UNKNOWN/skip entries; refactored club_registry.build_data_source to delegate to it and rewired scheduling_command.py to use the factory instead of hardcoded IceHallCalendar instantiation. — 2026-06-08
  - Files: tournament_scheduler/data_sources/calendar_source_factory.py, tournament_scheduler/club_registry.py
  - Approach: Add a small factory function (e.g. `build_calendar_source(entry: ClubCalendarSource, cache: CalendarCache)`) that returns the appropriate `BaseCalendarScraper`-compatible instance based on `entry.kind` (`ICAL` -> `ICalScraper(entry.source, cache)` wrapped in `IceHallCalendar`, `OUTLOOK` -> `OutlookCalendarScraper(cache)`), skipping/raising clearly for `UNKNOWN`/`skip=True` entries — this replaces the ad-hoc hardcoded instantiation seen in `scheduling_command.py` (`scraper = CalendarScraper(); kongsberg = get_club("Kongsberg"); IceHallCalendar(kongsberg.source, scraper)`).

- [x] Fixed ICalScraper to support arbitrary feed URLs (previously it only worked for Google Calendar email-style IDs, mangling any full URL into an invalid Google Calendar address); verified each of the three feeds live and updated the registry: Ringerike's source corrected to its real Teamup ICS export (https://ics.teamup.com/feed/ksr8bg1tpn5s3npskw/0.ics, confirmed working end-to-end with 121 events fetched and tournament-filtered); Jar and Jutul moved to skipTrue with detailed notes since their registered URLs are not usable iCal feeds (Forumbooking ical.aspx returns an empty placeholder VEVENT; Bærum ishall embeds a JS-only StyledCalendar widget with no exposed .ics feed). — 2026-06-08
  - Files: tournament_scheduler/club_registry.py, tournament_scheduler/data_sources/calendar_source_factory.py, tournament_scheduler/data_sources/ical_scraper.py
  - Approach: These three already have `kind=ICAL`, real `source` URLs, and `skip=False` in `CLUB_REGISTRY` (Jutul: `https://baerumishall.no/kalender/`, Jar: forumbooking URL, Ringerike: teamup URL) — confirm `ICalScraper` (which already implements `scrape_calendar` via `requests` + `icalendar`/`recurring_ical_events` and uses `self.cache`) parses each feed's event format correctly, adjusting parsing/dedup logic in `ical_scraper.py` only if a feed's structure (e.g. Teamup or Forumbooking export quirks) requires it.

- [ ] Replace hardcoded calendar-source instantiation in both CLI entry points with the registry-driven factory
  - Files: tournament_scheduler/cli/scheduling_command.py, tournament_scheduler/cli/reschedule_command.py
  - Approach: Replace the current hardcoded blocks (`scraper = CalendarScraper(); kongsberg = get_club("Kongsberg"); ... IceHallCalendar(kongsberg.source, scraper); BallHallCalendar(...)`) with a loop over `CLUB_REGISTRY` that calls the new factory for every entry where `skip=False`, building a list of calendar sources passed into `fetch_events`/the scheduler — preserving existing Kongsberg/Skien behavior while adding Jutul, Jar, Ringerike automatically (and Holmen/Frisk Asker once their entries are populated).

- [ ] Research and populate real calendar-source entries for Holmen and Frisk Asker, replacing their `UNKNOWN`/`skip=True` stubs
  - Files: tournament_scheduler/club_registry.py
  - Approach: Investigate each club's public calendar (check their official sites/arena booking systems — e.g. Forumbooking, Teamup, Outlook embeds, iCal feeds — similar to how Jutul/Jar/Ringerike sources were identified); update the `CLUB_REGISTRY` entries with the discovered `kind`, `source` URL, `skip=False`, and an updated `note`; if no usable calendar source can be found, leave `skip=True` with a note documenting what was checked and why it was rejected (do not leave the generic "URL not yet provided" placeholder note unchanged).

- [ ] Implement and verify scrapers for Holmen and Frisk Asker against their newly-discovered sources
  - Files: tournament_scheduler/data_sources/ical_scraper.py, tournament_scheduler/data_sources/calendar_scraper.py, tournament_scheduler/data_sources/calendar_source_factory.py
  - Approach: For each club, use the factory from task 1 to wire the discovered source into the appropriate existing scraper class (`ICalScraper` for iCal/Teamup/Forumbooking feeds, `OutlookCalendarScraper`-style Playwright scraping for Outlook embeds following the pattern in `calendar_scraper.py`); add club-specific config only where the existing scraper classes need a new constructor parameter (e.g. a configurable URL for Outlook-style scraping, mirroring how `ICalScraper` already takes a `calendar_id`).

- [ ] Add or extend tests covering the new scrapers and the registry-driven factory
  - Files: tests/test_calendar_source_factory.py, tests/test_club_registry.py, tests/test_ical_scraper.py
  - Approach: Add unit tests asserting the factory returns the correct scraper type per `CalendarSourceKind`, that `skip=True`/`UNKNOWN` entries are excluded from the CLI's source list without raising, and that `ICalScraper` correctly parses representative fixture feeds for the new clubs (using cached/sample iCal payloads, following existing test conventions under `tests/`).

## Notes
- Constraints: none.
- `CLUB_REGISTRY` (in `tournament_scheduler/club_registry.py`) already contains entries for Jutul, Jar, and Ringerike with real URLs and `kind=ICAL`/`skip=False` — these are not yet wired into either CLI's actual scraper-building logic, which currently hardcodes only Kongsberg (and implicitly Skien via `IceHallCalendar`/`GoogleCalendarScraper`).
- Holmen and Frisk Asker registry entries are genuine stubs (`kind=UNKNOWN`, `source=None`, `skip=True`, note="TODO: calendar URL not yet provided") per `PROJECT.md` — finding their real calendar URLs is in-scope research work for this feature, not a blocker to defer.
- Reuse `fetch_events` (via `BaseCalendarScraper`/`IceHallCalendar`) and `CalendarCache` (`tournament_scheduler/utils/calendar_cache.py`) for all new sources — do not introduce a parallel caching mechanism.
- `scheduling_command.py` and `reschedule_command.py` currently hardcode `CalendarScraper()`/`get_club("Kongsberg")`/`IceHallCalendar(...)`/`BallHallCalendar(...)` — both need to move to a registry-driven loop so new clubs are picked up without further CLI edits.
<!-- Research: none provided -->

## Acceptance Criteria
- [ ] When the CLI is run with the calendar-source selection enabled, it produces output that lists Holmen, Jutul, Jar, Ringerike, and Frisk Asker alongside the existing clubs without raising an exception.
- [ ] The CLUB_REGISTRY contains entries for all five clubs with `kind` set to `ICAL` or `OUTLOOK` (not `UNKNOWN`) and a non-null `source`, or — for any club where no real calendar source could be found — `skip=True` with a note that documents what was checked.
- [ ] Running the CLI with an entry that has `skip=True` does not crash; that source is excluded from the fetched event list and no error is reported for it.
- [ ] Both `scheduling_command.py` and `reschedule_command.py` build their calendar-source lists by iterating `CLUB_REGISTRY` rather than hardcoding club names, and each calls `fetch_events` through the shared `BaseCalendarScraper` interface.
- [ ] Each new iCal-based scraper reads its configured feed URL, returns parsed `CalendarEvent` objects, and writes them to the on-disk `CalendarCache` (verifiable via cache file contents or a passing test in `tests/`).

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-08 — Added tournament_scheduler/data_sources/calendar_source_factory.py with build_calendar_source(entry, cache) that maps CalendarSourceKind to scraper instances (OUTLOOK -> IceHallCalendar+OutlookCalendarScraper, ICAL -> IceHallCalendar+ICalScraper), returning None for UNKNOWN/skip entries; refactored club_registry.build_data_source to delegate to it and rewired scheduling_command.py to use the factory instead of hardcoded IceHallCalendar instantiation.
**Rationale:** Discovered club_registry.py already had a build_data_source helper doing similar work (without cache support); rather than duplicating logic, made the new factory the canonical implementation and turned build_data_source into a thin backward-compatible wrapper to avoid breaking existing season_command.py callers and tests.
**Findings:** All 61 tests pass (60 passed, 1 skipped, unchanged); manually verified build_calendar_source returns correct IceHallCalendar instances for all 9 RVV registry entries and None for the 4 UNKNOWN/skip clubs.
LESSONS: club_registry.py already contained a build_data_source(entry) helper nearly identical to the requested factory — search for existing equivalents before writing new factory modules; also note the factory must lazy-import from club_registry to avoid circular imports since club_registry now delegates back to it.
**Files:** tournament_scheduler/cli/scheduling_command.py (+2/-2), tournament_scheduler/club_registry.py (+13/-17), tournament_scheduler/data_sources/calendar_source_factory.py (+73/-0)
**Commit:** 0fd705a (hockey)

### 2026-06-08 — Fixed ICalScraper to support arbitrary feed URLs (previously it only worked for Google Calendar email-style IDs, mangling any full URL into an invalid Google Calendar address); verified each of the three feeds live and updated the registry: Ringerike's source corrected to its real Teamup ICS export (https://ics.teamup.com/feed/ksr8bg1tpn5s3npskw/0.ics, confirmed working end-to-end with 121 events fetched and tournament-filtered); Jar and Jutul moved to skipTrue with detailed notes since their registered URLs are not usable iCal feeds (Forumbooking ical.aspx returns an empty placeholder VEVENT; Bærum ishall embeds a JS-only StyledCalendar widget with no exposed .ics feed).
**Rationale:** Live-fetched all three feeds before assuming they'd parse — discovered the registered 'source' values for Jutul and Jar were HTML viewer pages, not iCal feeds, and that ICalScraper's URL-building logic was hardcoded to the Google Calendar template, which would silently produce a broken URL for any full-URL calendar_id. Chose to mark Jar/Jutul as skip with explanatory notes rather than wire them to non-functional endpoints, since shipping a scraper that always returns zero events would be worse than clearly flagging the gap for follow-up research (likely needs Playwright-based scraping for Jutul, and auth/session investigation for Jar).
**Findings:** Ringerike now fetches and tournament-filters real events end-to-end (121 events in a 60-day window, 1 tournament match found); all 61 tests pass (60 passed, 1 skipped) after updating test_club_registry.py's CLUBS_WITH_KNOWN_SOURCES/CLUBS_PENDING_URLS lists to reflect Jar and Jutul moving to skipTrue.
LESSONS: Always live-fetch and inspect a calendar feed URL before trusting a registry 'source' value labeled ICAL/iCal-compatible — page URLs (HTML viewers/JS widgets) are easy to mistake for feed URLs; ICalScraper.calendar_id can be either a Google-Calendar-style email ID or a full feed URL, and _feed_url() now branches on http(s):// prefix to handle both.
**Files:** tests/test_club_registry.py (+5/-1), tournament_scheduler/club_registry.py (+38/-10), tournament_scheduler/data_sources/ical_scraper.py (+19/-5)
**Commit:** [pending — fill after commit]
