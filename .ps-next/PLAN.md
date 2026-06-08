# Plan: Full-season tournament schedule generator across seven clubs
**Goal:** Given a roster config and season window, the tool scrapes all club calendars (existing + new), checks conflicts, and outputs a proposed set of 10-15 tournament dates with assigned matchups, optimizing for matchup diversity and even time spread, viewable in console and exportable to Excel.
**Created:** 2026-06-08
**Intent:** Replace ad-hoc per-tournament date hunting with a single end-to-end planner that can produce a whole season's worth of tournament proposals across all seven partner clubs at once.
**Backlog-ref:** 1

## Tasks
- [ ] Add a central club/calendar-source registry covering all seven clubs
  - Files: tournament_scheduler/club_registry.py (new), tournament_scheduler/data_sources/ice_hall_calendar.py, tournament_scheduler/data_sources/ical_scraper.py, tournament_scheduler/data_sources/google_calendar_scraper.py
  - Approach: Create a `club_registry.py` module that maps each club name (Holmen, Jutul, Jar, Ringerike, Frisk Asker, Kongsberg, Skien) to the right `CalendarDataSource` construction (URL + `CalendarScraper` for Outlook-based halls following the `IceHallCalendar("https://kongsberghallen.no/webkalender/ishall/", scraper)` pattern at tournament_scheduler.py:663-664, or `calendar_id` for `ICalScraper` following the Skien pattern in ical_scraper.py); replace the inline hardcoded URL construction currently duplicated in tournament_scheduler.py (~line 661-664) with a lookup through this registry so new clubs only need a registry entry. Each registry entry also records the club's home arena name (e.g. "Jarhallen", "Bærum ishall") so the planner can verify arena coverage. Known new-club calendar URLs: Jutul → https://baerumishall.no/kalender/ ; Jar → https://www.forumbooking.no/schema.aspx?obj=2&schema=Jarhallen%20(ishall)&kalender=true&safarifix=true ; Ringerike → https://teamup.com/ksr8bg1tpn5s3npskw . Holmen and Frisk Asker URLs are not yet known — add registry entries with TODO placeholders/skip flags so the rest of the pipeline still works for the five clubs with known sources, and document that those two need URLs before they can be scraped live.

- [ ] Add Roster, Matchup, and SeasonPlan data models
  - Files: tournament_scheduler/models.py
  - Approach: Extend models.py alongside the existing `CalendarEvent`/`TournamentInfo`/`SchedulingResult` dataclasses with `Team` (club name + team label, e.g. "Jar 1", + `age_group` field, e.g. "U10", "JU11"), `Roster` (ordered list of Teams), `Matchup` (pair of Teams + proposed date + `arena`/host club), and `SeasonPlan` (ordered list of Matchups + metadata such as date range, diversity score, and per-arena tournament counts) so planning logic and output/export code share one data shape. Also add an `AGE_GROUP_OVERLAP` mapping (or similar small lookup) capturing which age groups draw from overlapping player pools (e.g. boys U10 ↔ girls JU11, U11 ↔ JU12, etc. — adjacent boys/girls age groups one tier apart) so the planner can check for same-weekend collisions between them.

- [ ] Implement the season planning/optimization engine
  - Files: tournament_scheduler/season_planner.py (new), tournament_scheduler/scheduler.py
  - Approach: Add a `SeasonPlanner` that wraps `TournamentScheduler.find_available_dates` (scheduler.py:36-100) to get the set of conflict-free weekend dates for the season window, then runs a greedy assignment algorithm that:
    1. Picks 10-15 of those dates spread evenly across the window (e.g. bucket the date range into N roughly-equal slices and pick the best free date per slice);
    2. Assigns each date to a host arena/club, ensuring every arena in the roster gets at least one hosted tournament before any arena hosts a second (round-robin over arenas, falling back to least-recently-hosted when more dates than arenas);
    3. Assigns matchups per date using a round-robin / least-recently-played heuristic so each team accumulates a varied set of opponents over the season;
    4. Checks proposed dates against the `AGE_GROUP_OVERLAP` mapping from the models task and avoids — where a free alternative date exists — scheduling overlapping age groups (e.g. JU11 and U10) on the same weekend, to reduce double-booking of shared players; where no alternative exists, flags the collision in the plan's metadata so it surfaces in console/Excel output.
    Return a `SeasonPlan`.

- [ ] Build an Excel exporter for season plans
  - Files: tournament_scheduler/excel/plan_exporter.py (new), tournament_scheduler/excel/tournament_reader.py
  - Approach: Add a `SeasonPlanExporter` (sibling to the read-only `ExcelTournamentReader` in tournament_scheduler/excel/tournament_reader.py, which currently only loads workbooks via `openpyxl.load_workbook(data_only=True)`) that uses `openpyxl.Workbook()` to write one row per proposed tournament date with columns for date, weekday, home/away matchups, and venue/club, and saves to a user-specified `.xlsx` path.

- [ ] Add console rendering for season plans and matchup-diversity metrics to TournamentOutput
  - Files: tournament_scheduler/utils/rich_output.py
  - Approach: Add `print_season_plan(plan: SeasonPlan)` and `print_diversity_summary(plan: SeasonPlan)` methods to the existing `TournamentOutput` class (utils/rich_output.py) following the Rich `Table`-based rendering style of `print_conflict_table`/`print_available_dates`, showing each proposed date with its matchups and a per-team opponent-variety breakdown so the plan is reviewable before export.

