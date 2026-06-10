# Plan: Travel-time-aware game slot ordering
**Goal:** When generating per-tournament game schedules, surface the furthest-traveling team so the host can manually assign them an earlier slot.
**Created:** 2026-06-10
**Intent:** Teams traveling the longest distance to a tournament shouldn't automatically get the last game slot. As a minimum, make the furthest-traveling team visible in the tournament output (Excel, HTML, CSV, console) so the host can manually adjust.
**Backlog-ref:** 15

## Tasks
- [x] Add club-distance data module + furthest-traveling-team helper
  - Files: tournament_scheduler/club_distances.py (new)
  - Approach: Create a static club-to-club distance dict covering all 9 RVV clubs with approximate driving distances (km). Add a `distance(club_a, club_b)` lookup and a `furthest_traveling_team(tournament)` function that returns (team, distance_km) for the participant with the longest estimated travel to the host arena.

- [x] Surface furthest-traveling team in per-tournament Excel sheet
  - Files: tournament_scheduler/excel/plan_exporter.py
  - Approach: In `_write_tournament_sheet()`, after the game schedule header, add a row displaying "Lengst reise: <team> (~<dist> km)" when there are participants. Also add a "Lengste reise" column to the overview sheet with the farthest-traveling team per tournament.

- [x] Surface furthest-traveling team in HTML output
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Compute travel info for each tournament and include it in the JSON data sent to the HTML template. Add a travel-info tag (🚗 <team> ~<dist> km) to each tournament card.

- [x] Surface furthest-traveling team in Rich console output and CSV
  - Files: tournament_scheduler/utils/rich_output.py, tournament_scheduler/csv/csv_exporter.py, tournament_scheduler/cli/season_command.py
  - Approach: In `print_tournament_schedule()`, add a travel-annotation line after the game table. In the Rich diversity summary, add a "lengste reise" section. Add a `furthest_travel` column to the CSV overview.

## Notes
- Distances are approximate driving estimates between RVV club arenas (e.g. Kongsberghallen → Jarhallen ~80 km). These are static geographic values — no routing API needed.
- The distance lookup is a simple dict lookup, not computed dynamically. Missing club pairs default to 0 km (treated as host/unknown).
- Longer-term goal (not in scope): accept optional travel-time data per club from roster config and use it when actually ordering game slots. This task only surfaces the information.

## Acceptance Criteria
- [ ] Run `python3 -c 'from tournament_scheduler.club_distances import distance, furthest_traveling_team; assert callable(distance); assert callable(furthest_traveling_team)'` and confirm no error.
- [ ] Run `pytest` and confirm all existing tests still pass.
- [ ] Run `python3 -c 'from tournament_scheduler.models import Tournament; from tournament_scheduler.club_distances import furthest_traveling_team; t = Tournament(date=None, arena="Kongsberghallen", age_group="U10"); assert furthest_traveling_team(t) is None'` and confirm empty tournament returns None.
- [ ] Run `python3 -c 'from tournament_scheduler.club_distances import distance; assert distance("Kongsberg", "Jar") > 50'` and confirm distance lookup returns a reasonable value.
- [ ] Run `python3 -c 'from tournament_scheduler.club_distances import furthest_traveling_team; from tournament_scheduler.models import Team, Tournament; t = Tournament(date=None, arena="Kongsberghallen", age_group="U10", teams=[Team(club="Jar", label="Jar 1", age_group="U10"), Team(club="Kongsberg", label="Kongsberg U10", age_group="U10")]); result = furthest_traveling_team(t); assert result is not None and result[0].label == "Jar 1"'` and confirm furthest-traveling logic picks the team farthest from the host.

## Log




### 2026-06-10 — Surface furthest-traveling team in Rich console output and CSV
**Done:** true
**Rationale:** Added travel info to print_tournament_schedule (per-tournament line), print_diversity_summary (longest single-leg trip), CSV overview (furthest_travel column), and CLI _print_travel_warnings.
**Findings:** All 3 output formats now surface travel-distance info. The Rich console shows it inline per tournament and in the summary panel. CSV overview has a new column. CLI surfaces the longest trip season-wide.
**Files:** tournament_scheduler/utils/rich_output.py (+import, +travel line in print_tournament_schedule, +travel summary in print_diversity_summary), tournament_scheduler/csv/csv_exporter.py (+import, +overview column), tournament_scheduler/cli/season_command.py (+import, +_print_travel_warnings)
**Commit:** not committed
### 2026-06-10 — Surface furthest-traveling team in HTML output
**Done:** true
**Rationale:** Added travel info to the tournament JSON data (tr field) and a tag--travel CSS class with a travel-distance tag shown in each tournament card when travel data is available.
**Findings:** The HTML template is a large string constant, so changes had to be made carefully with exact whitespace matching. Added both the CSS class and the rendering logic in the render() function.
**Files:** tournament_scheduler/html/html_exporter.py (+import, +_plan_to_json travel field, +CSS class, +template tag)
**Commit:** not committed
### 2026-06-10 — Surface furthest-traveling team in per-tournament Excel sheet
**Done:** true
**Rationale:** Added a "Lengste reise" column to the season-overview sheet and a travel-info row to each per-tournament sheet showing the farthest-traveling team and distance. Uses an internal _travel_info() helper that calls furthest_traveling_team().
**Findings:** openpyxl stores empty-string values as None on read-back, so tests check for None or a valid string. Existing test needed header update. All 189 existing tests unaffected.
**Files:** tournament_scheduler/excel/plan_exporter.py (+import, +_travel_info, +overview column, +tournament sheet row), tests/test_plan_exporter.py (+updated header assertion)
**Commit:** not committed
### 2026-06-10 — Add club-distance data module + furthest-traveling-team helper
**Done:** true
**Rationale:** Created tournament_scheduler/club_distances.py with a static distance matrix for all 9 RVV clubs, arena-to-club reverse mapping, distance() lookup, and furthest_traveling_team() helper. All tests pass.
**Findings:** Distance matrix keys must be stored in alphabetical order to match the _normalise_key helper. Added comprehensive tests covering symmetric lookups, unknown clubs, empty tournaments, host-vs-visitor distinction, and arena fallback logic.
**Files:** tournament_scheduler/club_distances.py (+new 28 loc), tests/test_club_distances.py (+new 104 loc)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
