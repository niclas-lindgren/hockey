# Plan: Make Holmen's Sportello calendar scriptable
**Goal:** Holmen's Sportello calendar is scraped deterministically through the public GraphQL API, so `scrape` works without a browser-only recovery path.
**Created:** 2026-07-27
**Intent:** Replace the JS-only Holmen recovery gap with a repo-local scraper path that works from the normal CLI and keeps docs/tests in sync.

## Tasks
- [x] Add a deterministic Sportello GraphQL scraper and route Holmen to it
  - Files: tournament_scheduler/pipeline/scraper_sportello.py, tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: query Sportello's public GraphQL `publicBookings` endpoint in <=100-day chunks, normalize UTC timestamps to Europe/Oslo local datetimes, deduplicate bookings, and dispatch Holmen through the new deterministic scraper instead of the LLM-agent path.

- [x] Update operator-facing notes and CLI expectations for Holmen's recovery path
  - Files: tournament_scheduler/club_registry.py, docs/rvv-miniputt-pipeline.md, .agents/skills/rvv/SKILL.md, tests/test_rvv_cli_portability.py
  - Approach: rewrite Holmen/Sportello docs to call out the scriptable GraphQL scraper, keep `scrape-llm` guidance for remaining browser-only sources, and add/adjust CLI tests so Holmen points to `scrape` while a true browser-only source still shows the boundary message.

- [x] Add regression coverage for Sportello scraping and direct dispatch
  - Files: tests/test_stage2_scraping.py, tests/test_scraper_strategies.py, tests/test_scraper_sportello.py
  - Approach: mock GraphQL responses to prove chunking, local-time conversion, and deduping; verify `CalendarEngine.SPORTELLO` maps to the sportello scraper; and assert stage2 dispatch uses the new scraper for Holmen.

## Notes
Holmen's page is a JS SPA, but the data behind it is exposed through a public GraphQL endpoint (`publicBookings`), so a deterministic scraper should be able to replace the browser-only recovery path.

## Acceptance Criteria
- [ ] Running `rvv-miniputt scrape --club Holmen` returns Sportello bookings through the deterministic pipeline without requiring `scrape-llm` or interactive browser control.
- [ ] The docs and operator guidance update Holmen to scriptable status while keeping browser-tool guidance for the remaining blocked sources.
- [ ] Tests pass for Sportello chunking/parsing and prove stage 2 dispatch routes Holmen through the new scraper.

## Log



### 2026-07-27 — Add regression coverage for Sportello scraping and direct dispatch
**Done:** Added focused regression coverage for Sportello chunking/timezone normalization, strategy mapping, and stage 2 dispatch to the new Holmen scraper.
**Rationale:** The new scraper and routing need deterministic tests so the API limit, Oslo-time conversion, and engine dispatch don't drift back to browser-only handling.
**Findings:** The Sportello test stubs the GraphQL session and proves multi-chunk queries, duplicate suppression, and local-time conversion; stage 2 now calls `_run_sportello_scraper` for Holmen.
**Files:** tests/test_scraper_sportello.py, tests/test_scraper_strategies.py, tests/test_stage2_scraping.py
**Commit:** c0f006f
### 2026-07-27 — Update operator-facing notes and CLI expectations for Holmen's recovery path
**Done:** Updated the operator docs and CLI portability checks so Holmen is described as scriptable via the deterministic scraper, while browser-only sources still surface the browser-tool boundary.
**Rationale:** The user-facing guidance needed to match the new Sportello scraper so operators are steered to `scrape` for Holmen and only use `scrape-llm` where browser control is still required.
**Findings:** The docs now call out Holmen's deterministic GraphQL path; the CLI regression covers both behaviors by asserting Holmen points to `scrape` and a browser-only source still prints browser-tool guidance.
**Files:** .agents/skills/rvv/SKILL.md, docs/rvv-miniputt-pipeline.md, tournament_scheduler/club_registry.py, tests/test_rvv_cli_portability.py
**Commit:** c0f006f
### 2026-07-27 — Add a deterministic Sportello GraphQL scraper and route Holmen to it
**Done:** Added a deterministic Sportello scraper, routed Holmen through it in stage 2, and updated the strategy/dispatch plumbing so Holmen no longer depends on the browser-only recovery path.
**Rationale:** Holmen's Sportello calendar exposes a public GraphQL API, so a repo-local scraper is the right scriptable path and removes the JS-only gap without needing the LLM agent.
**Findings:** Sportello's public `publicBookings` GraphQL endpoint is reachable from the terminal and supports date-bounded queries; chunking to <=100 days avoids the API limit, and the returned UTC timestamps need conversion to local Norwegian time before conflict checks.
**Files:** tournament_scheduler/pipeline/scraper_sportello.py, tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/club_registry.py, tournament_scheduler/tools/calendar_compare.py
**Commit:** c0f006f
<!-- pi-next appends entries here after each task -->