- [ ] Wire a `--generate-season` flow into the scriptable CLI
  - Files: tournament_scheduler.py
  - Approach: Add new argparse flags (`--generate-season`, `--roster-file` or `--clubs`/`--teams` pairs, `--season-start`/`--season-end`, `--export-excel`) to tournament_scheduler.py, build the calendar sources for the configured clubs via the new club_registry, run all existing checkers plus `SeasonPlanner`, render with `TournamentOutput.print_season_plan`, and call `SeasonPlanExporter` when `--export-excel` is given — following the existing inline wiring pattern seen at tournament_scheduler.py:632-696.

- [ ] Add a guided "generate full season schedule" flow to the interactive CLI
  - Files: tournament_scheduler_interactive.py
  - Approach: Add a new main-menu option (alongside "Omplassere en eksisterende turnering" / "Finn ledige datoer for en ny turnering") that prompts in Norwegian for club/team roster entries (e.g. "Jar 1, Jar 2"), season start/end dates (defaulting to Oct-Apr), runs the new season-planning flow end-to-end via `SeasonPlanner`, renders results with `TournamentOutput.print_season_plan`, and offers to export to Excel via `SeasonPlanExporter`, reusing the existing search-history persistence pattern.

- [ ] Add tests for the season planner, club registry, and Excel export
  - Files: tests/test_season_planner.py (new), tests/test_club_registry.py (new), tests/test_plan_exporter.py (new)
  - Approach: Following the pytest conventions in tests/ (pytest.ini at repo root), write unit tests that feed `SeasonPlanner` a fixed set of teams (spanning multiple age groups, e.g. U10/U11/JU11, and multiple arenas) and a small fake set of available dates and assert it returns 10-15 matchups spread across the window with: no team facing the same opponent disproportionately more than others, every arena hosting at least one tournament, and no avoidable same-weekend collision between overlapping age groups (per `AGE_GROUP_OVERLAP`) when a free alternative date exists; assert the club registry returns a `CalendarDataSource` for each of the seven club names (and a usable placeholder/skip behavior for Holmen/Frisk Asker pending their URLs); and assert `SeasonPlanExporter` writes a readable `.xlsx` file whose rows match the `SeasonPlan` matchups, including arena and age-group columns (round-trip through `openpyxl.load_workbook`).

## Notes
- Build on the existing `fetch_events`/`CalendarCache`/conflict-checker infrastructure — do not rewrite `TournamentScheduler.find_available_dates`; wrap it.
- All console output must go through `TournamentOutput` (Rich) per project convention — avoid raw `print`.
- Club URLs/calendar IDs are currently hardcoded inline in tournament_scheduler.py; the new club registry should become the single source of truth so the five new clubs (Holmen, Jutul, Jar, Ringerike, Frisk Asker) plug in the same way Kongsberg/Skien do today.
- Use best judgment between a simple greedy/round-robin diversity heuristic and a more sophisticated optimization — a greedy least-recently-played assignment is sufficient to satisfy the goal without a large rewrite.
- Tournaments rotate across arenas (one per club) — every arena should host at least one tournament across the season. Teams belong to age groups (boys: U7-U12; girls: JU10/JU11/...). Age groups whose player pools overlap (e.g. JU11 and U10) should preferably avoid sharing a tournament weekend — treat this as a soft constraint the planner optimizes for and reports on, not a hard failure.
- Calendar URLs for Jutul, Jar, and Ringerike were provided directly by the user (see club registry task and PROJECT.md "Season-scheduling extension" section); Holmen and Frisk Asker URLs are still missing.
- No RESEARCH.md or HISTORY.md existed at plan time; findings above come from direct codebase inspection (scheduler.py, interfaces.py, data_sources/, conflict_checkers/, excel/tournament_reader.py, utils/rich_output.py, utils/calendar_cache.py, tournament_scheduler.py, tournament_scheduler_interactive.py).

## Acceptance Criteria
- [ ] Running the season-generation flow with a roster config (e.g. Jar 1, Jar 2, plus teams from the other six clubs) and an Oct-Apr window outputs a Rich console table listing 10-15 proposed weekend tournament dates with assigned matchups.
- [ ] The proposed plan has no team facing the same opponent more than the others by a wide margin — i.e. the diversity summary shows each team's opponent list contains a varied mix rather than repeats of one or two clubs.
- [ ] `SeasonPlan` metadata reports a per-arena tournament count that is ≥ 1 for every arena/club in the roster, and the diversity summary prints any unavoidable same-weekend collisions between overlapping age groups (e.g. JU11 vs U10) so the organizer can review them.
- [ ] Passing `--export-excel <path>` (or the interactive equivalent) writes an `.xlsx` file that, when read back with openpyxl, contains one row per proposed tournament date matching the console-reported matchups.
- [ ] The club registry returns a working `CalendarDataSource` for each of the seven clubs (Holmen, Jutul, Jar, Ringerike, Frisk Asker, Kongsberg, Skien), and `pytest tests/test_club_registry.py` passes.
- [ ] `pytest tests/test_season_planner.py tests/test_plan_exporter.py` exits with code 0, confirming the planner produces 10-15 evenly-spread matchup dates and the exporter round-trips data through Excel correctly.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->
