# Plan: Decouple global _CALENDAR_CACHE in stage2_scraping.py

**Feature:** Decouple global _CALENDAR_CACHE in stage2_scraping.py — global set in run() and consumed in _scrape_source() via side-channel; pass cache explicitly so _scrape_source can be unit-tested in isolation
**Goal:** Decouple global _CALENDAR_CACHE in stage2_scraping.py — global set in run() and consumed in _scrape_source() via side-channel; pass cache explicitly so _scrape_source can be unit-tested in isolation
**Backlog-ref:** 175
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Remove the global _CALENDAR_CACHE side-channel so _scrape_source is a pure, injected-dependency function that can be called in isolation by tests and external tools without requiring run() to have been called first.

---

## Tasks

- [x] Added calendar_cache: CalendarCache  None  None to _scrape_source signature and removed the _CALENDAR_CACHE side-channel assignment from the function body. — 2026-06-20
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`
  - Approach: Change the signature to `def _scrape_source(source_cfg, *, start_date, end_date, calendar_cache: CalendarCache | None = None)` and replace the `calendar_cache = _CALENDAR_CACHE` side-channel line with direct use of the new parameter.

- [x] Updated run() to create a local calendar_cache variable and pass it explicitly in the ThreadPoolExecutor submit call, removing the global assignment. — 2026-06-20
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`
  - Approach: In `run()`, after initialising `_CALENDAR_CACHE = CalendarCache(...)`, pass it explicitly via `executor.submit(_scrape_source, source_cfg, start_date=..., end_date=..., calendar_cache=calendar_cache)` so parallel workers receive the instance rather than reading a global.

- [x] Updated calendar_compare.py and pipeline_orchestrator.py to pass calendar_cacheNone explicitly at each _scrape_source call site. — 2026-06-20
  - Files: `tournament_scheduler/tools/calendar_compare.py`, `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Approach: At each `_scrape_source(source_cfg, start_date=..., end_date=...)` call site, create or thread through a `CalendarCache` instance and pass it as `calendar_cache=cache`; if no cache is appropriate for that context pass `None` explicitly.

- [x] Removed the _CALENDAR_CACHE: CalendarCache  None  None module-level declaration and the global _CALENDAR_CACHE statement inside run(). — 2026-06-20
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`
  - Approach: Delete the module-level `_CALENDAR_CACHE: CalendarCache | None = None` declaration and the `global _CALENDAR_CACHE` statement inside `run()`; update `run()` to use a local variable `calendar_cache = CalendarCache(work_dir=state.work_dir)` instead.

- [x] Added TestScrapeSourceIsolated class with 4 tests covering iCal branch, browser branch, error branch, and None cache — all calling _scrape_source directly without run(). Also fixed crashing_scraper closure in TestParallelExecution to include calendar_cache parameter. — 2026-06-20
  - Files: `tests/test_stage2_scraping.py`
  - Approach: Add a new test class (e.g. `TestScrapeSourceIsolated`) with cases that call `_scrape_source(source_cfg, start_date=..., end_date=..., calendar_cache=mock_cache)` directly — no `run()` needed — verifying that the function returns the expected result shape for iCal, browser, and error branches.

---

## Log

- 2026-06-20 Plan created

---

## Acceptance Criteria

When _scrape_source is called without a calendar_cache parameter, it fails with a TypeError indicating the missing argument.
The _CALENDAR_CACHE global variable is removed from tournament_scheduler/pipeline/stage2_scraping.py and no longer exists in the module namespace.
Unit tests can call _scrape_source directly with a CalendarCache instance and produce expected output without requiring global state setup.
External callers in calendar_compare.py and pipeline_orchestrator.py pass a CalendarCache instance as the calendar_cache parameter when calling _scrape_source.
The run() function in stage2_scraping.py creates a CalendarCache instance and passes it to _scrape_source when submitting work to the ThreadPoolExecutor.

### 2026-06-20 — Added calendar_cache: CalendarCache  None  None to _scrape_source signature and removed the _CALENDAR_CACHE side-channel assignment from the function body.
**Rationale:** Straightforward parameter addition; no alternatives needed.
**Findings:** Function now accepts calendar_cache as an explicit keyword parameter, enabling isolated testing.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+6/-2)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Updated run() to create a local calendar_cache variable and pass it explicitly in the ThreadPoolExecutor submit call, removing the global assignment.
**Rationale:** Local variable replaces global; no alternatives needed.
**Findings:** Parallel workers now receive the CalendarCache instance via parameter rather than global state.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+3/-4)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Updated calendar_compare.py and pipeline_orchestrator.py to pass calendar_cacheNone explicitly at each _scrape_source call site.
**Rationale:** Neither caller has a CalendarCache context, so None is appropriate; these are one-shot diagnostic calls.
**Findings:** Both external callers updated to use explicit calendar_cacheNone.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+1/-1), tournament_scheduler/tools/calendar_compare.py (+1)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Removed the _CALENDAR_CACHE: CalendarCache  None  None module-level declaration and the global _CALENDAR_CACHE statement inside run().
**Rationale:** Direct deletion after confirming no remaining references.
**Findings:** _CALENDAR_CACHE no longer exists in the module namespace.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (removed global)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Added TestScrapeSourceIsolated class with 4 tests covering iCal branch, browser branch, error branch, and None cache — all calling _scrape_source directly without run(). Also fixed crashing_scraper closure in TestParallelExecution to include calendar_cache parameter.
**Rationale:** Direct test of _scrape_source with injected CalendarCache; also fixed one existing test whose closure missed the new parameter.
**Findings:** All 40 tests pass; _run_ical_scraper returns a list not tuple (no unpacking in _scrape_source).
LESSONS: _run_ical_scraper returns a list directly (not a tuple); do not mock it with (list, str) tuples. _run_outlook_scraper returns a tuple (events, error_str).
**Files:** tests/test_stage2_scraping.py (+124/-2)
**Commit:** [pending — fill after commit]
