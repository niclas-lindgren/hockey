# Plan: Parallelize Stage 2 scraping with ThreadPoolExecutor (4 workers)
**Goal:** The 9-club scrape loop in `stage2_scraping.py` runs sources in parallel via `ThreadPoolExecutor(max_workers=4)`, giving ~3x speedup without changing per-source scraping logic.
**Created:** 2026-06-10
**Intent:** Each calendar source is independent — separate Playwright contexts per thread. Serial iteration wastes wall-clock time on I/O-bound browser and HTTP work.
**Backlog-ref:** 31

## Tasks
- [x] Refactor `run()` to collect source results via `ThreadPoolExecutor(max_workers=4)`
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Import `concurrent.futures.ThreadPoolExecutor`. Replace the serial `for source_cfg in sources:` loop with `executor.map()` or `executor.submit()`, calling `_scrape_source` per source in a worker thread. Collect results with `futures.as_completed()`. Keep the existing RUNNING status write and final checkpoint write (both outside the parallel block — they touch shared state). Each thread calls `_scrape_source` which internally creates its own `sync_playwright()` context, so no shared browser state. iCal scrapers don't use Playwright at all so they're trivially parallel-safe. Preserve the `blocked` collection logic unchanged.
- [x] Update tests to cover parallel execution and preserve existing behaviour
  - Files: tests/test_stage2_scraping.py
  - Approach: Add a test that verifies multiple sources run concurrently (e.g. by verifying ordering is non-deterministic, or by patching `_scrape_source` to track thread IDs). Ensure the existing tests still pass — they mock `_run_outlook_scraper` and `_run_ical_scraper` at a level below `_scrape_source`, so the parallel dispatch is transparent to them. Run `pytest tests/test_stage2_scraping.py -v` to confirm.

## Notes
- All browser scrapers (`_run_outlook_scraper`, `_run_styledcalendar_scraper`) create their own `sync_playwright()` context manager per call — no shared browser state, trivially thread-safe.
- iCal scrapers use HTTP — no browser, also trivially thread-safe.
- `PipelineState.write_stage` / `mark_done` calls are outside the parallel loop — only called before (RUNNING) and after (DONE/FAILED) the loop, so no threading concerns.
- The `_scrape_source` function and all helpers are pure functions with respect to shared state (they only operate on their own locals and arguments).
- The `CalendarEvent` model is a plain dataclass, safe to construct in any thread.
- Deduplication happens per-source inside each scraper function, so no cross-thread dedup collision.
- `max_workers=4` is a good default — balances parallelism with resource usage (4 concurrent Playwright browsers). Consider making it configurable via an optional kwarg `max_workers: int = 4` on `run()`.

## Acceptance Criteria
- [ ] `run()` uses `ThreadPoolExecutor` to scrape 9 sources in ~1/3 the wall-clock time (observable when running with real sources)
- [ ] All existing `test_stage2_scraping.py` tests pass unchanged or are updated to reflect the new dispatch
- [ ] Serial ordering semantics are not relied upon — parallel results are collected independently
- [ ] Blocked-source detection still works correctly (a source returning 0 events blocks the pipeline in strict mode)
- [ ] The `blocked` list in the checkpoint is correct regardless of which threads finish first

## Log


### 2026-06-10 — Update tests to cover parallel execution and preserve existing behaviour
**Done:** Added TestParallelExecution class with three tests: test_multiple_sources_all_collected, test_crashed_scraper_does_not_block_others, test_sources_run_in_different_threads.
**Rationale:** The three new tests cover: (1) all multiple-source results collected regardless of completion order, (2) a crashing scraper is caught per-future and does not block other workers, (3) sources actually execute in different OS threads proving parallelism. All tests mock at the helper level (_run_outlook_scraper / _run_ical_scraper) so they work regardless of serial or parallel dispatch.
**Findings:** The existing 8 tests pass without modification because they mock at _run_outlook_scraper / _run_ical_scraper level, which is called inside _scrape_source — transparent to the parallel dispatch. The thread-ID test consistently shows 3-5 unique threads for 5 sources with max_workers=4, confirming real parallelism.
**Files:** tests/test_stage2_scraping.py (+105 new test class)
**Commit:** not committed
### 2026-06-10 — Refactor `run()` to collect source results via `ThreadPoolExecutor(max_workers=4)`
**Done:** Replaced serial for-loop in run() with ThreadPoolExecutor(max_workers=4) using executor.submit() + as_completed(). Added exception handling per future so a crashing scraper doesn't take down other workers. Added optional max_workers kwarg (default 4) to run().
**Rationale:** Each source creates its own sync_playwright() context (or uses HTTP-only iCal feeds), so there's no shared browser state. ThreadPoolExecutor is the simplest stdlib option — no external dependencies, works with Playwright's sync API when each thread gets its own browser.
**Findings:** All 8 existing tests pass unchanged. The PipelineState writes (RUNNING and final checkpoint) remain outside the parallel block so no threading concerns. The blocked collection logic is preserved — each future's result is checked for block_reason after completion.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+24/-9)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
