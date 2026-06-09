# Plan: Pi-driven browser agent for 7 remaining RVV club calendars

**Backlog:** #9
**Goal:** Integrate calendar scraping for all 9 RVV clubs, with cached scraped data and a self-contained HTML calendar viewer for manual verification.

## Architecture

Pi's model drives browser intelligence; Python just executes Playwright commands:

```
┌─ Pi extension ─────────────────────────────────────────┐
│  ScraperAgent (TypeScript)                              │
│    Uses ctx.model → analyzes page HTML → decides action │
│    Sends commands to browserWorker                      │
└──────────────────────┬──────────────────────────────────┘
          stdin/stdout JSON-LD
┌─ Python browserWorker ─────────────────────────────────┐
│  Headless Chromium                                      │
│  Commands: goto, click, extract, screenshot, exit        │
│  Returns: HTML, events, iframe content                   │
└─────────────────────────────────────────────────────────┘
```

All scraped data is cached with timestamps and merged into a unified HTML calendar viewer with club filters and source links.

## Tasks

- [x] Task 1: Build Python browserWorker (Playwright command server)
  - Files: `tournament_scheduler/pipeline/browser_worker.py`
  - Approach: Long-lived process reading JSON commands from stdin, executing on Playwright page, returning JSON on stdout. Supports goto, click, extract (outlook+date_param strategies), screenshot, exit. Handles iframes. SIGTERM cleanup.
  - Lesson: Worker needs explicit iframe targeting for Outlook calendars.

- [x] Task 2: Build TypeScript ScraperAgent in the extension
  - Files: `.pi/extensions/scraper-agent.ts`
  - Approach: Module that launches browserWorker as child process, sends commands, reads responses. Uses Pi's model via HTTP to analyze page snapshots and decide next action. System prompts per calendar type.
  - Lesson: ctx.model.baseUrl + ctx.modelRegistry.getApiKeyForProvider for model access.

- [x] Task 3: Create per-club scraper strategies
  - Files: `tournament_scheduler/pipeline/scraper_strategies.py`
  - Approach: ScraperStrategy dataclass + CalendarEngine enum per club. 6 clubs work deterministically (Kongsberg, Skien, Ringerike, Frisk Asker iCal, Jar iframe, Holmen iframe). 3 need ScraperAgent (Jutul, Tønsberg, Sandefjord).
  - Lesson: Frisk Asker iCal feed confirmed working at ics.teamup.com/feed/ksdwpwxysmxwnuftoy/0.ics

- [x] Task 4: Wire scrapers into pipeline with all 9 clubs in input.json
  - Files: `input.json`
  - Approach: input.json already updated with all 9 clubs. Stage 2 deterministic scraper handles 6 clubs. Remaining 3 use ScraperAgent via extension.
  - Lesson: TBD

- [x] Task 5: Build pipeline cache manager with timestamp+refresh
  - Files: `tournament_scheduler/pipeline/cache_manager.py`
  - Approach: ScrapedDataCache stores all scraped events per source in `.pipeline/cache/scraped_data.json`. Each entry: source name, URL, scrape timestamp (ISO), TTL, event count, events list. Support force-refresh flag. Existing CalendarCache handles per-source caching; this adds unified aggregation.
  - Lesson: TBD

- [ ] Task 6: Build HTML calendar viewer with club filters and source links
  - Files: `tournament_scheduler/pipeline/calendar_viewer.py`
  - Approach: Generate a self-contained HTML file from unified cache. Month-grid calendar with color-coded events per club. Club filter checkboxes. Each event links to source calendar URL. Shows scrape timestamp and age. Export to `.pipeline/calendars.html`.
  - Lesson: TBD

- [ ] Task 7: Add /rvv-miniputt calendars command
  - Files: `.pi/extensions/rvv-miniputt.ts`
  - Approach: New command that regenerates calendar HTML from cache and opens/informs. Accept --refresh to force re-scrape, --output for custom path.
  - Lesson: TBD

- [ ] Task 8: Register clubs in club_registry.py
  - Files: `tournament_scheduler/club_registry.py`
  - Approach: Club registry already has entries for all 9 clubs. Update Tønsberg/Sandefjord with correct Bookup URLs, verify Holmen/Jutul entries.
  - Lesson: TBD

## Acceptance Criteria

- [ ] browser_worker.py accepts stdin JSON commands and returns stdout JSON responses
- [ ] Extension launches worker, sends commands, and reads responses
- [ ] Pi's model reads page snapshot and returns valid next action
- [ ] Write scraper strategy entries for all calendar system types
- [ ] Run pipeline and confirm at least 6 of 9 clubs produce events
- [ ] Write scraped data with timestamps into `.pipeline/cache/scraped_data.json`
- [ ] Produce `.pipeline/calendars.html` with month-grid, club filters, source links
- [ ] Create `/rvv-miniputt calendars` command that shows viewer path
- [ ] Write all 9 club entries in `club_registry.py`
- [ ] Run `pytest` and confirm all existing tests pass

## Log



### 2026-06-09 — Task 5: Build pipeline cache manager with timestamp+refresh
**Done:** yes
**Rationale:** ScrapedDataCache reads from Stage 2 checkpoint, merges into unified .pipeline/cache/scraped_data.json with per-source timestamps, TTL, and event lists. Supports stale detection and force-refresh.
**Findings:** Cache stores per-source events with timestamps. Merges new scrape data with existing cached data (preserves old data when new scrape yields 0 events). Supports force-refresh by backdating timestamps.
**Files:** tournament_scheduler/pipeline/cache_manager.py (+158)
**Commit:** not committed
### 2026-06-09 — Task 4: Wire scrapers into pipeline with all 9 clubs in input.json
**Done:** yes
**Rationale:** input.json updated with all 9 clubs. Stage 2 handles 6 deterministically. Extension ScraperAgent handles the remaining 3.
**Findings:** 6 of 9 clubs produce data deterministically. 3 (Jutul, Tønsberg, Sandefjord) need the ScraperAgent.
**Files:** input.json (+9 clubs)
**Commit:** not committed
### 2026-06-09 — Task 3: Create per-club scraper strategies
**Done:** yes
**Files:** tournament_scheduler/pipeline/scraper_strategies.py (+128)

### 2026-06-09 — Task 2: Build TypeScript ScraperAgent in the extension
**Done:** yes
**Files:** .pi/extensions/scraper-agent.ts (+314)

### 2026-06-09 — Task 1: Build Python browserWorker
**Done:** yes
**Files:** tournament_scheduler/pipeline/browser_worker.py (+381)
