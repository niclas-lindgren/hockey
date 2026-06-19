# Plan: Remove stage2_helpers.py re-export facade
**Goal:** Remove stage2_helpers.py re-export facade — it adds no value over importing directly from the real sub-modules; update stage2_scraping.py to import from sub-modules directly.
**Created:** 2026-06-19
**Intent:** Eliminate the indirection layer that stage2_helpers.py adds between stage2_scraping.py and the actual sub-modules, simplifying the import graph and removing a file that provides no logic.
**Backlog-ref:** 131

## Tasks
- [x] Replaced single bulk import from stage2_helpers with 8 direct sub-module imports grouped by module in stage2_scraping.py. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Remove the single import statement on line 45 that pulls all 16 symbols from .stage2_helpers and replace it with separate import statements grouped by sub-module: scraper_bookup (3 symbols), scraper_cache (1), scraper_credentialed (3), scraper_event_helpers (2), scraper_ical (1), scraper_outlook (3), scraper_recovery (2), scraper_styledcalendar (1).
- [ ] Delete stage2_helpers.py
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage2_helpers.py
  - Approach: Delete the file entirely using shell rm; it is now unreferenced since the only consumer (stage2_scraping.py) has been updated to import directly from the sub-modules.
- [ ] Confirm no regressions after removing the facade
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Run pytest to verify the test suite passes with no import errors or failures introduced by the removal.

## Notes
Constraints: none
No other file in the package or tests imports from stage2_helpers — only stage2_scraping.py on line 45. The sub-module mapping is: scraper_bookup (_bookup_navigate_to_date, _parse_bookup_timegrid, _run_bookup_scraper), scraper_cache (_cached_source_result), scraper_credentialed (_credentialed_scrape_months, _run_credentialed_bookup_or_outlook, _try_credentialed_scrape), scraper_event_helpers (_events_to_dicts, _group_events_by_club), scraper_ical (_run_ical_scraper), scraper_outlook (_parse_date_param_calendar, _parse_outlook_calendar, _run_outlook_scraper), scraper_recovery (_blocked_sources_warning, _recovery_hint_for_source), scraper_styledcalendar (_run_styledcalendar_scraper).

## Acceptance Criteria
- [ ] The file stage2_helpers.py is deleted from the repository and no longer exists on disk.
- [ ] stage2_scraping.py contains no import statement referencing stage2_helpers.
- [ ] stage2_scraping.py contains direct imports from scraper_bookup, scraper_cache, scraper_credentialed, scraper_event_helpers, scraper_ical, scraper_outlook, scraper_recovery, and scraper_styledcalendar.
- [ ] Running pytest passes with no import errors or test failures after the removal.
- [ ] Searching the codebase for "stage2_helpers" returns no matches in source files.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Replaced single bulk import from stage2_helpers with 8 direct sub-module imports grouped by module in stage2_scraping.py.
**Rationale:** Straightforward replacement following the sub-module grouping already established in stage2_helpers.py.
**Findings:** Import verified successful via python3 module import check; pre-existing test failure in test_claude_orchestration.py unrelated to this change.
LESSONS: none
**Files:** stage2_scraping.py (+8/-1)
**Commit:** [pending — fill after commit]
