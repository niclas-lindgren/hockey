# Hockey Tournament Scheduler
Finds optimal weekend dates for youth hockey tournaments by scraping multiple club/hall calendars and checking conflicts, for the people organizing Kongsberg's tournament and season schedules.

## Stack
- Language/runtime: Python 3
- Framework: Playwright (calendar scraping/JS rendering), Rich (console UX/output), openpyxl (Excel I/O), icalendar/recurring-ical-events (iCal feeds), holidays (Norwegian public holidays)
- Database: none — file-based (Excel schedules, JSON search history at `~/.hockey_scheduler_history.json`, on-disk calendar cache)

## Conventions
- Norwegian-language interactive CLI (`tournament_scheduler_interactive.py`); English-ish CLI flags for the scriptable entry point (`tournament_scheduler.py` / `tournament-scheduler.sh`)
- Console output goes through Rich (`tournament_scheduler/utils/rich_output.py`) — avoid raw `print` for user-facing output
- Conflict detection is split into composable "checkers" under `tournament_scheduler/conflict_checkers/`, each implementing a shared interface (see `interfaces.py`)
- Calendar scraping is split into per-source modules under `tournament_scheduler/data_sources/` (Outlook/Playwright scraping, Google Calendar, generic iCal); results are cached via `utils/calendar_cache.py`
- Tests live in `tests/` and use pytest (`pytest.ini` at repo root)

## Build & test
- Build: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && playwright install chromium`
- Test: `pytest`

## Meta
- **CLAUDE.md:** CLAUDE.md

## Codebase Notes
- **Entry points:** `tournament_scheduler.py` (CLI flags: `--teams`, `--excel-file`, `--start-date`, `--end-date`, `--reschedule`) and `tournament_scheduler_interactive.py` (guided Norwegian-language flow with search history); `tournament-scheduler.sh` is the launcher wrapper.
- **Core package `tournament_scheduler/`:**
  - `scheduler.py` / `models.py` / `interfaces.py` — orchestration, data models (e.g. tournament/event/timeslot), and shared checker/data-source interfaces
  - `data_sources/` — `calendar_scraper.py` (Outlook/Playwright base scraper with `fetch_events`), `ice_hall_calendar.py`, `ball_hall_calendar.py`, `google_calendar_scraper.py`, `ical_scraper.py` (generic iCal feeds)
  - `conflict_checkers/` — `team_availability_checker.py`, `tournament_checker.py`, `ball_hall_checker.py`, `holiday_checker.py`, `excel_checker.py`, `excel_team_checker.py`, `timeslot_checker.py`
  - `excel/` — `tournament_reader.py` for parsing existing Excel-based tournament schedules
  - `utils/` — `rich_output.py` (Rich console rendering), `calendar_cache.py`, `date_parser.py`, `search_history.py`
- **Currently integrated calendars:** Kongsberg ice hall and ball hall (Outlook/Playwright), Skien ice hall (Google Calendar iCal feed); existing Excel schedule lives at `existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx`
- **Debug helpers:** `debug/debug_calendar.py`, `debug/debug_excel_teams.py`, `debug/debug-calendar.sh`

## Season-scheduling extension — additional requirements
- **Arenas:** Tournaments are hosted at different ice-hockey arenas (one per club roughly). The season plan should include at least one tournament per arena/club.
- **Age groups:** Teams belong to age groups — boys: U7, U8, U9, U10, U11, U12; girls: JU10, JU11, etc. (JU = "jenter"/girls). Age groups with overlapping player pools (e.g. JU11 and U10 may share players) should preferably not have tournaments scheduled on the same weekend, to avoid player double-booking.
- **New club calendar sources (URLs provided by user):**
  - Jutul (Bærum ishall): https://baerumishall.no/kalender/
  - Jar (Jarhallen, via Forumbooking): https://www.forumbooking.no/schema.aspx?obj=2&schema=Jarhallen%20(ishall)&kalender=true&safarifix=true
  - Ringerike (via Teamup): https://teamup.com/ksr8bg1tpn5s3npskw
  - (Holmen and Frisk Asker calendar URLs not yet provided — to be obtained before implementing those scrapers)
