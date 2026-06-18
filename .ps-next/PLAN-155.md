# Plan: Harness-driven blocked source recovery
**Goal:** Harness-driven blocked source recovery: Stage 2 checkpoint lists blocked sources and sources that returned 0 events. When the harness reads the Stage 2 checkpoint and finds blocked or empty sources, it should attempt recovery using its own web access (tool calls, browser use) before deciding whether to proceed to Stage 3 without that data. Replaces the removed `_extract_events_via_llm` function and the Pi-era ScraperAgent loop — the same capability, owned by the harness instead of the pipeline. No pipeline code change needed; the Stage 2 checkpoint already surfaces the data needed to identify which sources need recovery.
**Created:** 2026-06-18
**Intent:** Restore blocked-source recovery as a harness-level capability so the Claude agent can use its own web access to fill data gaps before the season plan is generated, replacing the Pi-era ScraperAgent loop that was removed from the pipeline.
**Backlog-ref:** 155
**Constraints:** none

## Tasks
- [x] Added a 'Recovery check — blocked and empty sources' section to run.md's Stage 2 instructions, directing the agent to inspect data.blocked and data.sources[*].event_count before proceeding to Stage 3. — 2026-06-18
  - Files: .claude/commands/rvv-miniputt/run.md, .agents/skills/rvv/SKILL.md
  - Approach: Insert a new section in the run.md command instructions that tells the agent, after `rvv-miniputt scrape` completes, to read `.pipeline/stage2_scraping.json` and inspect `blocked_sources` and `sources_with_zero_events` before invoking Stage 3.

- [x] Created recovery_cli.py with _cmd_recovery_targets(), added recovery-targets subparser to args.py, and wired the handler in rvv_cli.py. The command reads .pipeline/stage2_scraping.json and emits a JSON array of {name, url, reason, block_reason, llm_fallback} for each blocked or zero-event (non-skipped) source. — 2026-06-18
  - Files: tournament_scheduler/cli/recovery_cli.py, tournament_scheduler/cli/__init__.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: Add a `rvv-miniputt recovery-targets` subcommand that reads `.pipeline/stage2_scraping.json`, merges `blocked_sources` and `sources_with_zero_events`, calls `_recovery_hint_for_source()` from `scraper_recovery.py` to get the URL per source, and prints a JSON array of `{name, url, reason}` objects the agent can consume.

- [x] Created recovery_injector.py with inject_recovered_events(source_name, events, work_dir) that uses ScrapedDataCache.read()/write() to patch a source entry with recovered events, setting blockedFalse and updating timestamps so subsequent Stage 2 or Stage 3 runs use the injected data. — 2026-06-18
  - Files: tournament_scheduler/pipeline/recovery_injector.py, tournament_scheduler/pipeline/cache_manager.py
  - Approach: Create `recovery_injector.py` with a `inject_recovered_events(source_name, events, work_dir)` function that patches the cache entry for the given source using `ScrapedDataCache` so that a subsequent Stage 2 re-run (or Stage 3 direct invocation) picks up the recovered data without re-scraping.

- [x] Added _cmd_recovery_inject() to recovery_cli.py that reads a JSON event list from stdin and calls inject_recovered_events(). Registered recovery-inject subparser in args.py (--source required, --work-dir optional) and wired handler in rvv_cli.py. — 2026-06-18
  - Files: tournament_scheduler/cli/recovery_cli.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: Expose `recovery_injector.inject_recovered_events()` as a CLI subcommand (`recovery-inject --source NAME`) that reads a JSON event list from stdin, so the harness can pipe WebFetch-extracted events directly into the cache without writing intermediate files.

- [ ] Extend the run command with per-source recovery loop instructions
  - Files: .claude/commands/rvv-miniputt/run.md
  - Approach: For each source returned by `recovery-targets`, the command instructs the agent to use WebFetch (or browser tool) to retrieve the source URL, extract events from the HTML, and pipe them via `recovery-inject --source NAME`; on success, the agent marks the source recovered and continues; on failure, it logs a warning and moves on.

- [ ] Write the proceed/abort decision logic into the run command
  - Files: .claude/commands/rvv-miniputt/run.md
  - Approach: After the recovery loop, the command instructs the agent to call `rvv-miniputt status` (or re-read the checkpoint) to confirm how many sources remain blocked or empty, then decide: if all critical sources are recovered proceed to Stage 3; if some remain blocked but `--allow-missing-sources` is acceptable, proceed with a warning; otherwise abort and report which sources still need manual intervention.

