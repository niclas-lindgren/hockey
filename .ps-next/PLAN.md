# Plan: Make Holmen's Sportello calendar scriptable
**Goal:** Holmen's Sportello calendar is scraped deterministically through the public GraphQL API, so `scrape` works without a browser-only recovery path.
**Created:** 2026-07-27
**Intent:** Replace the JS-only Holmen recovery gap with a repo-local scraper path that works from the normal CLI and keeps docs/tests in sync.

## Tasks
- [ ] Add a deterministic Sportello GraphQL scraper and route Holmen to it
  - Files: tournament_scheduler/pipeline/scraper_sportello.py, tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: query Sportello's public GraphQL `publicBookings` endpoint in <=100-day chunks, normalize UTC timestamps to Europe/Oslo local datetimes, deduplicate bookings, and dispatch Holmen through the new deterministic scraper instead of the LLM-agent path.

- [ ] Update operator-facing notes and CLI expectations for Holmen's recovery path
  - Files: tournament_scheduler/club_registry.py, docs/rvv-miniputt-pipeline.md, .agents/skills/rvv/SKILL.md, tests/test_rvv_cli_portability.py
  - Approach: rewrite Holmen/Sportello docs to call out the scriptable GraphQL scraper, keep `scrape-llm` guidance for remaining browser-only sources, and add/adjust CLI tests so Holmen points to `scrape` while a true browser-only source still shows the boundary message.

- [ ] Add regression coverage for Sportello scraping and direct dispatch
  - Files: tests/test_stage2_scraping.py, tests/test_scraper_strategies.py, tests/test_scraper_sportello.py
  - Approach: mock GraphQL responses to prove chunking, local-time conversion, and deduping; verify `CalendarEngine.SPORTELLO` maps to the sportello scraper; and assert stage2 dispatch uses the new scraper for Holmen.

## Notes
Holmen's page is a JS SPA, but the data behind it is exposed through a public GraphQL endpoint (`publicBookings`), so a deterministic scraper should be able to replace the browser-only recovery path.

## Acceptance Criteria
- [ ] Running `rvv-miniputt scrape --club Holmen` returns Sportello bookings through the deterministic pipeline without requiring `scrape-llm` or interactive browser control.
- [ ] The docs and operator guidance update Holmen to scriptable status while keeping browser-tool guidance for the remaining blocked sources.
- [ ] Tests pass for Sportello chunking/parsing and prove stage 2 dispatch routes Holmen through the new scraper.

## Log
<!-- pi-next appends entries here after each task -->
