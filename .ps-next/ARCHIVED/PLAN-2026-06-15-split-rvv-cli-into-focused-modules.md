# Plan: Split rvv CLI into focused modules
**Goal:** `rvv_cli.py` is reduced to a thin dispatcher while argument parsing, pipeline orchestration, and reporting live in dedicated modules.
**Created:** 2026-06-15
**Intent:** Make the long RVV CLI easier to read, test, and extend without changing user-facing commands.
**Backlog-ref:** 105

## Tasks
- [x] Extract parser construction and validation into `tournament_scheduler/cli/args.py`
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/args.py
  - Approach: move `_build_parser`, `_validate_args`, and any shared date/argument helpers into the new module; keep parser behavior and flags identical, and have `main()` import the parser/validation helpers.

- [x] Move pipeline command flow into `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: extract `calendars`, `run`, `scrape`, `scrape-llm`, per-run log writing, cache helpers, and any shared pipeline-output logic into a dedicated orchestrator module; keep the CLI output and exit codes unchanged.

- [x] Move log/status rendering into `tournament_scheduler/cli/reporting.py` and trim `rvv_cli.py` to dispatch only
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/reporting.py
  - Approach: extract the log listing/report rendering path into a small reporting helper, wire `main()` to imported command handlers, and verify the remaining top-level CLI file is a thin command router.

## Notes
Recent CLI refactors already exist in `season_command.py`, `update_command.py`, and `review_command.py`; follow that style and avoid changing command semantics. Existing tests import `tournament_scheduler.cli.rvv_cli.main`, so preserve that entry point.

## Acceptance Criteria
- [ ] `rvv_cli.py` delegates parser creation and command handling to the new modules while keeping all existing commands available.
- [ ] Existing CLI-related tests still pass with no changes to their expected behavior.
- [ ] `tournament_scheduler/cli/args.py`, `pipeline_orchestrator.py`, and `reporting.py` exist and contain the extracted responsibilities.

## Log



### 2026-06-15 — Move log/status rendering into `tournament_scheduler/cli/reporting.py` and trim `rvv_cli.py` to dispatch only
**Done:** Moved the `rvv-miniputt logs` rendering logic into `tournament_scheduler/cli/reporting.py` and imported it back into `rvv_cli.py` as a thin handler hook.
**Rationale:** This removes the last large reporting block from the CLI entrypoint and keeps the command output identical while making the dispatcher smaller.
**Findings:** The CLI entry point still imports and runs successfully after the reporting split, and the CLI-focused pytest subset continues to pass. No behavior changes were needed beyond the module boundary.
**Files:** tournament_scheduler/cli/reporting.py (+1 new), tournament_scheduler/cli/rvv_cli.py (-logs block, +import)
**Commit:** not committed
### 2026-06-15 — Move pipeline command flow into `tournament_scheduler/cli/pipeline_orchestrator.py`
**Done:** Moved the RVV pipeline-facing CLI handlers into `tournament_scheduler/cli/pipeline_orchestrator.py` and changed `rvv_cli.py` to import them instead of defining the full run/calendars/scrape logic inline.
**Rationale:** This removes the longest command implementations from the monolithic entrypoint while preserving the existing CLI behavior and exit codes.
**Findings:** The extracted handlers still work as standalone imports, and the existing CLI tests that exercise adjust/review flows still pass after the refactor. The new module owns its own Rich console and cache/log helpers.
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+1 new), tournament_scheduler/cli/rvv_cli.py (-pipeline handlers, +imports)
**Commit:** not committed
### 2026-06-15 — Extract parser construction and validation into `tournament_scheduler/cli/args.py`
**Done:** Moved the full RVV CLI parser builder into `tournament_scheduler/cli/args.py` and had `rvv_cli.py` import it as `_build_parser`.
**Rationale:** This isolates the largest pure-argument-construction block from the dispatcher without changing command semantics or entry points.
**Findings:** The CLI had no separate validation helper to preserve; parser construction was the only shared concern in this task. Importing `tournament_scheduler.cli.rvv_cli.main` still works after the split.
**Files:** tournament_scheduler/cli/args.py (+1 new), tournament_scheduler/cli/rvv_cli.py (-top-level parser block, +import)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
