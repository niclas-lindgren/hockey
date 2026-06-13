# Plan: Reuse valid scraped calendar cache entries
**Goal:** Stage 2 skips re-scraping sources when the unified cache still holds valid events, even if the last scrape for that source was blocked.
**Created:** 2026-06-13
**Intent:** Avoid wasting time on repeat scrapes for calendars that already have fresh cached data, especially when a source remains temporarily blocked.
**Backlog-ref:** 76

## Tasks
- [x] Relax Stage 2 cache-hit logic so fresh cached events are reused even if the previous scrape was blocked
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/cache_manager.py
  - Approach: Treat `blocked` as status metadata rather than a cache-hit veto. Reuse entries when the date range matches, the entry still has events, and the TTL is fresh; when a blocked scrape falls back to previously cached events, keep the cached data reusable instead of forcing a new scrape on every run.
- [x] Add regression coverage for blocked-cache reuse and cache freshness preservation
  - Files: tests/test_stage2_scraping.py
  - Approach: Seed the unified cache with a fresh blocked entry that still has events, assert Stage 2 reads it from cache without calling the scraper, and verify the cache still retains the prior events/data needed for the next run.

## Notes
- This should stay within Stage 2/cache behavior; no pipeline contract changes are needed.
- Preserve the existing blocked-source warning behavior for runs that truly have no usable cached data.

## Acceptance Criteria
- [ ] Stage 2 reports cached hits for valid blocked entries instead of re-scraping them.
- [ ] A fresh blocked cache entry with events does not invoke the browser/ical scraper during Stage 2.

## Log


### 2026-06-13 — Add regression coverage for blocked-cache reuse and cache freshness preservation
**Done:** Added regression tests covering both a fresh blocked cache hit and refresh of preserved cache data after a blocked rescrape.
**Rationale:** The tests lock in the new cache semantics so fresh blocked entries skip scraping and preserved fallback data remains reusable after a failed refresh.
**Findings:** A blocked source with existing events was previously always re-scraped because the cache predicate rejected blocked entries. The new tests confirm cache reuse and that preserved events survive a forced blocked scrape with an updated timestamp.
**Files:** tests/test_stage2_scraping.py
**Commit:** not committed
### 2026-06-13 — Relax Stage 2 cache-hit logic so fresh cached events are reused even if the previous scrape was blocked
**Done:** Stage 2 now reuses fresh cached source results even when the last scrape for that source was blocked.
**Rationale:** Blocked should be treated as scrape metadata, not a cache-hit veto, so valid cached events can avoid unnecessary re-scrapes.
**Findings:** Fresh blocked entries were being skipped only because the cache-hit predicate rejected blocked sources. The cache manager now refreshes preserved event timestamps when a scrape returns no events, keeping fallback cache data reusable instead of immediately stale.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py; tournament_scheduler/pipeline/cache_manager.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
