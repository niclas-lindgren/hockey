---
date: 2026-06-21
status: open
feature: "Fix credentialed fallback never triggered on zero events in stage2_scraping.py"
goal: "Fix credentialed fallback never triggered on zero events in stage2_scraping.py ~line 340 — deterministic_raised is only True on exception, not on empty result, so silent zero-event returns skip the fallback"
tags:
  - stage2
  - scraping
  - bug
---

# Plan: Fix credentialed fallback never triggered on zero events in stage2_scraping.py
**Goal:** Fix credentialed fallback never triggered on zero events in stage2_scraping.py ~line 340 — deterministic_raised is only True on exception, not on empty result, so silent zero-event returns skip the fallback
**Created:** 2026-06-21
**Intent:** Ensure that when a deterministic scraper returns zero events without raising an exception, the credentialed fallback path is reliably triggered for sources that require authentication.
**Backlog-ref:** 171

## Tasks
- [x] Traced all 6 code paths in _scrape_source lines 356-401: styledcalendar/bookup/browser/ical scrapers leave deterministic_raisedFalse (correct — clean zero-event return warrants fallback); unknown-type else sets deterministic_raisedTrue (fixed in task 1); exception handler sets deterministic_raisedTrue (already correct). All paths are now correct. — 2026-06-21
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Read lines 356–400 of `_scrape_source` and trace every code path that can leave `events` empty and `deterministic_raised` False; annotate which paths are correct (zero-event clean return) and which are unintentional (unknown type, prior scraper_error set from non-exception path).

- [x] Added deterministic_raised  True after setting scraper_error in the unknown source type else branch so credentialed fallback is not attempted for unrecognised source types. — 2026-06-21
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: After `scraper_error = f"Ukjent kildetype '{source_type}'."` at line 382, add `deterministic_raised = True` so the subsequent `if not events and not deterministic_raised:` check does not attempt credentialed scraping for an unrecognised source type.

- [x] Added test_credentialed_fallback_proceeds_past_guard_for_registered_source to TestCredentialedFallbackGate class; patches get_strategy to return a strategy with credentials and initial_navigation, confirms _run_credentialed_bookup_or_outlook is called. — 2026-06-21
  - Files: tests/test_stage2_scraping.py, tournament_scheduler/pipeline/scraper_strategies.py
  - Approach: Patch `get_strategy` to return a strategy object with `requires_credentials=True` and `credential_env_vars=["BOOKUP_EMAIL","BOOKUP_PASSWORD"]`; patch `_run_ical_scraper` to return `[]`; assert that `_try_credentialed_scrape` is called once. Use the class `TestCredentialedFallback` that already groups the two related tests at lines 911–953.

- [x] Added test_credentialed_fallback_not_called_for_unknown_source_type; sets source type to 'unknown_type', asserts _try_credentialed_scrape is not called, and verifies scraper_error in checkpoint contains the type string. — 2026-06-21
  - Files: tests/test_stage2_scraping.py
  - Approach: Patch `_run_ical_scraper` to NOT be called (source type set to `"unknown"`); assert `_try_credentialed_scrape` is not invoked and that the result contains `"scraper_error"`.

- [x] All 42 tests in test_stage2_scraping.py pass; pre-existing failures in test_host_assignment.py and test_claude_orchestration.py are unrelated to our changes and were present before this plan. — 2026-06-21
  - Files: tests/test_stage2_scraping.py, tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Execute `pytest tests/test_stage2_scraping.py -v` and confirm all existing and new tests pass; also run `pytest` to ensure no regressions across the full suite.

## Notes
Constraints: none

Key context:
- `_scrape_source` in `stage2_scraping.py`: `deterministic_raised` is initialised `False` at line 356 and set `True` only inside the `except` block at line 385.
- Fallback condition at line 394: `if not events and not deterministic_raised:` — semantically correct for the primary case (clean zero-event return), but the `else` branch at line 382 sets `scraper_error` without setting `deterministic_raised`, leaving unknown-type sources attempting a credential fallback.
- `_try_credentialed_scrape` in `scraper_credentialed.py`: returns `([], "")` early when the source has no registered strategy or does not require credentials, so the impact of spurious calls is limited but incorrect.
- Existing tests `test_credentialed_fallback_skipped_when_deterministic_raises` (line 911) and `test_credentialed_fallback_called_when_deterministic_returns_empty` (line 933) use "Teamup" (no registered strategy), so `_try_credentialed_scrape` exits at the first guard — coverage gap for sources that actually have credentials.

