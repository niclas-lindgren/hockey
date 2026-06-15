# Plan: Refactor stage2_helpers.py into smaller focused modules
**Goal:** stage2_helpers.py (~1107 lines) is split into ~9 single-concern modules, all tests pass unchanged, and stage2_scraping.py continues to import from stage2_helpers as a backward-compat re-export facade.
**Created:** 2026-06-15
**Intent:** Improve maintainability and readability by separating scraping orchestration, source-specific scrapers (Outlook, BookUp, StyledCalendar, iCal), credentialed login flow, event serialization/grouping, and error recovery hints into dedicated files.
**Backlog-ref:** 107

## Tasks
- [x] Create scraper_constants.py — shared SOURCE_* type constants, _BROWSER_SOURCE_TYPES, _ICAL_SOURCE_TYPES sets
  - Files: tournament_scheduler/pipeline/scraper_constants.py
  - Approach: Extract the 6 constants (SOURCE_OUTLOOK, SOURCE_HTML, SOURCE_ICAL, SOURCE_GOOGLE, _BROWSER_SOURCE_TYPES, _ICAL_SOURCE_TYPES) from both stage2_helpers.py and stage2_scraping.py into a single shared module that both can import.

- [x] Create scraper_cache.py — _cached_source_result() helper
  - Files: tournament_scheduler/pipeline/scraper_cache.py
  - Approach: Extract `_cached_source_result()` function (lines 21-39 of current stage2_helpers.py) into its own module. It builds a source result dict from a fresh cache entry — purely data construction with no Playwright dependency.

- [x] Create scraper_recovery.py — _recovery_hint_for_source(), _blocked_sources_warning()
  - Files: tournament_scheduler/pipeline/scraper_recovery.py
  - Approach: Extract both Norwegian-language error/recovery message functions. Both depend on `get_strategy()` from scraper_strategies and `os.environ` for credential checks.

- [x] Create scraper_credentialed.py — _try_credentialed_scrape(), _run_credentialed_bookup_or_outlook(), _credentialed_scrape_months()
  - Files: tournament_scheduler/pipeline/scraper_credentialed.py
  - Approach: Extract all three functions that handle credential-injected scraping (Playwright-based login flow). Note the dangling docstring at lines ~445-460 (leftover from _credentialed_scrape_months) that will be cleaned.

- [x] Create scraper_ical.py — _run_ical_scraper()
  - Files: tournament_scheduler/pipeline/scraper_ical.py
  - Approach: Extract the simple iCal/Google Calendar scraper wrapper (~25 lines). Thin delegation to ICalScraper.

- [x] Create scraper_event_helpers.py — _events_to_dicts(), _group_events_by_club()
  - Files: tournament_scheduler/pipeline/scraper_event_helpers.py
  - Approach: Extract the two serialization/grouping helpers. Pure data transformation, no side effects, no Playwright.

- [x] Create scraper_outlook.py — _run_outlook_scraper(), _parse_outlook_calendar(), _parse_date_param_calendar()
  - Files: tournament_scheduler/pipeline/scraper_outlook.py
  - Approach: Extract the Outlook iframe-based scraper (~180 lines) and its two HTML parsers (~90 lines combined). The parsers are only called by the Outlook scraper so they stay co-located.

- [x] Create scraper_bookup.py — _run_bookup_scraper(), _bookup_navigate_to_date(), _parse_bookup_timegrid()
  - Files: tournament_scheduler/pipeline/scraper_bookup.py
  - Approach: Extract the BookUp SPA scraper and its two navigation/parsing helpers. All three share the `frame` Playwright context and FullCalendar semantics.

- [x] Create scraper_styledcalendar.py — _run_styledcalendar_scraper()
  - Files: tournament_scheduler/pipeline/scraper_styledcalendar.py
  - Approach: Extract the StyledCalendar/FullCalendar scraper (~130 lines). Standalone Playwright scraper for Bærum ishall embed.

- [x] Slim stage2_helpers.py to pure re-exports and remove dead code
  - Files: tournament_scheduler/pipeline/stage2_helpers.py
  - Approach: Replace all ~1107 lines with re-exports from the new modules (`from .scraper_cache import _cached_source_result`, etc.). Remove the unused `_scrape_source()` function (has its own copy in stage2_scraping.py). Remove duplicated `SOURCE_*`/`_BROWSER_SOURCE_TYPES`/`_ICAL_SOURCE_TYPES` constants (now in scraper_constants.py). Keep the same public API so stage2_scraping.py's import works unchanged.

