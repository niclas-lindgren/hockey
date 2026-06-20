# Plan: Extract shared source_result dict helper in stage2_scraping.py
**Goal:** Extract shared source_result dict helper in stage2_scraping.py — missing-URL case, normal result, and error result all hand-roll the same dict shape across ~3 locations
**Created:** 2026-06-20
**Intent:** Eliminate repeated dict literals so all three source-result branches in stage2_scraping.py share one canonical construction point, making the shape easier to change and test.
**Backlog-ref:** 176

## Tasks
- [x] Added _make_source_result() module-level helper in stage2_scraping.py; refactored all three inline dict constructions (empty-URL skip, executor exception handler, _scrape_source base) to use it. — 2026-06-20
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Define a new module-level helper `_make_source_result(name, url, type, events, event_count, blocked, block_reason, llm_fallback, *, skipped=False, skip_reason=None, scraper_error=None, from_cache=False)` that returns the canonical dict; place it near the existing imports and existing helpers, following the style of `_cached_source_result` in scraper_cache.py.
- [x] Already implemented in the previous task — missing-URL branch now calls _make_source_result with skippedTrue and skip_reason. — 2026-06-20
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Locate the missing-URL branch (~line 163) that hand-rolls a dict with skipped/skip_reason extras and replace it with `_make_source_result(..., skipped=True, skip_reason=...)`, keeping all existing field values identical.
- [x] Already implemented in the first task — the executor exception handler now calls _make_source_result with scraper_error. — 2026-06-20
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Locate the error branch (~lines 207-217) that hand-rolls a dict with scraper_error and replace it with `_make_source_result(..., scraper_error=exc_str)`, keeping all existing field values identical.
- [x] Replaced _cached_source_result call with _make_source_result(..., from_cacheTrue) inline; removed now-unused _cached_source_result import from stage2_scraping.py. — 2026-06-20
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: At ~line 185 where `_cached_source_result(source_cfg, entry)` is called, unpack the cache entry fields and pass them to `_make_source_result(..., from_cache=True)`; verify the returned keys match what _cached_source_result currently returns, then remove or leave the import as appropriate.
- [ ] Update tests to assert consistent dict shape across all three branches
  - Files: tests/test_stage2_scraping.py
  - Approach: Add or extend test cases that exercise missing-URL, error, and normal-result paths and assert the returned source_result dicts share the common keys (name, url, type, events, event_count, blocked, block_reason, llm_fallback) in all cases; verify branch-specific extras (skipped, scraper_error, from_cache) are present only where expected.

## Notes
Constraints: none

Key codebase context:
- `_cached_source_result` in `tournament_scheduler/pipeline/scraper_cache.py` is imported at line 46 of stage2_scraping.py and handles the cached (normal-result) path; the new helper must produce an identical key set for that branch.
- All three branches share the core keys: name, url, type, events, event_count, blocked, block_reason, llm_fallback.
- Branch-specific extras: missing-URL adds skipped + skip_reason; error adds scraper_error; normal adds from_cache.

## Acceptance Criteria
- [ ] stage2_scraping.py contains no hand-rolled source_result dict literals — all three branches call the shared helper.
- [ ] The shared helper returns a dict that has all common keys (name, url, type, events, event_count, blocked, block_reason, llm_fallback) regardless of which branch calls it.
- [ ] Running pytest tests/test_stage2_scraping.py passes with all existing and new test cases green.
- [ ] The missing-URL branch produces a source_result that has skipped=True and a non-empty skip_reason, and does not contain scraper_error or from_cache.
- [ ] The error branch produces a source_result that contains scraper_error and does not contain skipped.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-20 — Added _make_source_result() module-level helper in stage2_scraping.py; refactored all three inline dict constructions (empty-URL skip, executor exception handler, _scrape_source base) to use it.
**Rationale:** Straightforward extraction — all three sites had compatible shapes; optional keys (skipped, skip_reason, scraper_error, from_cache) are included conditionally so the helper remains backward-compatible.
**Findings:** All tests pass; dict shape is now canonical and constructed in one place.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+80/-33)
**Commit:** pending — fill after commit

### 2026-06-20 — Already implemented in the previous task — missing-URL branch now calls _make_source_result with skippedTrue and skip_reason.
**Rationale:** Done as part of the helper introduction task.
**Findings:** Missing-URL branch verified to use _make_source_result in stage2_scraping.py.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (no additional changes)
**Commit:** none

### 2026-06-20 — Already implemented in the first task — the executor exception handler now calls _make_source_result with scraper_error.
**Rationale:** Done as part of the helper introduction task.
**Findings:** Error branch verified to use _make_source_result in stage2_scraping.py.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (no additional changes)
**Commit:** none

### 2026-06-20 — Replaced _cached_source_result call with _make_source_result(..., from_cacheTrue) inline; removed now-unused _cached_source_result import from stage2_scraping.py.
**Rationale:** Inlining the cache-hit path keeps all dict construction through a single canonical helper; _cached_source_result in scraper_cache.py is still available if other callers need it.
**Findings:** All tests pass; _cached_source_result import removed from stage2_scraping.py.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+12/-2)
**Commit:** pending — fill after commit
