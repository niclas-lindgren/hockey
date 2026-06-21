# Plan: Fix browser_worker.py retry goto timeout

**Goal:** Fix browser_worker.py ~line 300 retry goto using same 30s timeout — fallback navigation uses identical timeout so it cannot recover from slow page loads
**Created:** 2026-06-21
**Intent:** The cmd_goto retry uses the same 30s timeout as the initial attempt, making it useless for slow pages; giving the retry a longer timeout and lighter wait_until allows recovery from genuinely slow loads.
**Backlog-ref:** 172

## Tasks

- [x] Added GOTO_TIMEOUT_MS30_000 and GOTO_RETRY_TIMEOUT_MS60_000 as module-level constants; replaced both hardcoded 30_000 values in cmd_goto with these named constants so the retry uses a longer timeout. — 2026-06-21
  - Files: tournament_scheduler/pipeline/browser_worker.py
  - Approach: Define GOTO_TIMEOUT_MS = 30_000 and GOTO_RETRY_TIMEOUT_MS = 60_000 as module-level constants at the top of browser_worker.py, replacing all hardcoded 30_000 values in cmd_goto with these named constants for clarity.

- [x] Added wait_until"domcontentloaded" to the retry goto call so the fallback navigation no longer waits for full network idle, enabling recovery from slow but eventually responsive pages. — 2026-06-21
  - Files: tournament_scheduler/pipeline/browser_worker.py
  - Approach: Update the retry goto call (line ~297) to use timeout=GOTO_RETRY_TIMEOUT_MS (60_000ms) and add wait_until="domcontentloaded" so the fallback navigation does not wait for full network idle, allowing recovery from pages that are slow but eventually respond.

- [x] Added TestCmdGotoRetry class to tests/test_browser_worker.py with 4 tests: initial goto uses GOTO_TIMEOUT_MS/networkidle, retry uses GOTO_RETRY_TIMEOUT_MS/domcontentloaded, retry timeout is strictly larger, and both failures return okFalse. — 2026-06-21
  - Files: tests/test_browser_worker.py
  - Approach: Create or extend a test in tests/test_browser_worker.py that mocks page.goto() to raise a timeout on the first call and succeed on the retry, asserting that the retry is called with a longer timeout value than the initial attempt.

## Notes

Constraints: none

Key context:
- cmd_goto method in browser_worker.py (lines 289–302): first goto uses timeout=30_000 with wait_until="networkidle"; retry goto also uses timeout=30_000 with no wait_until parameter
- set_default_timeout(15_000) is set at page init (line 153)
- All other scrapers (llm_scraper.py, scraper_credentialed.py, scraper_outlook.py, scraper_bookup.py) hardcode 30_000 for page.goto() — not in scope of this fix

## Acceptance Criteria

- [ ] The browser_worker.py cmd_goto method contains a retry goto call with timeout=60_000 instead of the original 30_000.
- [ ] The browser_worker.py cmd_goto retry call uses wait_until="domcontentloaded" instead of no wait_until parameter.
- [ ] The browser_worker.py cmd_goto method produces a successful navigation result when pages are slow but eventually become available within the extended timeout.
- [ ] The browser_worker.py cmd_goto method reports a timeout error only when pages truly cannot load within the extended 60_000ms timeout period.
- [ ] Tests pass for the updated retry logic, verifying the retry call receives a longer timeout than the initial navigation attempt.

## Log

<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-21 — Added GOTO_TIMEOUT_MS30_000 and GOTO_RETRY_TIMEOUT_MS60_000 as module-level constants; replaced both hardcoded 30_000 values in cmd_goto with these named constants so the retry uses a longer timeout.
**Rationale:** Straightforward — retry fallback previously used same 30s timeout as initial attempt, giving it no extra time to recover from slow loads.
**Findings:** Both goto calls in cmd_goto now reference named constants; retry uses 60s instead of 30s.
LESSONS: none
**Files:** tournament_scheduler/pipeline/browser_worker.py (+6/-2)
**Commit:** dedb048 (hockey)

### 2026-06-21 — Added wait_until"domcontentloaded" to the retry goto call so the fallback navigation no longer waits for full network idle, enabling recovery from slow but eventually responsive pages.
**Rationale:** none
**Findings:** Retry goto now uses domcontentloaded instead of full networkidle — combined with the 60s timeout from task 1, this gives the fallback a real chance to succeed on slow pages.
LESSONS: none
**Files:** tournament_scheduler/pipeline/browser_worker.py (+1/-1)
**Commit:** c6541a9 (hockey)

### 2026-06-21 — Added TestCmdGotoRetry class to tests/test_browser_worker.py with 4 tests: initial goto uses GOTO_TIMEOUT_MS/networkidle, retry uses GOTO_RETRY_TIMEOUT_MS/domcontentloaded, retry timeout is strictly larger, and both failures return okFalse.
**Rationale:** none
**Findings:** All 20 tests pass; new tests mock _page and start() to avoid launching real Playwright.
LESSONS: none
**Files:** tests/test_browser_worker.py (+70)
**Commit:** [pending — fill after commit]