- [x] Update stage2_scraping.py to import constants from scraper_constants.py
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Replace local constants (SOURCE_OUTLOOK, SOURCE_HTML, SOURCE_ICAL, SOURCE_GOOGLE, _BROWSER_SOURCE_TYPES, _ICAL_SOURCE_TYPES) with `from .scraper_constants import ...`. No functional change — just deduplication.

- [x] Run tests to verify nothing is broken
  - Files: tests/test_stage2_scraping.py
  - Approach: Run `cd /Users/niclasl/src/hockey && python3 -m pytest tests/test_stage2_scraping.py -v` to confirm all existing tests pass. Fix any import errors.

## Notes
- stage2_scraping.py imports 16 specific functions from stage2_helpers.py via `from .stage2_helpers import (...)`. The slimmed stage2_helpers.py must re-export all of them.
- The unused `_scrape_source()` in the current stage2_helpers.py (lines 42-130) is never imported by stage2_scraping.py — stage2_scraping.py defines its own local `_scrape_source` at line 275. Safe to remove.
- The constants are duplicated between stage2_helpers.py and stage2_scraping.py. Deduplicate by moving to scraper_constants.py.
- The dangling docstring at line ~416-418 in stage2_helpers.py (a lone docstring after `_credentialed_scrape_months`) needs cleanup during extraction.
- New modules should NOT create circular imports. `scraper_constants.py` must have zero dependencies on other pipeline modules.

## Acceptance Criteria
- [x] stage2_helpers.py is reduced from ~1107 lines to ~30 lines of re-exports
- [x] All 16 functions originally imported by stage2_scraping.py are available via stage2_helpers with the same names
- [x] The unused `_scrape_source()` function is removed (was dead code)
- [x] SOURCE_* constants are defined exactly once in scraper_constants.py
- [x] `python3 -m pytest tests/test_stage2_scraping.py -v` passes with no changes to test files
- [x] `python3 -m pytest tests/` passes without regressions
- [x] No new circular imports are introduced

## Log

