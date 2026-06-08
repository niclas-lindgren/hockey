# PLAN

**Feature:** Season plan Excel export — produce a shareable Excel workbook (one sheet or summary view per club/team) listing the proposed season's tournament dates, participating teams, and matchup pairings, suitable for distribution to clubs and coaches; reuse `tournament_scheduler/excel/` conventions.
**Goal:** Season plan Excel export — produce a shareable Excel workbook (one sheet or summary view per club/team) listing the proposed season's tournament dates, participating teams, and matchup pairings, suitable for distribution to clubs and coaches; reuse `tournament_scheduler/excel/` conventions.
**Backlog-ref:** 5
**Constraints:** none
**Date:** 2026-06-08

## Intent
Clubs and coaches need a club/team-centric view of the season plan (rather than the existing tournament-centric overview) so each club can see at a glance which dates, opponents, and arenas affect its own teams.

## Tasks
- [x] Added _write_club_summary_sheet to SeasonPlanExporter that builds one worksheet per club listing each team's tournament date, opponent(s), host arena, and age group, and wired it into the export flow plus updated the sheet-count test. — 2026-06-08
  - Files: `tournament_scheduler/excel/plan_exporter.py`
  - Approach: Derive the per-club view by iterating `SeasonPlan.tournaments`, grouping `Game.home`/`Game.away` entries by `Team.club`, and rendering one row per (team, tournament-date, opponent, arena) tuple; reuse `_format_date`, `_weekday_name`, `_style_header_row`, and `_autosize_columns` for consistent formatting.

- [ ] Add club-sheet naming/uniqueness handling using existing Excel sheet-title constraints
  - Files: `tournament_scheduler/excel/plan_exporter.py`
  - Approach: Reuse `_unique_sheet_title`/`_sanitize_sheet_title` and `_MAX_SHEET_TITLE_LENGTH` (or extract a shared helper if naming differs for club vs. tournament sheets) so club names that collide or exceed the 31-character Excel limit are sanitized and made unique, mirroring the per-tournament sheet logic.

- [ ] Add a new module-level header/column constant set for the club/team summary view (e.g. `_CLUB_SUMMARY_HEADERS`)
  - Files: `tournament_scheduler/excel/plan_exporter.py`
  - Approach: Define column headers (e.g. Date, Weekday, Team, Age group, Opponent, Arena, Host club) alongside the existing `_OVERVIEW_HEADERS`/`_GAMES_HEADERS` constants, following the same naming and Norwegian-language conventions (`_NORWEGIAN_WEEKDAYS`).

- [ ] Wire the new club/team summary sheets into `SeasonPlanExporter.export()`
  - Files: `tournament_scheduler/excel/plan_exporter.py`
  - Approach: After writing the "Sesongoversikt" overview sheet and per-tournament sheets, iterate `Roster.clubs()` (or the set of clubs derived from `SeasonPlan.tournaments[*].teams`) and call the new club-summary writer for each club, appending sheets to the same workbook returned by `export()`.

- [ ] Add an export option/flag to choose between full workbook and per-club extracts (or confirm a single combined workbook satisfies "shareable per club")
  - Files: `tournament_scheduler/excel/plan_exporter.py`, `tournament_scheduler/cli/season_command.py`
  - Approach: Extend `SeasonPlanExporter.export()` (or add a sibling method, e.g. `export_club_summaries`) with an optional parameter controlling whether club-summary sheets are included, and surface this through the existing `--export-excel` CLI wiring in `season_command.py` (and the interactive-menu yes/no export prompt) so users can opt in without breaking the current default export behavior.

- [ ] Add unit tests covering the per-club/per-team summary sheets
  - Files: `tests/test_plan_exporter.py`
  - Approach: Following the `Test*`/`test_*`/plain-`assert` conventions and `FakeScheduler`/`tmp_path` patterns from prior plan_exporter tests, build a small `SeasonPlan` fixture spanning 2+ clubs and assert the exported workbook contains one sheet per club, with correct rows for each team's date/opponent/arena, sanitized/unique sheet titles, and styled+autosized headers.

- [ ] Update README/CLI help text (if present) to document the new club/team summary export
  - Files: `tournament_scheduler.py` or `tournament_scheduler_interactive.py` (CLI help/menu text), `CLAUDE.md` if export conventions are documented there
  - Approach: Add a brief description of the new per-club summary sheets to the relevant `--help`/menu prompt strings so users know the exported workbook now includes club-level views, matching the existing Norwegian-language CLI conventions.

## Acceptance Criteria
- The SeasonPlanExporter produces a new Excel workbook with one sheet per club when given a season plan, where each sheet contains the tournament dates, opponents, and host arenas for all teams from that club.
- The exported Excel workbook contains a separate worksheet for each unique club in the season plan, with each sheet labeled using the club's name and sanitized to meet Excel sheet title length limits.
- Each team's information is listed in the club-specific worksheet, showing the tournament date, opponent team name, and host arena for every game in that team's schedule.
- The exported workbook includes the correct number of sheets matching the total number of unique clubs in the season plan, with no duplicate or missing sheets.
- The exported Excel file is readable and properly formatted using openpyxl, with headers styled and columns auto-sized to fit content.

## Log
(none yet)

### 2026-06-08 — Added _write_club_summary_sheet to SeasonPlanExporter that builds one worksheet per club listing each team's tournament date, opponent(s), host arena, and age group, and wired it into the export flow plus updated the sheet-count test.
**Rationale:** none
**Findings:** Confirmed via tests: per-club sheets are created with unique titles ('Klubb <name>'), one row per (team, tournament-date, opponent, arena); existing sheet-count test updated to account for the new club sheets; full suite passes (89 passed, 1 skipped).
LESSONS: none
**Files:** tests/test_plan_exporter.py (+5/-1) tournament_scheduler/excel/plan_exporter.py (+77/-1)
**Commit:** [pending — fill after commit]
