# Plan: Cache/fresh-fetch indicator in HTML report
**Goal:** The `calendars.html` sidebar shows a freshness indicator per club — whether data is fresh, cached, stale, or blocked.
**Created:** 2026-06-10
**Intent:** Currently the sidebar shows only event count and age. Users can't tell if data is live or from a previous cache run. A clear per-source status badge makes the pipeline's data quality transparent.
**Backlog-ref:** 38

## Tasks
- [x] Add per-source freshness/cache-status computation and badge in calendars.html
  - Files: tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: Compute a `_cache_status` helper that returns a badge string ("🔄 Fersk", "📦 Cachet", "⚡ Utdatert", "🚫 Blokkert") based on scrape_timestamp vs TTL, note field, and blocked flag. Display it in the sidebar club filter labels next to event count.

## Notes
- The cache already stores `scrape_timestamp` and `note` ("bruker tidligere cache...") per source.
- TTL is 6 hours by default (`DEFAULT_TTL_HOURS`).
- The sidebar currently shows: `(976 hendelser, 2t siden) 🟢`. The freshness badge should be added to this line.
- The `_age_string()` helper already computes human-readable age. The freshness badge adds a qualitative dimension: is the age acceptable?

## Acceptance Criteria
- [x] Each club in the sidebar shows a freshness badge: "Fersk", "Cachet", "Utdatert", or "Blokkert"
- [x] Fresh data (less than TTL old) shows "🔄 Fersk"
- [x] Data with `note` saying "tidligere cache" shows "📦 Cachet"
- [x] Data older than TTL (stale) shows "⚡ Utdatert"
- [x] Blocked sources show "🚫 Blokkert"

## Log

### 2026-06-10 — Add per-source freshness/cache-status computation and badge in calendars.html
**Done:** Added `_cache_status()` helper that returns a freshness badge per source: 🚫 Blokkert, 📦 Cachet, 🔄 Fersk, ⚡ Utdatert, or ❓ Ukjent. Updated sidebar filter generation to display the badge replacing the old 🟢/🔴 dots. Added CSS for `.club-freshness` styling.
**Rationale:** The cache already tracks scrape_timestamp, note (for cache fallback), and blocked status. The `_cache_status` function reads these and produces a human-readable Norwegian badge. Priority: blocked > cached fallback > fresh/stale based on TTL.
**Findings:** 7 clubs show ⚡ Utdatert (beyond 6h TTL), 2 show 🚫 Blokkert (Tønsberg, Sandefjord). Fresh 🔄 and Cachet 📦 badges are covered by code logic but require specific cache states to appear.
**Files:** tournament_scheduler/pipeline/calendar_viewer.py (+46/-9)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
