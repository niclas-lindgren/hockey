# Plan: BookUp authentication & 100% calendar fidelity
**Goal:** BookUp clubs (Tønsberg, Sandefjord Penguins) can be scraped with authentication via the ScraperAgent, and a new comparison tool audits all 9 club scrapers for fidelity against source calendars.
**Created:** 2026-06-10
**Intent:** Enable scraping of the two BookUp SPA clubs that require login, and build a deterministic comparison tool to catch scraper regressions — ensuring every event visible on the source calendar appears in scraped output.
**Backlog-ref:** 30

## Tasks
- [x] Pass scraper strategy initial_navigation to the ScraperAgent and execute pre-loop
  - Files: .pi/lib/scraper-agent.ts, .pi/extensions/rvv-miniputt.ts, tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/browser_worker.py
  - Approach: (1) Create a Python CLI entry point in `scraper_strategies.py` that dumps a named strategy as JSON (with initial_navigation steps). (2) In `scraper-agent.ts`, add `initialNavigation` param to the `scrape()` method — the agent executes these steps before starting the LLM agent loop, substituting `$BOOKUP_EMAIL`/`$BOOKUP_PASSWORD` from `process.env`. (3) In `rvv-miniputt.ts`, before creating the ScraperAgent, call the Python JSON dump to get the strategy, extract initial_navigation, and pass it to `agent.scrape()`.

- [x] Build calendar fidelity comparison tool
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


### 2026-06-10 — Build calendar fidelity comparison tool
**Done:** Created tournament_scheduler/tools/calendar_compare.py with full fidelity comparison pipeline: loads sources from input.json or Stage 1 checkpoint, runs deterministic scrapers for each source against a configurable target week, checks for zero events / date-range anomalies / missing weekdays / duplicates, flags non-deterministic BookUp/Forumbooking/Sportello sources as requiring the Pi ScraperAgent, and writes structured JSON reports to .pipeline/compare/.
**Rationale:** The tool reuses the existing stage2_scraping._scrape_source() function for all deterministic sources, keeping scraping logic in one place. Non-deterministic sources get a clear "krever Pi ScraperAgent" warning rather than a zero-event error that would be misleading.
**Findings:** The tool found legitimate fidelity issues: Kongsberg Outlook iframe returns 0 events for far-future months (Oct 2026), Jutul StyledCalendar extracts an entire month instead of just the target week, and the iCal-based sources (Ringerike, Frisk Asker) work well but return slightly out-of-range events due to iCal recurrence expansion.
**Files:** tournament_scheduler/tools/__init__.py (+1), tournament_scheduler/tools/calendar_compare.py (+320), tournament_scheduler/pipeline/scraper_strategies.py (+62, --name/--all CLI)
**Commit:** 7dd2f24
### 2026-06-10 — Pass scraper strategy initial_navigation to the ScraperAgent and execute pre-loop
**Done:** Added strategy JSON CLI to scraper_strategies.py (--name/--all flags), NavigationStep type and initialNavigation support in scraper-agent.ts with env-var substitution, and dynamic strategy fetching in rvv-miniputt.ts that passes initial_navigation to agent.scrape().
**Rationale:** The BrowserWorker already supported `type` and `click` commands, so only three files needed changes: the Python side for JSON export, the TS agent for executing pre-loop steps, and the extension for wiring them together. Env-var substitution uses process.env lookup with regex ${NAME} pattern matching the strategy format.
**Findings:** scraper-agent.ts was untracked (from backlog item 24), so git diff didn't show it. browser_worker.py already supports the `type` command used by initial_navigation — no changes needed there.
**Files:** ts/scraper_strategies.py (+62), .pi/lib/scraper-agent.ts (+48), .pi/extensions/rvv-miniputt.ts (+34/-17)
**Commit:** 4a78467
<!-- pi-next appends entries here after each task -->
