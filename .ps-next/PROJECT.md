# Hockey Tournament Scheduler
Finds optimal weekend dates for youth hockey tournaments by scraping multiple club/hall calendars and checking conflicts, for the people organizing Kongsberg's tournament and season schedules. The season-scheduling extension targets all clubs in **Region Viken Vest (RVV, https://www.rvvhockey.no/)**: Ringerike, Tønsberg, Frisk Asker, Sandefjord Penguins, Jar, Holmen, Skien, Jutul and Kongsberg — 9 clubs total.

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

## Season-scheduling extension — expected output
1. **Season overview:** a single schedule listing every proposed tournament across all age groups and genders (boys U7-U12, girls JU10/JU11/...), with its arena/location and date.
2. **Per-tournament schedules:** for each tournament, the list of participating teams plus the actual game schedule within that tournament — every participating team should play every other participating team (round-robin within the tournament). The number of games that run in parallel depends on the age group and must be configurable, e.g. a config like `{U7: {parallelGames: 4}, U10: {parallelGames: 3}}`; other age-group-specific settings may be added to this config later.
3. **Spond export (lower priority — after the above is working):** export the season plan to Spond's Excel-import format for season planning. Build this last, once the season overview and per-tournament schedules are solid.

## Season-scheduling extension — additional requirements
- **Region scope:** All 9 RVV clubs — Ringerike, Tønsberg, Frisk Asker, Sandefjord Penguins, Jar, Holmen, Skien, Jutul, Kongsberg. (Originally scoped to 7 — Tønsberg and Sandefjord Penguins were missing and have been added; Sandefjord already appears as an opponent in the existing Excel schedule `existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx` but has no calendar scraper yet.)
- **Arenas:** Tournaments are hosted at different ice-hockey arenas (one per club roughly). The season plan should include at least one tournament per arena/club.
- **Age groups:** Teams belong to age groups — boys: U7, U8, U9, U10, U11, U12; girls: JU10, JU11, etc. (JU = "jenter"/girls). Age groups with overlapping player pools (e.g. JU11 and U10 may share players) should preferably not have tournaments scheduled on the same weekend, to avoid player double-booking.
- **Club calendar sources:**
  - Kongsberg ice/ball hall — already integrated (Outlook/Playwright) https://kongsberghallen.no/webkalender/ishall/
  - Skien — already integrated (Google Calendar iCal feed) https://skienishockey.no/kalender-isbooking/
  - Jutul (Bærum ishall): https://baerumishall.no/kalender/
  - Jar (Jarhallen, via Forumbooking): https://www.forumbooking.no/schema.aspx?obj=2&schema=Jarhallen%20(ishall)&kalender=true&safarifix=true
  - Ringerike (via Teamup): https://teamup.com/ksr8bg1tpn5s3npskw
  - Holmen — https://kalender.sportello.no/booking/11055
  - Frisk Asker — https://teamup.com/ksdwpwxysmxwnuftoy
  - Tønsberg — https://www.bookup.no/utleie/Index/860#___/view:item/id:860/part:/r:0/mod:book
  - Sandefjord Penguins — https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen___/view:item/id:4497/part:/place:3907:SANDEFJORD/q:sandefjord/r:26/mod:book
