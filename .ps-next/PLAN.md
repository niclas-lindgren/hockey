# Plan: BookUp authentication & 100% calendar fidelity
**Goal:** BookUp clubs (Tønsberg, Sandefjord Penguins) can be scraped with authentication via the ScraperAgent, and a new comparison tool audits all 9 club scrapers for fidelity against source calendars.
**Created:** 2026-06-10
**Intent:** Enable scraping of the two BookUp SPA clubs that require login, and build a deterministic comparison tool to catch scraper regressions — ensuring every event visible on the source calendar appears in scraped output.
**Backlog-ref:** 30

## Tasks
- [ ] Pass scraper strategy initial_navigation to the ScraperAgent and execute pre-loop
  - Files: .pi/lib/scraper-agent.ts, .pi/extensions/rvv-miniputt.ts, tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/browser_worker.py
  - Approach: (1) Create a Python CLI entry point in `scraper_strategies.py` that dumps a named strategy as JSON (with initial_navigation steps). (2) In `scraper-agent.ts`, add `initialNavigation` param to the `scrape()` method — the agent executes these steps before starting the LLM agent loop, substituting `$BOOKUP_EMAIL`/`$BOOKUP_PASSWORD` from `process.env`. (3) In `rvv-miniputt.ts`, before creating the ScraperAgent, call the Python JSON dump to get the strategy, extract initial_navigation, and pass it to `agent.scrape()`.

- [ ] Build calendar fidelity comparison tool
  - Files: tournament_scheduler/tools/calendar_compare.py, tournament_scheduler/pipeline/scraper_strategies.py
  - Approach: Create `tournament_scheduler/tools/calendar_compare.py` as a standalone CLI that (a) reads source configs from `input.json` (or Stage 1 checkpoint via `--work-dir`), (b) for each source, runs its deterministic scraper (or ScraperAgent for non-deterministic sources) for a fixed target week (default to a known week, configurable via `--week YYYY-MM-DD`), (c) outputs a structured JSON diff with scraped events per source and fidelity warnings (zero events, date-range anomalies, missing days-of-week patterns), and (d) generates a human-readable summary. Expose as `python3 -m tournament_scheduler.tools.calendar_compare`.

## Notes
- BookUp SPA: The two BookUp clubs (Tønsberg and Sandefjord Penguins) require login. The `scraper_strategies.py` already defines `initial_navigation` steps with env var placeholders. The ScraperAgent must execute these before the LLM loop.
- Env vars: `BOOKUP_EMAIL` and `BOOKUP_PASSWORD` are expected in the process environment when running the ScraperAgent with BookUp clubs.
- Calendar compare: The comparison tool uses the existing Stage 2 scrapers for deterministic sources; BookUp/Jutul/Jar/Holmen (non-deterministic) will need the ScraperAgent, so the compare tool provides a `--use-agent` flag.
- Fidelity warnings include: zero events for a source that historically had bookings, events outside the requested date range, duplicate events, and sources where every day is empty (potential scraper failure).
- The compare tool writes results to `.pipeline/compare/<source>_<week>.json` for archival and trend tracking.

## Acceptance Criteria
- [ ] ScraperAgent's `scrape()` method accepts `initialNavigation` array, executes login steps before the LLM loop, and substitutes `$BOOKUP_EMAIL`/`$BOOKUP_PASSWORD` from process.env
- [ ] `python3 -m tournament_scheduler.pipeline.scraper_strategies --name "Tønsberg"` outputs valid JSON with the full strategy including `initial_navigation`
- [ ] `python3 -m tournament_scheduler.tools.calendar_compare --week 2026-10-05` runs against all 9 sources and produces a fidelity report
- [ ] Calendar compare tool reports fidelity warnings for zero-event sources and date-range anomalies as structured JSON
- [ ] run: python3 -m tournament_scheduler.tools.calendar_compare --week 2026-10-05 2>&1 | head -30 (syntax check)
- [ ] run: python3 -m tournament_scheduler.pipeline.scraper_strategies --name "Tønsberg" 2>&1 | python3 -m json.tool (valid JSON output)

## Log
<!-- pi-next appends entries here after each task -->