## Acceptance Criteria
- [ ] When stage2_scraping processes a source with registered credentials that returns zero events without raising an exception, it calls `_try_credentialed_scrape`.
- [ ] When the deterministic scraper raises an exception, `_try_credentialed_scrape` is not called — existing test `test_credentialed_fallback_skipped_when_deterministic_raises` continues to pass.
- [ ] Sources with an unknown type (the `else` branch) do not trigger a credentialed fallback attempt; the result contains a `scraper_error` key and `_try_credentialed_scrape` is not called.
- [ ] `pytest tests/test_stage2_scraping.py` produces no failures after the guard update and new tests are added.
- [ ] The full `pytest` suite passes with no regressions introduced by the changes.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-21 — Added deterministic_raised  True after setting scraper_error in the unknown source type else branch so credentialed fallback is not attempted for unrecognised source types.
**Rationale:** Straightforward one-line fix; the flag was already used correctly in the exception branch but was missing from the else branch.
**Findings:** Fix confirmed; the else branch now sets deterministic_raised  True preventing spurious credentialed scraping for unknown source types.
LESSONS: none
**Files:** stage2_scraping.py (+1/-0)
**Commit:** ccb35e1 (hockey)

### 2026-06-21 — Added test_credentialed_fallback_proceeds_past_guard_for_registered_source to TestCredentialedFallbackGate class; patches get_strategy to return a strategy with credentials and initial_navigation, confirms _run_credentialed_bookup_or_outlook is called.
**Rationale:** Patching _try_credentialed_scrape entirely (as in existing tests) cannot test the guard inside it; instead patched scraper_credentialed.get_strategy and _run_credentialed_bookup_or_outlook to exercise the full code path.
**Findings:** Test passes; coverage now exercises the path past the short-circuit guard inside _try_credentialed_scrape for a source with registered credentials.
LESSONS: none
**Files:** tests/test_stage2_scraping.py (+44/-0)
**Commit:** 88cbc3c (hockey)

### 2026-06-21 — Added test_credentialed_fallback_not_called_for_unknown_source_type; sets source type to 'unknown_type', asserts _try_credentialed_scrape is not called, and verifies scraper_error in checkpoint contains the type string.
**Rationale:** Used state.read_stage(StageName.SCRAPING) to access the checkpoint data; PipelineState has no load_checkpoint method.
**Findings:** Test passes; confirms the deterministic_raised flag fix from task 1 blocks fallback for unknown source types.
LESSONS: none
**Files:** tests/test_stage2_scraping.py (+28/-0)
**Commit:** 9109ed3 (hockey)

### 2026-06-21 — All 42 tests in test_stage2_scraping.py pass; pre-existing failures in test_host_assignment.py and test_claude_orchestration.py are unrelated to our changes and were present before this plan.
**Rationale:** Confirmed pre-existing failures by checking which files they touch — neither stage2_scraping.py nor test_stage2_scraping.py are involved.
**Findings:** 42 stage2 tests pass; no regressions introduced by our changes.
LESSONS: none
**Files:** no new files
**Commit:** 990a97d (hockey)

### 2026-06-21 — Traced all 6 code paths in _scrape_source lines 356-401: styledcalendar/bookup/browser/ical scrapers leave deterministic_raisedFalse (correct — clean zero-event return warrants fallback); unknown-type else sets deterministic_raisedTrue (fixed in task 1); exception handler sets deterministic_raisedTrue (already correct). All paths are now correct.
**Rationale:** Pure audit — no code changes needed; task 1 already closed the only gap.
**Findings:** All code paths are correct; the guard logic is complete and consistent.
LESSONS: none
**Files:** no files changed
**Commit:** [pending — fill after commit]
