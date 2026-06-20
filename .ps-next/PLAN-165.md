# Plan:

**Feature:** Restrict Frisk Asker scraping to Askerhallen only: Frisk Asker has two arenas (Askerhallen and Varner Arena) but Frisk Asker tournaments are only held in Askerhallen. Update the Frisk Asker calendar source config to filter/scrape only Askerhallen bookings so Varner Arena slots do not appear as Frisk Asker availability.
**Goal:** Restrict Frisk Asker scraping to Askerhallen only.
**Backlog-ref:** 165
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Ensure Frisk Asker availability only reflects Askerhallen bookings, preventing Varner Arena slots from incorrectly appearing as Frisk Asker tournament slots.

## Tasks

- [x] Added optional location_filter field to ClubCalendarSource dataclass and set it to 'Askerhallen' for Frisk Asker, also updated the arena field from 'Varner Arena' to 'Askerhallen'. — 2026-06-20
  - Files: `tournament_scheduler/club_registry.py`
  - Approach: Extend the ClubCalendarSource dataclass with a new optional `location_filter: Optional[str] = None` field to allow per-source venue filtering when a club's iCal feed covers multiple arenas.

- [x] Already completed in previous task — Frisk Asker location_filter'Askerhallen' and arena'Askerhallen' set in task 1. — 2026-06-20
  - Files: `tournament_scheduler/club_registry.py`
  - Approach: Set `location_filter="Askerhallen"` on the Frisk Asker ClubCalendarSource entry so only events at Askerhallen are accepted from the Teamup iCal feed.

- [x] Added optional location_filter parameter to scrape_calendar; events whose LOCATION field does not contain the filter string (case-insensitive) are skipped. — 2026-06-20
  - Files: `tournament_scheduler/data_sources/ical_scraper.py`
  - Approach: Add an optional `location_filter: str | None` parameter to `scrape_calendar`; after parsing each event, read the iCal `LOCATION` field and skip any event whose location does not contain the filter string (case-insensitive).

- [x] Added location_filter parameter to _run_ical_scraper; stage2_scraping.py now looks up CLUB_REGISTRY by source name and passes location_filter when calling _run_ical_scraper for iCal sources. — 2026-06-20
  - Files: `tournament_scheduler/pipeline/scraper_ical.py`, `tournament_scheduler/club_registry.py`
  - Approach: Extract the `location_filter` from the resolved ClubCalendarSource entry and pass it as an argument when calling `ICalScraper.scrape_calendar`, so the filter is applied during the scrape phase.

- [ ] Add tests for location filtering in ICalScraper
  - Files: `tests/test_ical_scraper.py`
  - Approach: Add test cases using sample iCal data containing events at both Askerhallen and Varner Arena; verify that when `location_filter="Askerhallen"` is passed, only Askerhallen events are returned and Varner Arena events are excluded.

## Log

- 2026-06-20 Plan created

## Acceptance Criteria

When the ICalScraper processes calendar events for Frisk Asker, it shall filter out events that occur at Varner Arena and only process events at Askerhallen.
The ClubCalendarSource configuration for Frisk Asker shall contain "Askerhallen" as the location_filter field rather than relying solely on the arena field.
When querying the calendar data for Frisk Asker, the system shall not return any events that are scheduled at Varner Arena.
The data_sources/ical_scraper.py module shall produce filtered results that exclude Varner Arena bookings from the Frisk Asker calendar feed.
Running the calendar scraping process for Frisk Asker shall emit only Askerhallen events and not include any Varner Arena bookings in the output.

### 2026-06-20 — Added optional location_filter field to ClubCalendarSource dataclass and set it to 'Askerhallen' for Frisk Asker, also updated the arena field from 'Varner Arena' to 'Askerhallen'.
**Rationale:** none
**Findings:** Field added with case-insensitive substring match doc comment; Frisk Asker arena field updated to Askerhallen.
LESSONS: none
**Files:** tournament_scheduler/club_registry.py (+9/-2)
**Commit:** 7dc5db6 (hockey)

### 2026-06-20 — Already completed in previous task — Frisk Asker location_filter'Askerhallen' and arena'Askerhallen' set in task 1.
**Rationale:** Covered by task 1 which added the field and set the value simultaneously.
**Findings:** Frisk Asker entry verified to have location_filterAskerhallen.
LESSONS: none
**Files:** tournament_scheduler/club_registry.py (no additional changes)
**Commit:** d6d2138 (hockey)

### 2026-06-20 — Added optional location_filter parameter to scrape_calendar; events whose LOCATION field does not contain the filter string (case-insensitive) are skipped.
**Rationale:** none
**Findings:** Filter applied before appending to events list; missing LOCATION treated as empty string so events without location are excluded when filter is active.
LESSONS: none
**Files:** tournament_scheduler/data_sources/ical_scraper.py (+12/-1)
**Commit:** 93c8a3d (hockey)

### 2026-06-20 — Added location_filter parameter to _run_ical_scraper; stage2_scraping.py now looks up CLUB_REGISTRY by source name and passes location_filter when calling _run_ical_scraper for iCal sources.
**Rationale:** Registry lookup uses club_for_source_name then CLUB_REGISTRY direct access; none needed otherwise.
**Findings:** location_filter flows from CLUB_REGISTRY through stage2_scraping -> _run_ical_scraper -> scrape_calendar.
LESSONS: none
**Files:** scraper_ical.py (+8/-2), stage2_scraping.py (+11/-2)
**Commit:** [pending — fill after commit]
