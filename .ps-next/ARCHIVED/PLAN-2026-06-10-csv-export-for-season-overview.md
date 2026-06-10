# Plan: CSV export for season overview

**Goal:** Expose the existing CSV exporter via `--export-csv PATH` CLI flag and interactive flow.
**Created:** 2026-06-10
**Intent:** Provide a lightweight CSV export format for clubs without Excel, easy to paste into Google Sheets.
**Backlog-ref:** 20

## Tasks

- [x] Task 1: Add `--export-csv` CLI flag to tournament_scheduler.py arg parser
  - Files: `tournament_scheduler.py`
  - Approach: Add a `--export-csv` argparse argument that takes a file path, like the existing `--export-excel` flag. Keep the same pattern.

- [x] Task 2: Wire `--export-csv` into SeasonCommand.run()
  - Files: `tournament_scheduler/cli/season_command.py`
  - Approach: After the existing `--export-excel` block, add a parallel `if args.export_csv:` block that imports CsvExporter and calls `.export(plan, args.export_csv)`. The overview CSV (with `_overview` suffix) will be written alongside.

- [x] Task 3: Add CSV export option to the interactive flow
  - Files: `tournament_scheduler_interactive.py`
  - Approach: After the Excel export prompt in `run_season_plan()`, add a similar prompt asking if the user wants CSV export, calling CsvExporter.export().

- [x] Task 4: Run tests and verify
  - Files: `tests/`, `export/`
  - Approach: Run `pytest` to confirm nothing breaks. Optionally do a manual `--generate-season --export-csv test.csv` dry run to verify output.

## Notes
- The `CsvExporter` class already exists at `tournament_scheduler/csv/csv_exporter.py` and is used by Stage 4 in the pipeline.
- It writes two files: `<path>.csv` (flat game rows) and `<path_stem>_overview.csv` (one row per tournament).
- The overview CSV already matches the Sesongoversikt Excel sheet structure: date, arena, age_group, host_club, team_count, game_count.
- No new CSV logic needed — just wiring and CLI exposure.

## Log




### 2026-06-09 — Task 4: Run tests and verify
**Done:** yes
**Rationale:** All 177 pytest tests pass (177 passed, 1 skipped). Syntax check passed on all changed files. No regressions.
**Findings:** 177 passed, 1 skipped, 0 failures. No new dependencies or imports broken.
**Files:** tests/ (pytest all pass)
**Commit:** not committed
### 2026-06-09 — Task 3: Add CSV export option to the interactive flow
**Done:** yes
**Rationale:** Added CSV export prompt after Excel export in run_season_plan(). Asks user, imports CsvExporter, calls .export(), reports success.
**Findings:** CsvExporter imported inline to avoid circular import issues. Default CSV filename is sesongplan.csv.
**Files:** tournament_scheduler_interactive.py (+7 lines)
**Commit:** not committed
### 2026-06-09 — Task 2: Wire `--export-csv` into SeasonCommand.run()
**Done:** yes
**Rationale:** Added if args.export_csv block that imports CsvExporter and calls .export(plan, args.export_csv) with success output via TournamentOutput.
**Findings:** CsvExporter.export() returns (games_path, overview_path) tuple. No issues.
**Files:** tournament_scheduler/cli/season_command.py (+6 lines)
**Commit:** not committed
### 2026-06-09 — Task 1: Add `--export-csv` CLI flag to tournament_scheduler.py arg parser
**Done:** yes
**Rationale:** Added --export-csv argument to argparse parser, following the same pattern as --export-excel.
**Findings:** Pattern is identical to existing --export-excel flag. No new dependencies needed.
**Files:** tournament_scheduler.py (+2 lines)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->

## Acceptance Criteria
- [ ] `--export-csv PATH` flag is recognized by `tournament_scheduler.py --help`
- [ ] Running `--generate-season --export-csv test.csv` writes both `test.csv` and `test_overview.csv` with correct headers
- [ ] Interactive flow shows CSV export prompt after generating a season plan
- [ ] `pytest` passes with no regressions
