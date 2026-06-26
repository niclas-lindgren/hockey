# Plan: Stage 2 scrape-merge recovery command
**Goal:** Add a CLI command that normalizes a recovered Stage 2 checkpoint from cache and writes the repaired checkpoint back to disk.
**Created:** 2026-06-26
**Intent:** Let the harness fix recovered Stage 2 state through the CLI instead of editing cache/checkpoint files directly.
**Backlog-ref:** 6

## Tasks
- [x] Implement Stage 2 checkpoint normalization from recovered cache entries
  - Files: tournament_scheduler/pipeline/recovery_injector.py, tournament_scheduler/pipeline/scraper_event_helpers.py
  - Approach: add a helper that loads the Stage 2 envelope, merges recovered source events/counts from the unified cache, clears blocked state for recovered sources, rebuilds events_by_club, recomputes the checkpoint date range from event data, and rewrites the checkpoint with an updated status/summary.
- [x] Expose `rvv-miniputt scrape-merge` in the CLI parser and dispatch
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/recovery_cli.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: wire a new subcommand that targets the Stage 2 checkpoint in `--work-dir`, calls the normalization helper, and prints a compact JSON summary of merged/recovered sources and remaining blockers.
- [x] Add regression tests for the recovery merge flow
  - Files: tests/test_recovery_injector.py, docs/rvv-miniputt-pipeline.md
  - Approach: cover the helper directly and through the CLI handler; verify recovered sources are unblocked, event counts/date range are refreshed, and the command documentation mentions the new recovery step.

## Notes
Stage 2 currently writes a checkpoint plus a unified cache; recovery-inject updates the cache only. This task makes the checkpoint self-heal after recovery so Stage 3 can resume without manual file edits.

## Acceptance Criteria
- [ ] `rvv-miniputt scrape-merge --work-dir <dir>` reads an existing Stage 2 checkpoint and rewrites it with recovered source counts and unblocked sources.
- [ ] The rewritten Stage 2 checkpoint shows refreshed `events_by_club`, `blocked`, and scraped date-range fields.
- [ ] Tests pass for the helper and CLI path.

## Log



### 2026-06-26 — Add regression tests for the recovery merge flow
**Done:** Added tests covering the normalization helper and the new CLI path, plus a short pipeline-guide note describing the recovery-inject → scrape-merge workflow.
**Rationale:** We need regression coverage that proves recovered sources are unblocked, counts/date ranges refresh, and the new command is documented.
**Findings:** Used a recovered Kongsberg ishall fixture so the checkpoint rebuild also exercises events_by_club generation; targeted recovery tests pass.
**Files:** tests/test_recovery_injector.py (+118), docs/rvv-miniputt-pipeline.md (+4)
**Commit:** not committed
### 2026-06-26 — Expose `rvv-miniputt scrape-merge` in the CLI parser and dispatch
**Done:** Wired a new `scrape-merge` subcommand through argparse and the main CLI dispatcher, and added a handler that prints a compact JSON normalization summary.
**Rationale:** The harness needs a supported command surface instead of calling recovery helpers or editing files directly.
**Findings:** The new command is thin: it delegates to the normalization helper, returns JSON, and fails cleanly when the Stage 2 checkpoint is missing or invalid.
**Files:** tournament_scheduler/cli/args.py (+11), tournament_scheduler/cli/recovery_cli.py (+22), tournament_scheduler/cli/rvv_cli.py (+4)
**Commit:** not committed
### 2026-06-26 — Implement Stage 2 checkpoint normalization from recovered cache entries
**Done:** Added a Stage 2 normalization helper that reloads recovered cache data into the checkpoint, refreshes per-source counts, clears blocked state for recovered sources, rebuilds events_by_club, and recomputes the checkpoint date range before rewriting the checkpoint.
**Rationale:** The harness needs the checkpoint itself to reflect recovered events so Stage 3 can resume without editing cache files by hand.
**Findings:** Recovered sources are keyed off cache entries with real events; the helper now treats the Stage 2 checkpoint as the source of truth and keeps empty/no-op checkpoints safe to rewrite.
**Files:** tournament_scheduler/pipeline/recovery_injector.py (+94), tournament_scheduler/pipeline/scraper_event_helpers.py (+34)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
