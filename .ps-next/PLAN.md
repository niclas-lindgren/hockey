# Plan: ScraperAgent for blocked clubs (Jutul, Tønsberg, Sandefjord)

**Backlog:** #24
**Goal:** Use the Pi-driven ScraperAgent to scrape the 3 remaining clubs that the deterministic Stage 2 cannot handle — Jutul (StyledCalendar JS widget), Tønsberg (Bookup SPA), and Sandefjord Penguins (Bookup SPA).

## Architecture

The extension's pipeline runner (`rvv-miniputt.ts`) orchestrates everything:

```
Stage 2 (Python, deterministic)
  → yields 6 clubs with events, 3 blocked
  ↓
Extension checks blocked sources
  ↓
For each blocked source:
  ScraperAgent (TypeScript) launches browserWorker
  → Pi's model reads page → decides actions → extracts events
  ↓
Merge results into cache + regenerate viewer
```

The ScraperAgent and browserWorker already exist. This plan integrates them into the pipeline flow and handles the navigation of each specific site.

## Tasks

- [ ] Task 1: Add ScraperAgent integration to rvv-miniputt.ts pipeline runner
  - Files: `.pi/extensions/rvv-miniputt.ts`
  - Approach: After Stage 2 completes, check for blocked sources. For each blocked source that has a strategy in scraper_strategies.py, launch ScraperAgent → browserWorker. Send the scraped results to the cache manager. Merge with existing stage 2 data. Regenerate the viewer.
  - Lesson: TBD

- [ ] Task 2: Scrape Jutul (Bærum ishall, StyledCalendar)
  - Files: `.pi/lib/scraper-agent.ts`
  - Approach: Open https://baerumishall.no/kalender/. The page has a StyledCalendar JS widget — Pi's model needs to find the month navigation (forward/back buttons) and extract events from the rendered calendar grid. Navigate through each month Sep 2026 — Apr 2027.
  - Lesson: TBD

- [ ] Task 3: Scrape Tønsberg (Bookup SPA)
  - Files: `.pi/lib/scraper-agent.ts`
  - Approach: Open https://www.bookup.no/utleie/Index/860. Bookup is a JS SPA with date-picker navigation and a booking grid. Pi's model needs to interact with the date picker to navigate months and extract booking times from the grid.
  - Lesson: TBD

- [ ] Task 4: Scrape Sandefjord Penguins (Bookup SPA, Bugårdshallen)
  - Files: `.pi/lib/scraper-agent.ts`
  - Approach: Open https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen. Same Bookup platform as Tønsberg but different venue. Reuse the same navigation strategy.
  - Lesson: TBD

- [ ] Task 5: Validate all 9 clubs produce events in a pipeline run
  - Files: `input.json`, `.pipeline/cache/scraped_data.json`
  - Approach: Run full pipeline (Stage 1 + Stage 2 + ScraperAgent for blocked). Check cache has events from all 9 clubs. Regenerate viewer. Run tests.
  - Lesson: TBD

## Acceptance Criteria

- [ ] Extension runs ScraperAgent for blocked sources after Stage 2
- [ ] Jutul produces at least 1 event in a test run
- [ ] Tønsberg produces at least 1 event in a test run
- [ ] Sandefjord produces at least 1 event in a test run
- [ ] All 9 clubs have events in the unified cache
- [ ] Viewer regenerated with all 9 clubs
- [ ] Run `pytest` and confirm all tests pass

## Log

(Will be populated as tasks are completed.)
