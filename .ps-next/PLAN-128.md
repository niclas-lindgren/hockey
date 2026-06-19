# Plan: Fix credentialed fallback to skip on deterministic exception
**Goal:** Fix stage2_scraping._scrape_source credentialed fallback: only fall through to credentialed scrape when deterministic scrape succeeded but returned 0 events — not when it raised an exception (network timeout, parse crash).
**Created:** 2026-06-19
**Intent:** Prevent credentialed scraping from being invoked unnecessarily when the deterministic scraper fails with an exception, ensuring the fallback is only used when it may actually help (zero events returned, not a crash).
**Backlog-ref:** 128

## Tasks
- [x] Added deterministic_raised flag to _scrape_source: set True in except clause, credentialed fallback now only runs when not deterministic_raised. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Add a boolean `deterministic_raised = False` before the try block, set it to `True` inside the except clause. This separates "scraper raised" from "scraper returned 0 events" without changing any other control flow.

- [x] Guard was implemented together with the flag in task 1: condition on line 336 is already 'if not events and not deterministic_raised'. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Change the condition on line 331 from `if not events:` to `if not deterministic_raised and not events:` so that `_try_credentialed_scrape` is only called when the deterministic scrape completed without raising and returned an empty list.

- [x] Added TestCredentialedFallbackGate with two tests: one verifying _try_credentialed_scrape is NOT called when deterministic raises RuntimeError, one verifying it IS called when deterministic returns empty list. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tests/test_stage2_scraping.py
  - Approach: Add a test that patches one of the deterministic scraper helpers (e.g. `_run_ical_scraper`) to raise `RuntimeError` and asserts that `_try_credentialed_scrape` is never called; also add a complementary test where the deterministic scraper returns `[]` (no exception) and asserts that `_try_credentialed_scrape` IS called.

## Notes
Constraints: none

Bug location: `stage2_scraping.py` lines 306-334 — the `except Exception as exc` block sets `scraper_error` but leaves `events = []`, and the subsequent `if not events:` check cannot distinguish the two cases.

Key files:
- `/Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage2_scraping.py` — contains `_scrape_source` (line 260)
- `/Users/niclasl/src/hockey/tests/test_stage2_scraping.py` — existing scraping tests (903 lines)

## Acceptance Criteria
- [ ] When a deterministic scraper raises an exception inside _scrape_source, _try_credentialed_scrape is not called.
- [ ] When a deterministic scraper returns an empty list without raising, _try_credentialed_scrape is called as the fallback.
- [ ] pytest passes with no regressions after the fix is applied.
- [ ] The result dict returned by _scrape_source contains the deterministic scraper error when an exception is raised and no credentialed error is produced.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Added deterministic_raised flag to _scrape_source: set True in except clause, credentialed fallback now only runs when not deterministic_raised.
**Rationale:** Simple flag addition as prescribed in the plan; no alternatives needed.
**Findings:** Credentialed fallback now correctly skips when deterministic scraper raised an exception, only triggering on clean zero-event returns.
LESSONS: none
**Files:** stage2_scraping.py (+7/-2)
**Commit:** a56d1c8 (hockey)

### 2026-06-19 — Guard was implemented together with the flag in task 1: condition on line 336 is already 'if not events and not deterministic_raised'.
**Rationale:** Already implemented as part of the prior task — no separate change needed.
**Findings:** Condition already reads 'if not events and not deterministic_raised' in stage2_scraping.py.
LESSONS: none
**Files:** no files changed (already done in task 1)
**Commit:** [pending — fill after commit]

### 2026-06-19 — Added TestCredentialedFallbackGate with two tests: one verifying _try_credentialed_scrape is NOT called when deterministic raises RuntimeError, one verifying it IS called when deterministic returns empty list.
**Rationale:** Direct patch approach as described in plan approach sub-bullet — patches _run_ical_scraper and _try_credentialed_scrape.
**Findings:** Both tests pass: fallback skipped on exception, fallback invoked on clean empty return.
LESSONS: none
**Files:** tests/test_stage2_scraping.py (+48)
**Commit:** [pending — fill after commit]
