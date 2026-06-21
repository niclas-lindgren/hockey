# Plan: Scraper cache config fingerprinting
**Goal:** Scraper cache should fingerprint relevant config (e.g. location_filter) so that a config change automatically invalidates stale cache entries instead of requiring manual cache file deletion
**Created:** 2026-06-21
**Intent:** Prevent silent stale-data bugs where a user changes location_filter (or other scrape-affecting config) but the cache silently returns old events because the key never included those config fields.
**Backlog-ref:** 188

## Tasks
- [x] Extended _get_cache_key, get, and set in CalendarCache to accept an optional location_filter parameter included in the pipe-delimited hash string; updated ICalScraper.scrape_calendar to pass location_filter to both cache.get and cache.set. — 2026-06-21
  - Files: tournament_scheduler/utils/calendar_cache.py
  - Approach: Extend `_get_cache_key` to accept an optional `location_filter: str | None` parameter and include it in the pipe-delimited string before hashing; update all call sites in calendar_cache.py to pass the value through.
- [x] Verified that scraper_ical.py already accepts and forwards location_filter to ICalScraper.scrape_calendar, and stage2_scraping.py already fetches location_filter from CLUB_REGISTRY and passes it to _run_ical_scraper — no code changes needed. — 2026-06-21
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/scraper_ical.py
  - Approach: In `_run_ical_scraper` (stage2_scraping.py) and any helper in scraper_ical.py that calls into CalendarCache, pass the `location_filter` value already fetched from CLUB_REGISTRY so the updated `_get_cache_key` receives it.
- [x] Added _compute_config_fingerprint helper and config_fingerprint field to per-source cache entries in ScrapedDataCache.build_from_checkpoint; added is_config_match method; propagated location_filter through stage2 source_result dict so build_from_checkpoint can include it in the fingerprint. — 2026-06-21
  - Files: tournament_scheduler/pipeline/cache_manager.py
  - Approach: Add a `config_fingerprint` field (md5 of relevant config: url, location_filter, source kind) to each per-source entry written by `build_from_checkpoint`; on cache read in `is_stale` or a new `is_config_match` method, compare stored fingerprint against freshly computed one and treat mismatch as a cache miss.
- [x] Added config fingerprint check to the cache-hit guard in stage2_scraping.py: before accepting a cached entry, is_config_match is called with the current url, source_type, and location_filter; a mismatch causes the source to be re-scraped. — 2026-06-21
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/cache_manager.py
  - Approach: In the cache-hit check (stage2_scraping.py ~line 230), after the staleness check, also call `cache.is_config_match(name, current_fingerprint)`; on mismatch, skip the cached entry so the source is re-scraped and a fresh entry is written.
- [ ] Add unit tests for cache key and fingerprint invalidation
  - Files: tests/test_calendar_cache.py, tests/test_stage2_scraping.py
  - Approach: Add test cases asserting that two `_get_cache_key` calls with different `location_filter` values produce different keys; add an integration-style test for stage2 that seeds a cache entry with a stale fingerprint and asserts the source is re-scraped instead of reused.

## Notes
Two separate caching layers exist: `tournament_scheduler/utils/calendar_cache.py` (CalendarCache — used for iCal HTTP responses, keyed by url+name+dates) and `tournament_scheduler/pipeline/cache_manager.py` (ScrapedDataCache — the unified stage2 checkpoint cache, keyed by source name). Both must fingerprint config to prevent stale hits. The `location_filter` field in `ClubCalendarSource` (club_registry.py) is the primary config parameter that affects which events survive scraping but is currently absent from all cache keys.

## Acceptance Criteria
- [ ] When location_filter changes for a source, the cache manager produces a new cache entry for that source instead of returning stale events.
- [ ] The CalendarCache `_get_cache_key` method returns different hex digests for the same url and date range when location_filter values differ.
- [ ] The ScrapedDataCache per-source entries contain a config_fingerprint field that includes the location_filter value.
- [ ] Running pytest passes with no regressions, and the new tests for key differentiation and fingerprint mismatch invalidation pass.
- [ ] No manual cache file deletion is required after a location_filter change — re-running stage 2 automatically re-scrapes and updates the affected source.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-21 — Extended _get_cache_key, get, and set in CalendarCache to accept an optional location_filter parameter included in the pipe-delimited hash string; updated ICalScraper.scrape_calendar to pass location_filter to both cache.get and cache.set.
**Rationale:** Chose to add location_filter as optional kwarg with None default so all existing call sites (calendar_scraper.py, etc.) continue to work unchanged; tests pass.
**Findings:** cache.get and cache.set in ical_scraper.py now pass location_filter so different filters produce distinct cache entries; calendar_scraper.py callers unaffected (default None).
LESSONS: none
**Files:** ical_scraper.py (+6/-4), calendar_cache.py (+23/-6)
**Commit:** 889d252 (hockey)

### 2026-06-21 — Verified that scraper_ical.py already accepts and forwards location_filter to ICalScraper.scrape_calendar, and stage2_scraping.py already fetches location_filter from CLUB_REGISTRY and passes it to _run_ical_scraper — no code changes needed.
**Rationale:** Already implemented as part of prior work; the full propagation path (CLUB_REGISTRY -> stage2 -> scraper_ical -> ICalScraper -> cache) was complete.
**Findings:** Full location_filter propagation path confirmed in place: stage2_scraping.py:380 passes it to _run_ical_scraper which passes it to ICalScraper.scrape_calendar.
LESSONS: none
**Files:** no files changed — already implemented
**Commit:** d5ab609 (hockey)

### 2026-06-21 — Added _compute_config_fingerprint helper and config_fingerprint field to per-source cache entries in ScrapedDataCache.build_from_checkpoint; added is_config_match method; propagated location_filter through stage2 source_result dict so build_from_checkpoint can include it in the fingerprint.
**Rationale:** Stored location_filter in source_result at the ical scraper dispatch point in stage2_scraping.py so it flows into the checkpoint and then into cache_manager without requiring CLUB_REGISTRY import in cache_manager.
**Findings:** config_fingerprint is now stored per source entry and is_config_match returns False for legacy entries without a fingerprint (conservative invalidation).
LESSONS: Legacy cache entries without config_fingerprint are treated as mismatches by is_config_match (returns False); callers should handle this as a cache miss.
**Files:** cache_manager.py (+47/-0), stage2_scraping.py (+2/-1)
**Commit:** 2bc00eb (hockey)

### 2026-06-21 — Added config fingerprint check to the cache-hit guard in stage2_scraping.py: before accepting a cached entry, is_config_match is called with the current url, source_type, and location_filter; a mismatch causes the source to be re-scraped.
**Rationale:** The location_filter lookup for the cache-hit guard reuses the same CLUB_REGISTRY pattern as _scrape_source, keeping the logic consistent without duplication.
**Findings:** Cache entries with stale config (changed url, source_type, or location_filter) now trigger a re-scrape automatically; legacy entries without a fingerprint also trigger a re-scrape (is_config_match returns False).
LESSONS: none
**Files:** stage2_scraping.py (+8/-0)
**Commit:** [pending — fill after commit]