### 2026-06-15 — Create scraper_constants.py
**Done:** Created scraper_constants.py with SOURCE_OUTLOOK, SOURCE_HTML, SOURCE_ICAL, SOURCE_GOOGLE constants and _BROWSER_SOURCE_TYPES/_ICAL_SOURCE_TYPES sets.
**Rationale:** Single source of truth for source-type constants eliminates duplication between stage2_helpers.py and stage2_scraping.py.
**Findings:** The same 6 constants were defined identically in both stage2_helpers.py and stage2_scraping.py. Moved to one shared module.
**Files:** tournament_scheduler/pipeline/scraper_constants.py (+8 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_cache.py
**Done:** Created scraper_cache.py with _cached_source_result() extracted and using SOURCE_OUTLOOK from scraper_constants.
**Rationale:** Separates cache-hit helper from the main orchestration module. No Playwright or side-effect dependencies.
**Findings:** The function itself is unchanged from the original — pure data construction from a cache entry dict.
**Files:** tournament_scheduler/pipeline/scraper_cache.py (+19 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_recovery.py
**Done:** Created scraper_recovery.py with _recovery_hint_for_source() and _blocked_sources_warning() extracted into a dedicated module.
**Rationale:** Separates Norwegian-language error messages and recovery hints from the scraping logic. Both functions depend on get_strategy/requires_credentials from scraper_strategies.
**Findings:** These functions wrap Norwegian credential/blocked-source messaging that depends on the scraper_strategies module and os.environ.
**Files:** tournament_scheduler/pipeline/scraper_recovery.py (+44 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_credentialed.py
**Done:** Created scraper_credentialed.py with _try_credentialed_scrape(), _run_credentialed_bookup_or_outlook(), _credentialed_scrape_months(). Removed dangling docstring (leftover from refactor).
**Rationale:** Separates the credentialed Playwright login+scrape flow from the main orchestration module. Imports _parse_bookup_timegrid from scraper_bookup and _parse_date_param_calendar/_parse_outlook_calendar from scraper_outlook.
**Findings:** Found and removed a dangling docstring (~13 lines) after _credentialed_scrape_months that was a leftover from a previous refactor — it referenced undefined variable `source_name`.
**Files:** tournament_scheduler/pipeline/scraper_credentialed.py (+143 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_ical.py
**Done:** Created scraper_ical.py with _run_ical_scraper() — thin delegation to ICalScraper.
**Rationale:** Separates the iCal/Google Calendar scraper wrapper into its own module. Standalone with no cross-module dependencies.
**Findings:** Unchanged from original — 15-line delegation function to ICalScraper.
**Files:** tournament_scheduler/pipeline/scraper_ical.py (+18 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_event_helpers.py
**Done:** Created scraper_event_helpers.py with _events_to_dicts() and _group_events_by_club() — pure data transformations with no side effects.
**Rationale:** Separates event serialization/grouping from orchestration and scraping. No Playwright or pipeline state dependencies.
**Findings:** These functions depend on CalendarEvent model and club_for_source_name from club_registry — no imports from other pipeline modules.
**Files:** tournament_scheduler/pipeline/scraper_event_helpers.py (+53 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_outlook.py
**Done:** Created scraper_outlook.py with _run_outlook_scraper(), _parse_outlook_calendar(), and _parse_date_param_calendar() — Outlook iframe scraping and HTML parsing.
**Rationale:** Separates the Outlook iframe/date-parameter scraper (Playwright) and its two HTML parsers into one focused module. Co-located because parsers are only called by the scraper.
**Findings:** _run_outlook_scraper uses both parsers internally, all three stay in the same module for cohesion.
**Files:** tournament_scheduler/pipeline/scraper_outlook.py (+240 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_bookup.py
**Done:** Created scraper_bookup.py with _run_bookup_scraper(), _bookup_navigate_to_date(), _parse_bookup_timegrid(). Also replaced __import__("datetime").timedelta with clean timedelta import.
**Rationale:** Separates the BookUp SPA FullCalendar scraper into its own module. All three helpers share the Playwright frame context and FullCalendar semantics.
**Findings:** scraper_credentialed.py imports _parse_bookup_timegrid from this module — no circular dependency since scraper_bookup.py does not import from scraper_credentialed.
**Files:** tournament_scheduler/pipeline/scraper_bookup.py (+190 lines)
**Commit:** 61747ed

### 2026-06-15 — Create scraper_styledcalendar.py
**Done:** Created scraper_styledcalendar.py with _run_styledcalendar_scraper() — Standalone Playwright scraper for Bærum ishall StyledCalendar embed.
**Rationale:** Separates the StyledCalendar/FullCalendar scraper into its own module. No cross-module dependencies.
**Findings:** Standalone scraper with no imports from other pipeline modules (only CalendarEvent from models and playwright sync_api).
**Files:** tournament_scheduler/pipeline/scraper_styledcalendar.py (+130 lines)
**Commit:** 61747ed

### 2026-06-15 — Slim stage2_helpers.py to pure re-exports and remove dead code
**Done:** Slimmed stage2_helpers.py from ~1107 lines to ~30 lines of re-exports. Removed unused _scrape_source() function. Removed duplicated SOURCE_*/_BROWSER_SOURCE_TYPES/_ICAL_SOURCE_TYPES constants.
**Rationale:** Backward-compat facade keeps stage2_scraping.py's `from .stage2_helpers import (...)` working unchanged. Dead code (_scrape_source was never imported) removed safely.
**Findings:** The unused _scrape_source() in old stage2_helpers.py (lines 42-130) was indeed dead — stage2_scraping.py defines and uses its own local copy. Constants were duplicated; now centralized in scraper_constants.py.
**Files:** tournament_scheduler/pipeline/stage2_helpers.py (1107→~30 lines)
**Commit:** 61747ed

### 2026-06-15 — Update stage2_scraping.py to import constants from scraper_constants.py
**Done:** Updated stage2_scraping.py to import SOURCE_*, _BROWSER_SOURCE_TYPES, _ICAL_SOURCE_TYPES from scraper_constants instead of defining them locally. No functional change.
**Rationale:** Deduplicates source-type constants that were previously duplicated between stage2_helpers.py and stage2_scraping.py.
**Findings:** The stage2_scraping.py already had its own local copy of SOURCE_* constants and _BROWSER/_ICAL_SOURCE_TYPES sets — identical to what was in stage2_helpers.py. Now both use the centralized scraper_constants module.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (replaced constants with import)
**Commit:** 61747ed

### 2026-06-15 — Run tests to verify nothing is broken
**Done:** All 399 tests pass (1 skipped, pre-existing). 0 new failures. Full test suite green.
**Rationale:** Verified backward compat by running full test suite. stage2_helpers.py re-exports all 16 functions correctly, and scraper_constants.py deduplication is seamless.
**Findings:** All 20 test_stage2_scraping.py tests pass. Full suite of 399 tests + 1 skip without regressions. Coverage shows new modules being exercised.
**Files:** tests/test_stage2_scraping.py (no changes)
**Commit:** 61747ed
