# Plan: Single-club scrape mode
**Goal:** `rvv-miniputt scrape --club "Sandefjord Penguins"` scrapes a single calendar source and displays results — for fast troubleshooting without running the full pipeline.
**Created:** 2026-06-10
**Intent:** Currently the only way to test a single scraper is to run the entire 4-stage pipeline, which takes minutes. A single-club scrape mode saves time when debugging blocked sources like Sandefjord Penguins or testing LLM fallback strategies.
**Backlog-ref:** 39

## Tasks
- [x] Add `scrape` subcommand with --club and --work-dir/--export-dir options
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Add subparser in `_build_parser()`, wire in `main()`. The handler looks up the source config from Stage 1 checkpoint, calls `_scrape_source` (import from stage2_scraping), displays event count, blocked status, and LLM fallback info.
- [x] Handle missing/unknown club names with helpful Norwegian error messages
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: If --club doesn't match any source in the config, list available source names. If no Stage 1 checkpoint exists, tell user to run `rvv-miniputt run` first.

## Notes
- The existing `_scrape_source` function in `stage2_scraping.py` already does single-source scraping — we just need a CLI wrapper.
- Source config lives in `.pipeline/stage1_config.json` under `sources[]` with `name`, `type`, `url` fields.
- The scrape subcommand should accept `--work-dir` (default `.pipeline`) like other subcommands.
- Rich console output: use `_console` for consistent styling.

## Acceptance Criteria
- [x] `rvv-miniputt scrape --club "Sandefjord Penguins"` scrapes only Sandefjord and shows event count + blocked/LLM fallback status
- [x] `rvv-miniputt scrape --club "Unknown Club"` shows a list of available source names
- [x] `rvv-miniputt scrape --help` shows the subcommand with its options
- [x] The scrape subcommand is listed in `rvv-miniputt --help`

## Log


### 2026-06-10 — Handle missing/unknown club names with helpful Norwegian error messages
**Done:** Both error paths verified: missing Stage 1 checkpoint prints Norwegian message to run rvv-miniputt run first; unknown club name prints available sources with types. Already implemented as part of _cmd_scrape.
**Rationale:** Bundled with scrape subcommand — single cohesive handler with both error paths.
**Findings:** Already handled in initial _cmd_scrape implementation.
**Files:** tournament_scheduler/cli/rvv_cli.py (already counted)
**Commit:** not committed
### 2026-06-10 — Add `scrape` subcommand with --club and --work-dir/--export-dir options
**Done:** Added `scrape` subcommand to rvv-miniputt CLI: parses --club name, looks up source from Stage 1 config, calls _scrape_source, displays event count, blocked status, scraper errors, and LLM fallback with navigation steps.
**Rationale:** Reuses existing _scrape_source from stage2_scraping.py. Source lookup by case-insensitive name match against Stage 1 config. Adds no new dependencies.
**Findings:** Unknown club names show a list of available sources with types. iCal sources (Frisk Asker) hit the cache and return immediately. outlook/bookup sources (Sandefjord) return 0 events but flag LLM fallback with navigation steps.
**Files:** tournament_scheduler/cli/rvv_cli.py (+70/-0)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
