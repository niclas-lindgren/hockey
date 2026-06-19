# Plan: Move hardcoded URL substring checks into scraper_strategies.py

**Feature:** Move hardcoded URL substring checks (baerumishall.no, bookup.no) from stage2_scraping._scrape_source dispatch block into scraper_strategies.py alongside get_strategy/needs_llm_agent — adding a new special-case source currently requires editing the core scraping loop.
**Goal:** Move hardcoded URL substring checks (baerumishall.no, bookup.no) from stage2_scraping._scrape_source dispatch block into scraper_strategies.py alongside get_strategy/needs_llm_agent — adding a new special-case source currently requires editing the core scraping loop.
**Backlog-ref:** 133
**Constraints:** none
**Date:** 2026-06-19
**Intent:** Centralise per-source dispatch knowledge in scraper_strategies.py so that the core scraping loop is open/closed — new special-case sources can be added by editing only the strategies module.

---

## Tasks

- [x] Added get_deterministic_scraper_type function to scraper_strategies.py mapping CalendarEngine values to scraper type strings. — 2026-06-19
  - Files: `tournament_scheduler/pipeline/scraper_strategies.py`
  - Approach: Add a new public function that takes a `ScraperStrategy` and returns a string identifier ("styledcalendar", "bookup", "browser", "ical", or None) based on `strategy.engine`. Map `STYLED_CALENDAR` → "styledcalendar", `BOOKUP_SPA` → "bookup", `OUTLOOK_IFRAME` / `DATE_PARAM` → "browser", `TEAMUP_ICAL` / `GENERIC_ICAL` → "ical". Include a docstring and export the function alongside `get_strategy`, `needs_llm_agent`, etc.

- [x] Replaced baerumishall.no and bookup.no URL substring checks with strategy-based dispatch using get_deterministic_scraper_type; falls back to source_type sets for sources not in STRATEGIES. — 2026-06-19
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`
  - Approach: At the top of the deterministic scraper block, call `get_strategy(name)` to retrieve the strategy for the current source. Then call `get_deterministic_scraper_type(strategy)` and branch on the returned string instead of `"baerumishall.no" in url` / `"bookup.no" in url`. Keep the existing `source_type in _BROWSER_SOURCE_TYPES` / `_ICAL_SOURCE_TYPES` fallbacks for sources not in STRATEGIES. Import `get_deterministic_scraper_type` from `scraper_strategies`.

- [x] Added TestStrategyBasedDispatch class with two tests: BOOKUP_SPA→_run_bookup_scraper and STYLED_CALENDAR→_run_styledcalendar_scraper, using real strategy registry entries (Tønsberg and Jutul). — 2026-06-19
  - Files: `tests/test_stage2_scraping.py`
  - Approach: For existing tests that mock `_run_bookup_scraper` or `_run_styledcalendar_scraper` triggered by a URL like "bookup.no" or "baerumishall.no", verify they still call the correct scraper function under the new strategy-based dispatch (the test setup may need to ensure a matching STRATEGIES entry exists or mock `get_strategy`). Add a test asserting that a source with `CalendarEngine.BOOKUP_SPA` routes to `_run_bookup_scraper` and one with `CalendarEngine.STYLED_CALENDAR` routes to `_run_styledcalendar_scraper`.

- [ ] Add unit tests for `get_deterministic_scraper_type` in a scraper_strategies test file
  - Files: `tests/test_scraper_strategies.py`
  - Approach: Create or extend `tests/test_scraper_strategies.py` with parametrised pytest cases that call `get_deterministic_scraper_type(strategy)` for each `CalendarEngine` variant and assert the returned string matches expectations. Cover at minimum `STYLED_CALENDAR`, `BOOKUP_SPA`, `OUTLOOK_IFRAME`, `TEAMUP_ICAL`, and `GENERIC_ICAL`.

- [ ] Update docstring in `stage2_scraping._scrape_source` to reflect new dispatch path
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`
  - Approach: Rewrite the function docstring to state that special-case dispatch (StyledCalendar, Bookup) is now driven by the `ScraperStrategy.engine` field looked up via `get_deterministic_scraper_type`, rather than by URL substring checks. Remove or update any inline comments that reference the old `"baerumishall.no" in url` pattern.

---

## Log

- 2026-06-19 Plan created

---

## Acceptance Criteria

The `_scrape_source` function in `stage2_scraping.py` no longer contains the strings "baerumishall.no" or "bookup.no".
`get_deterministic_scraper_type` in `scraper_strategies.py` returns "styledcalendar" for a `STYLED_CALENDAR` strategy and "bookup" for a `BOOKUP_SPA` strategy.
Running `pytest` passes all existing and new tests related to `_scrape_source` dispatch, including tests for bookup and styledcalendar routing.
Adding a new special-case source to `STRATEGIES` in `scraper_strategies.py` with the appropriate `CalendarEngine` value is sufficient to have it dispatched correctly in `_scrape_source` without modifying `stage2_scraping.py`.
The `get_deterministic_scraper_type` function is exported from `scraper_strategies.py` alongside the existing `get_strategy`, `needs_llm_agent`, and `requires_credentials` functions.

### 2026-06-19 — Added get_deterministic_scraper_type function to scraper_strategies.py mapping CalendarEngine values to scraper type strings.
**Rationale:** Straightforward mapping dict approach keeps engine-to-type knowledge co-located with other strategy helpers.
**Findings:** Function returns correct strings: bookup→bookup, styled_calendar→styledcalendar, outlook_iframe/date_param/forumbooking/sportello→browser, teamup_ical/generic_ical→ical; verified via python3 import test.
LESSONS: none
**Files:** scraper_strategies.py (+31/-0)
**Commit:** 54d1d95 (hockey)

### 2026-06-19 — Replaced baerumishall.no and bookup.no URL substring checks with strategy-based dispatch using get_deterministic_scraper_type; falls back to source_type sets for sources not in STRATEGIES.
**Rationale:** Minimal-invasive: added two lines before the if/elif chain, replaced the first two branches with string comparisons on the returned token, kept fallback branches untouched.
**Findings:** All 28 stage2 tests pass; import verified via python3 -c.
LESSONS: none
**Files:** stage2_scraping.py (+10/-5)
**Commit:** 297ed90 (hockey)

### 2026-06-19 — Added TestStrategyBasedDispatch class with two tests: BOOKUP_SPA→_run_bookup_scraper and STYLED_CALENDAR→_run_styledcalendar_scraper, using real strategy registry entries (Tønsberg and Jutul).
**Rationale:** Used real STRATEGIES entries so the strategy lookup exercises actual production mappings rather than mocking get_strategy; AssertionError side effects guard against wrong scraper being called.
**Findings:** All 30 stage2 tests pass (28 existing + 2 new).
LESSONS: none
**Files:** test_stage2_scraping.py (+64/-0)
**Commit:** [pending — fill after commit]
