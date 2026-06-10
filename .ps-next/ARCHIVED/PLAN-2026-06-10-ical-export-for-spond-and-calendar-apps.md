# Plan: iCal export for Spond and calendar apps
**Goal:** The generated season plan can be exported as .ics with per-tournament VEVENTs, filterable by age group, exposed via `--export-ical PATH` CLI flag and interactive flow.
**Created:** 2026-06-10
**Intent:** Tournament organizers can import the season plan into Spond, Google Calendar, and Outlook — one calendar event per tournament (not per game).
**Backlog-ref:** 18

## Tasks
- [x] Add per-tournament summary export to ICalExporter with age-group and club filtering
  - Files: tournament_scheduler/ical/ical_exporter.py
  - Approach: Add a new `export_tournament_summary()` method to `ICalExporter` that creates one VEVENT per tournament (not per game), with DTSTART=tournament date, LOCATION=arena, SUMMARY="<age_group> — <arena>", DESCRIPTION with team list. Add optional `age_group_filter` (str) and `club` (str) parameters. Keep existing per-game export unchanged.

- [x] Add `--export-ical PATH [--ical-age-group GROUP] [--ical-per-club]` CLI flag
  - Files: tournament_scheduler.py, tournament_scheduler/cli/season_command.py
  - Approach: Add `--export-ical` and `--ical-age-group` and `--ical-per-club` to argparse in tournament_scheduler.py. In SeasonCommand.run(), after the existing Excel/CSV exports, add iCal export using the new ICalExporter.export_tournament_summary() method. When --ical-per-club is set, generate one .ics per club.

- [x] Add interactive iCal export flow
  - Files: tournament_scheduler_interactive.py
  - Approach: After the existing "Vil du eksportere til CSV?" question, add an iCal export question "Vil du eksportere sesongplanen til iCal (.ics)?" with optional age-group filter. Call export_tournament_summary().

## Notes
- The existing `ICalExporter` already exports per-game VEVENTs used by the Stage 4 pipeline. This plan adds a complementary per-tournament summary export for the user-facing CLI/interactive flows — it does not modify the existing per-game export.
- The `icalendar` library is already in requirements.txt.
- Per-club .ics files should go in the same directory as the main .ics with names like `club_Jar.ics`, `club_Jutul.ics`.

## Acceptance Criteria
- [ ] Run `python3 -c 'from tournament_scheduler.ical.ical_exporter import ICalExporter; e = ICalExporter(); assert hasattr(e, "export_tournament_summary")'` and confirm no error.
- [ ] `python3 tournament_scheduler.py --generate-season --roster-file <test-file> --export-ical /tmp/test.ics` succeeds (or exits gracefully if scraping unavailable).
- [ ] `pytest` passes.
- [ ] The generated .ics file contains one VEVENT per tournament with valid DTSTART, LOCATION, and SUMMARY fields.
- [ ] When `--ical-age-group U10` is used, only U10 tournaments appear in the .ics.
- [ ] When `--ical-per-club` is used, one .ics per club is generated alongside the main .ics.

## Log



### 2026-06-10 — Add interactive iCal export flow
**Done:** true
**Rationale:** Added iCal export question after CSV in the interactive flow, with optional age-group filter and optional per-club .ics generation.
**Findings:** Follows the same pattern as the existing Excel/CSV export questions. Uses ask_yes_no/ask_text for input consistency.
**Files:** tournament_scheduler_interactive.py (+import Path, +20 lines)
**Commit:** not committed
### 2026-06-10 — Add `--export-ical PATH [--ical-age-group GROUP] [--ical-per-club]` CLI flag
**Done:** true
**Rationale:** Added --export-ical, --ical-age-group, and --ical-per-club flags to argparse. Wired into SeasonCommand.run() alongside existing Excel/CSV exports. When --ical-per-club is set, generates one .ics file per club with club-filtered events.
**Findings:** The --ical-per-club flag generates per-club .ics files in the same directory as the main .ics, named like <stem>_<club>.ics. Each contains only events where that club participates, with "Dine lag:" highlighted in the event description.
**Files:** tournament_scheduler.py (+6 lines), tournament_scheduler/cli/season_command.py (+import Path, +22 lines)
**Commit:** not committed
### 2026-06-10 — Add per-tournament summary export to ICalExporter with age-group and club filtering
**Done:** true
**Rationale:** Added export_tournament_summary() method to ICalExporter that creates one VEVENT per tournament with DTSTART, LOCATION, SUMMARY, DESCRIPTION. Supports age_group_filter and club parameters. Existing per-game export() method is untouched.
**Findings:** The existing ICalExporter already worked well for per-game events. The new per-tournament summary is a separate method so Stage 4 pipeline continues to use the per-game export unchanged.
**Files:** tournament_scheduler/ical/ical_exporter.py (expanded with export_tournament_summary, _build_tournament_summary_calendar, _tournament_summary_event)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
