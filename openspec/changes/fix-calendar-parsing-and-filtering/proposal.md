# Fix Calendar Parsing and Filtering

## Why
The tournament scheduler was incorrectly showing dates as unavailable due to three critical bugs:
1. Calendar event times were showing as 00:00 instead of actual times (e.g., 13:00-15:30 showed as 00:00-02:30)
2. Non-tournament events (like "Åpen ishall" - open ice) were blocking dates instead of being filtered out
3. Time slot availability logic incorrectly required the entire 2.5h tournament to fit within the 11:00-14:00 start window, instead of just requiring the start time to be within that window

These bugs resulted in false negatives - valid tournament dates being marked as unavailable.

## What Changes
- Fix Outlook calendar scraper to apply parsed start times to event datetime objects
- Fix tournament scheduler to use filtered calendar sources instead of bypassing tournament keyword filtering
- Add missing tournament keywords ('ef ', 'ju', 'kamp', age groups) to recognize more tournament events
- Correct time slot availability logic to allow tournaments to extend beyond latest_start time
- Update time slot checker message to clarify that start time must be within window, not entire duration

## Impact
- Affected specs: `calendar-scraping`, `tournament-filtering`, `timeslot-availability` (modifications to existing behavior)
- Affected code:
  - `tournament_scheduler/data_sources/calendar_scraper.py` (time parsing fix)
  - `tournament_scheduler/data_sources/ice_hall_calendar.py` (keyword additions)
  - `tournament_scheduler_interactive.py` (filtering bypass fix)
  - `tournament_scheduler.py` (filtering bypass fix)
  - `tournament_scheduler/conflict_checkers/timeslot_checker.py` (availability logic fix)
- External dependencies: None
- Breaking changes: None (bug fixes restore intended behavior)
