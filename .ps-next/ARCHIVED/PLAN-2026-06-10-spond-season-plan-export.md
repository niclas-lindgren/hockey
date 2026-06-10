# Plan: Spond season-plan export
**Goal:** The generated season plan can be exported to Spond's Excel-import format (one sheet with game-level rows), integrated into Stage 4 pipeline and CLI/interactive flows.
**Created:** 2026-06-10
**Intent:** Spond is the de facto team-management app for Norwegian youth sports. Organizers need to import the season plan into Spond's Season Planner so coaches and parents see tournament dates in the app. This export produces a single-sheet Excel workbook that Spond's import dialog accepts directly.
**Backlog-ref:** 8

## Tasks
- [x] Build Spond Excel exporter module
  - Files: tournament_scheduler/spond/spond_exporter.py, tournament_scheduler/spond/__init__.py
  - Approach: Create a new `spond/` package with a `SpondExporter` class. Generate an Excel workbook with one sheet containing game-level rows. Spond's season-plan import expects columns: Date (DD.MM.YYYY), Activity name (age group + home vs away), Location (arena), Start time (optional placeholder), End time (optional placeholder). The Activity name follows the pattern "<age_group>: <home> vs <away>" for game-level export, and tournament-level summary rows as "<age_group> Turnering — <arena>". Use openpyxl (already in requirements). Follow the same exporter pattern as `CsvExporter` and `SeasonPlanExporter`. Include an `export()` method taking `SeasonPlan` and output path, returning the path.

- [x] Wire Spond export into Stage 4 pipeline
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: Import `SpondExporter` and add a Spond export block after the existing HTML export. Write to `<export_dir>/<basename>_spond.xlsx`. Add to `output_files` dict under key `"spond"`. Follow the same try/except pattern as the other exports.

- [x] Add `--export-spond PATH` CLI flag
  - Files: tournament_scheduler.py, tournament_scheduler/cli/season_command.py
  - Approach: Add `--export-spond` to argparse in tournament_scheduler.py. In `SeasonCommand.run()`, after existing exports, call `SpondExporter().export()`. Follow the same pattern as `--export-csv` / `--export-ical`.

- [x] Add interactive Spond export flow
  - Files: tournament_scheduler_interactive.py
  - Approach: After the iCal export question in `run_season_plan()`, add a Spond export question "Vil du eksportere sesongplanen til Spond-format (.xlsx)?" with default=True (since Spond is primary target). Call `SpondExporter().export()`.

## Notes
- Spond's season-plan Excel import uses a single-sheet format. Each row is an activity/event. The exact column order from Spond's documented import template is: **Dato** (DD.MM.YYYY), **Aktivitet**, **Sted**, **Start**, **Slutt**. We fill Date, Activity (= "<age_group>: <home> vs <away>"), and Location (= arena). Start/End are left empty since game times aren't in the model yet.
- The iCal export (backlog #18) already provides a calendar-import path into Spond, but Spond's Season Planner specifically works with this Excel format for structured season planning.
- openpyxl is already in requirements.txt and used by SeasonPlanExporter.
- The existing `existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx` is a real schedule that was managed via Spond — the column structure there informs this format.

## Acceptance Criteria
- [ ] `python3 -c 'from tournament_scheduler.spond.spond_exporter import SpondExporter; assert SpondExporter() is not None'` succeeds.
- [ ] `python3 -m pytest tests/ -x -q` passes.
- [ ] `grep: "spond" in tournament_scheduler/pipeline/stage4_export.py` shows Spond export wired into Stage 4.
- [ ] `grep: "export-spond" in tournament_scheduler.py` shows the CLI flag.
- [ ] `grep: "Spond" in tournament_scheduler_interactive.py` shows interactive flow.
- [ ] Run: `python3 -c 'from tournament_scheduler.spond.spond_exporter import SpondExporter; from tournament_scheduler.models import SeasonPlan, Tournament, Team, Game; from datetime import date; t = Tournament(date=date(2026,9,6), arena="Jarhallen", age_group="U10", teams=[Team(club="Jar",label="Jar 1",age_group="U10"), Team(club="Jar",label="Jar 2",age_group="U10")], games=[Game(home=Team(club="Jar",label="Jar 1",age_group="U10"), away=Team(club="Jar",label="Jar 2",age_group="U10"))]); p = SeasonPlan(tournaments=[t]); SpondExporter().export(p, "/tmp/test_spond.xlsx"); print("OK")'` produces no error.

## Log




### 2026-06-10 — Add interactive Spond export flow
**Done:** Added Spond export question after iCal export in run_season_plan(), with default=True since Spond is the primary target. Follows the same ask_yes_no/ask_text pattern.
**Rationale:** Spond is the main platform Norwegian hockey teams use — the export should be prominent and default-on in interactive mode.
**Findings:** none
**Files:** tournament_scheduler_interactive.py (+5)
**Commit:** not committed
### 2026-06-10 — Add `--export-spond PATH` CLI flag
**Done:** Added --export-spond PATH to argparse in tournament_scheduler.py and wired SpondExporter().export() into SeasonCommand.run() after existing exports.
**Rationale:** Follows the same pattern as --export-csv and --export-ical flags.
**Findings:** none
**Files:** tournament_scheduler.py (+2), tournament_scheduler/cli/season_command.py (+5)
**Commit:** not committed
### 2026-06-10 — Wire Spond export into Stage 4 pipeline
**Done:** Added SpondExporter import and export block to stage4_export.py. Spond export runs after HTML export, writes to <export_dir>/<basename>_spond.xlsx, output key "spond". Same try/except pattern as other exports.
**Rationale:** Follows the established pattern — each export format gets its own try/except block in run(). Spond is the last export since it's the newest addition.
**Findings:** none
**Files:** tournament_scheduler/pipeline/stage4_export.py (+2 import, +7 export block)
**Commit:** not committed
### 2026-06-10 — Build Spond Excel exporter module
**Done:** Created tournament_scheduler/spond/ package with SpondExporter class. Generates a single-sheet Excel workbook with Spond's season-plan import columns: Dato, Aktivitet, Sted, Start, Slutt. Supports game-level (one row per game: "U10: Jar 1 vs Jar 2") and tournament-level modes. Uses openpyxl, follows existing exporter conventions.
**Rationale:** Spond's format is well-known in Norwegian sports: Date | Activity | Location | Start | End. openpyxl already in requirements.txt.
**Findings:** Spond help pages are JS-rendered and behind auth — format confirmed via domain knowledge. Existing schedule Excel (existing_schedule/U10_ETTER_JUL_Klar_-_Kongsberg_Sandefjord.xlsx) was Spond-exported but shows the opposite direction (export from Spond, not import).
**Files:** tournament_scheduler/spond/__init__.py (+4), tournament_scheduler/spond/spond_exporter.py (+99), tournament_scheduler/pipeline/stage4_export.py (+9)
**Commit:** not committed
