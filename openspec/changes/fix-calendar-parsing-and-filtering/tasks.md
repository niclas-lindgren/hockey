# Implementation Tasks

## 1. Fix Calendar Event Time Parsing
- [x] Modify `OutlookCalendarScraper._parse_outlook_calendar()` to apply parsed `start_time` to datetime objects
- [x] Add logic to convert fractional hours to hour/minute components
- [x] Update datetime object with actual event start time instead of leaving at 00:00
- [x] Validate fix with `debug-calendar.sh` for sample dates (2026-02-07, 2026-02-08)

## 2. Fix Tournament Filtering Bypass
- [x] Update `tournament_scheduler_interactive.py` line 255-256 to call `kongsberg_ice.fetch_events()` instead of `outlook_scraper.scrape_calendar()`
- [x] Update `tournament_scheduler_interactive.py` line 276-277 to call `skien_ice.fetch_events()` instead of `skien_scraper.scrape_calendar()`
- [x] Update `tournament_scheduler.py` line 668 to call `ice_hall.fetch_events()` instead of `scraper.scrape_calendar()`
- [x] Fix variable reference in print statement (line 675) from `all_ice_hall_events` to `ice_hall_events`
- [x] Validate that non-tournament events are properly filtered out

## 3. Expand Tournament Keywords
- [x] Add 'ef ' to tournament_keywords to catch events like "EF søndag"
- [x] Add 'ju' to catch junior events like "JU14"
- [x] Add 'kamp' to catch match events
- [x] Add age group identifiers (u8-u18) to catch team-specific events
- [x] Validate that "EF søndag" and similar events are now recognized as tournaments

## 4. Fix Time Slot Availability Logic
- [x] Update gap checking logic to calculate `earliest_possible_start` and `latest_possible_start` based on gap boundaries
- [x] Fix "after last event" logic to only check if start time is within allowed window
- [x] Remove incorrect requirement that entire duration fits within start window
- [x] Update checker message from "need 2.5h between 11:00-14:00" to "need 2.5h, starting between 11:00-14:00"
- [x] Validate that dates with late-ending slots (e.g., 13:30-16:00) are now marked as available

## 5. Validation
- [x] Test Feb 8, 2026: Should show as available with slot 13:00-15:30 (after "EF søndag" ends at 13:00)
- [x] Test Feb 7, 2026: Should show correct event times (09:30, 11:00, 13:00) instead of 00:00
- [x] Test that "Åpen ishall" events are filtered out and don't block availability
- [x] Test that tournaments can extend past 14:00 as long as they start by 14:00
