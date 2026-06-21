# Plan: Fix crash in suggest_makeup_dates when scheduler fails
**Goal:** Fix crash in cancellation_workflow.py ~line 230-234 — result.detailed_exclusions and set difference both used without None guard; crashes if the scheduler fails
**Created:** 2026-06-21
**Intent:** Prevent suggest_makeup_dates from crashing with NameError when _make_lightweight_scheduler() raises before result is assigned, so the cancellation workflow degrades gracefully instead of propagating an unhandled exception.
**Backlog-ref:** 170

## Tasks
- [x] Wrapped _make_lightweight_scheduler() call and find_available_dates in a single try/except block; result initialised to None before the block to prevent NameError on scheduler construction failure. — 2026-06-21
  - Files: tournament_scheduler/pipeline/cancellation_workflow.py
  - Approach: In suggest_makeup_dates, initialise result = None before the try block, then wrap the _make_lightweight_scheduler() call (line 211) and the find_available_dates call together in a single try/except so that any scheduler initialisation failure is caught and logged, matching the existing exception-handling pattern for find_available_dates.

- [x] Confirmed existing None guards on lines 229 and 233 are sufficient; SchedulingResult.detailed_exclusions always defaults to [] so result.detailed_exclusions is never None when result is truthy. Added or [] fallback as extra defensive measure. — 2026-06-21
  - Files: tournament_scheduler/pipeline/cancellation_workflow.py
  - Approach: Confirm that the guards `set(result.available_dates) if result else set()` on line 229 and `(result.detailed_exclusions if result else [])` on line 234 cover all cases where result is None after the broadened try/except; add `or []` fallback to detailed_exclusions access if result is truthy but detailed_exclusions is unexpectedly falsy.

- [x] Added two new test cases in TestSuggestMakeupDates: one for _make_lightweight_scheduler raising RuntimeError and one for find_available_dates raising RuntimeError, both confirming suggest_makeup_dates returns [] without crashing. — 2026-06-21
  - Files: tests/test_cancellation_workflow.py
  - Approach: Add two new test cases in the existing test file: one that patches _make_lightweight_scheduler to raise an exception (verifying the method returns an empty list without crashing), and one that patches find_available_dates to raise (confirming the same graceful-return behaviour), following the MagicMock/patch patterns already used in the file.

## Notes
Constraints: none

Root cause: _make_lightweight_scheduler() on line 211 of cancellation_workflow.py is not inside the try/except block that guards find_available_dates (lines 218-226). If scheduler construction raises (e.g. missing import or misconfiguration), result is never assigned and lines 229/234 raise NameError.

Lines 229 and 234 already have correct `if result else` guards for the find_available_dates failure path; the only missing guard is for the scheduler-construction failure path.

tournament_updater.py line 793 wraps sched_result.detailed_exclusions inside a try/except — same defensive pattern to follow here.

SchedulingResult.detailed_exclusions is typed as List[Tuple[date, str]] (no Optional) and is never None when returned normally.

## Acceptance Criteria
- [ ] Running pytest tests/test_cancellation_workflow.py passes with no errors after the fix is applied.
- [ ] suggest_makeup_dates returns an empty list (not an unhandled exception) when _make_lightweight_scheduler raises an exception.
- [ ] suggest_makeup_dates returns an empty list (not an unhandled exception) when scheduler.find_available_dates raises an exception.
- [ ] The fix does not remove or weaken the existing None guards on lines 229 and 234.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-21 — Wrapped _make_lightweight_scheduler() call and find_available_dates in a single try/except block; result initialised to None before the block to prevent NameError on scheduler construction failure.
**Rationale:** Single unified try/except ensures any scheduler construction exception is caught and logged, matching the existing pattern for find_available_dates failures.
**Findings:** resultNone initialisation and unified try/except prevent NameError when scheduler construction fails; all 20 cancellation workflow tests still pass.
LESSONS: none
**Files:** tournament_scheduler/pipeline/cancellation_workflow.py (+3/-4)
**Commit:** pending — fill after commit

### 2026-06-21 — Confirmed existing None guards on lines 229 and 233 are sufficient; SchedulingResult.detailed_exclusions always defaults to [] so result.detailed_exclusions is never None when result is truthy. Added or [] fallback as extra defensive measure.
**Rationale:** SchedulingResult dataclass defines detailed_exclusions: List[Tuple[date,str]]  field(default_factorylist), so the truthy-result guard already ensures a list; the or [] fallback adds a belt-and-suspenders defence against any future subclass overriding the field.
**Findings:** detailed_exclusions defaults to [] in SchedulingResult so the existing guard is sufficient; or [] fallback added for extra safety.
LESSONS: none
**Files:** tournament_scheduler/pipeline/cancellation_workflow.py (+1/-1)
**Commit:** pending — fill after commit

### 2026-06-21 — Added two new test cases in TestSuggestMakeupDates: one for _make_lightweight_scheduler raising RuntimeError and one for find_available_dates raising RuntimeError, both confirming suggest_makeup_dates returns [] without crashing.
**Rationale:** none
**Findings:** Both new tests pass; total test count for test_cancellation_workflow.py increased from 20 to 22.
LESSONS: none
**Files:** tests/test_cancellation_workflow.py (+45/-0)
**Commit:** pending — fill after commit
