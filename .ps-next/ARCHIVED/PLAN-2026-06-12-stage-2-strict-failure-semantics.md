# Plan: Stage 2 strict-failure semantics
**Goal:** Stage 2 writes a visible FAILED checkpoint before strict failures, and the stage2 test suite passes deterministically.
**Created:** 2026-06-12
**Intent:** Make blocked-source behavior explicit for operators and keep the Stage 2 regression suite stable.
**Backlog-ref:** 61

## Tasks
- [x] Update the Stage 2 strict-failure regression and checkpoint assertions
  - Files: tests/test_stage2_scraping.py
  - Approach: Change the zero-events strict test to expect a failed checkpoint envelope on disk (status=failed, blocked source name present, inspectable error payload) instead of no checkpoint file.
- [x] Make the parallel execution regression deterministic
  - Files: tests/test_stage2_scraping.py
  - Approach: Replace the thread-count test's instant stub with a synchronized blocking stub so multiple worker threads are actually exercised before asserting parallel dispatch.

## Notes
Stage 2 already writes FAILED checkpoints on blocked strict runs in the current implementation; the main work is aligning tests with that contract and removing the flaky thread assertion. Avoid touching unrelated export deletions or the stage2 codepath unless the tests reveal a real defect.

## Acceptance Criteria
- [ ] run: pytest tests/test_stage2_scraping.py
- [ ] run: pytest
- [ ] grep: tests/test_stage2_scraping.py contains is_failed(StageName.SCRAPING)
- [ ] grep: tests/test_stage2_scraping.py contains Barrier

## Log


### 2026-06-12 — Make the parallel execution regression deterministic
**Done:** Replaced the instant thread-count stub with a synchronized barrier-based stub so the ThreadPoolExecutor test reliably exercises multiple worker threads.
**Rationale:** The old assertion was flaky because the executor could reuse a single worker when the stub returned immediately; a blocking barrier forces true parallel dispatch.
**Findings:** pytest tests/test_stage2_scraping.py and full pytest both passed after the change.
**Files:** tests/test_stage2_scraping.py
**Commit:** not committed
### 2026-06-12 — Update the Stage 2 strict-failure regression and checkpoint assertions
**Done:** Changed the zero-events strict regression to assert a FAILED checkpoint envelope exists on disk, and verified the blocked source name is persisted in the checkpoint payload.
**Rationale:** Stage 2 already writes a failed checkpoint before raising; the test should validate the contract instead of expecting no file.
**Findings:** pytest tests/test_stage2_scraping.py passed (17 passed), and the full pytest suite passed (342 passed, 1 skipped). The existing dirty stage2_scraping.py change from before this task remains unrelated to the test update.
**Files:** tests/test_stage2_scraping.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