- [ ] Write unit tests for recovery_injector and recovery-targets command
  - Files: tests/test_recovery_injector.py
  - Approach: Add pytest tests that create a minimal fake stage2 checkpoint, call `inject_recovered_events()` with synthetic event dicts, and assert that the cache entry is updated and readable; also test the `recovery-targets` JSON output structure against a fixture checkpoint.

## Notes
- No changes to stage2_scraping.py, stage3_planning.py, or other pipeline Python modules — the feature lives entirely in the harness command and new CLI helpers.
- `scraper_recovery.py` already has `_recovery_hint_for_source()` returning URL and hint per source — use it, do not duplicate.
- `llm_scraper.py` is available as a Python-callable fallback if WebFetch is insufficient for JS-heavy sources (invoke via `rvv-miniputt scrape-llm`).
- `cache_manager.py`'s `ScrapedDataCache` is the canonical write path — do not patch the stage2 checkpoint JSON directly.

## Acceptance Criteria
- [ ] After Stage 2 runs and finds blocked or zero-event sources, the run command output lists those sources by name before Stage 3 begins.
- [ ] The `rvv-miniputt recovery-targets` subcommand returns a JSON array containing one entry per blocked or zero-event source, each with at minimum `name` and `url` fields.
- [ ] The `rvv-miniputt recovery-inject` subcommand writes events to the unified cache and the cache entry is readable by subsequent pipeline stages.
- [ ] When recovery succeeds for all blocked sources, the run command proceeds to Stage 3 automatically without requiring operator confirmation.
- [ ] When one or more sources remain blocked after recovery attempts, the run command reports which sources are unrecovered and does not silently proceed without logging the gap.

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-18 — Added a 'Recovery check — blocked and empty sources' section to run.md's Stage 2 instructions, directing the agent to inspect data.blocked and data.sources[*].event_count before proceeding to Stage 3.
**Rationale:** Straightforward documentation edit; the stage2 checkpoint structure was confirmed from .pipeline/stage2_scraping.json (keys: blocked, sources with event_count/blocked fields).
**Findings:** The stage2 checkpoint stores per-source data under data.sources (each entry has event_count, blocked, block_reason, llm_fallback). The top-level data.blocked list mirrors sources where blockedtrue. Zero-event sources are those with event_count0 and blockedfalse.
LESSONS: none
**Files:** .claude/commands/rvv-miniputt/run.md (+13/-0)
**Commit:** abdde5e (hockey)

### 2026-06-18 — Created recovery_cli.py with _cmd_recovery_targets(), added recovery-targets subparser to args.py, and wired the handler in rvv_cli.py. The command reads .pipeline/stage2_scraping.json and emits a JSON array of {name, url, reason, block_reason, llm_fallback} for each blocked or zero-event (non-skipped) source.
**Rationale:** none
**Findings:** The stage2 checkpoint wraps source data under data.sources (not top-level). Sources with skippedTrue are correctly excluded from recovery targets. Sandefjord currently has event_count0 but skippedTrue so it is not emitted.
LESSONS: none
**Files:** tournament_scheduler/cli/recovery_cli.py (+71), args.py (+11), rvv_cli.py (+3)
**Commit:** a7892d6 (hockey)

### 2026-06-18 — Created recovery_injector.py with inject_recovered_events(source_name, events, work_dir) that uses ScrapedDataCache.read()/write() to patch a source entry with recovered events, setting blockedFalse and updating timestamps so subsequent Stage 2 or Stage 3 runs use the injected data.
**Rationale:** none
**Findings:** ScrapedDataCache stores sources under data['sources'][name] with event_count, blocked, events, scrape_timestamp fields. The injector merges into existing source entry to preserve any extra fields (e.g. url).
LESSONS: none
**Files:** tournament_scheduler/pipeline/recovery_injector.py (+67/-0)
**Commit:** 79265ed (hockey)

### 2026-06-18 — Added _cmd_recovery_inject() to recovery_cli.py that reads a JSON event list from stdin and calls inject_recovered_events(). Registered recovery-inject subparser in args.py (--source required, --work-dir optional) and wired handler in rvv_cli.py.
**Rationale:** none
**Findings:** Command tested: piping a JSON array through stdin produces {injected, source, work_dir} JSON confirmation and exit 0.
LESSONS: none
**Files:** recovery_cli.py (+48/-1), args.py (+16), rvv_cli.py (+2/-1)
**Commit:** [pending — fill after commit]
