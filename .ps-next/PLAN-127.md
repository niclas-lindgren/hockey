# Plan: Raise on missing tournament date in _dict_to_plan
**Goal:** Raise on missing tournament date in stage4_helpers._dict_to_plan instead of silently defaulting to date.today() — a missing date should be a clear error, not a silent wrong value.
**Created:** 2026-06-19
**Intent:** Prevent corrupt checkpoint data from silently producing plans with today's date as the tournament date, replacing a silent wrong value with a clear, traceable error.
**Backlog-ref:** 127

## Tasks
- [x] Replace silent date.today() fallback with ValueError raise in _dict_to_plan — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage4_helpers.py
  - Approach: On line 41, change `tournament_date = date.fromisoformat(date_str) if date_str else date.today()` to raise a `ValueError` with a descriptive message (e.g. "Tournament date is required but missing or empty") when `date_str` is falsy.
- [x] Add two tests asserting ValueError is raised when tournament date is missing or empty — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tests/test_stage4_export.py
  - Approach: Add a new test that calls `_dict_to_plan` with a tournament dict where the `"date"` key is absent or empty, and asserts `pytest.raises(ValueError)` with a message containing "date".
- [ ] Audit existing tests that call _dict_to_plan and fix any that omit the date field
  - Files: /Users/niclasl/src/hockey/tests/test_stage4_export.py, /Users/niclasl/src/hockey/tests/test_review_packets.py
  - Approach: Search for all `_dict_to_plan` call sites in existing tests (lines 144, 168, 447 in test_stage4_export.py and line 149 in test_review_packets.py) and ensure every tournament dict passed includes a valid `"date"` field in ISO format.

## Notes
Constraints: none

The silent default is at stage4_helpers.py line 41. Callers in stage4_export.py and html_exporter.py do not need error-handling changes — the ValueError should propagate naturally as a programming error (not a recoverable condition). Only the test layer needs updating to supply valid dates in fixture dicts and to add a negative test for the missing-date case.

## Acceptance Criteria
- [ ] When _dict_to_plan is called with a tournament dict missing the "date" key, it raises a ValueError and does not return a plan object.
- [ ] When _dict_to_plan is called with an empty string for "date", it raises a ValueError containing the word "date" in the exception message.
- [ ] Running pytest passes with no failures after all existing test fixtures are updated to include valid date fields.
- [ ] The codebase contains no remaining reference to `date.today()` as a fallback in _dict_to_plan.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Replace silent date.today() fallback with ValueError raise in _dict_to_plan
**Rationale:** Straightforward single-line change as specified in the plan
**Findings:** Changed line 41 of stage4_helpers.py to raise ValueError when date_str is falsy; existing tests pass (the test_review_command_applies_change_request_and_reexports failure pre-exists)
LESSONS: none
**Files:** stage4_helpers.py (+3/-1)
**Commit:** a7644f0 (hockey)

### 2026-06-19 — Add two tests asserting ValueError is raised when tournament date is missing or empty
**Rationale:** Two tests cover both absence and empty string; both pass
**Findings:** Added test_raises_on_missing_tournament_date and test_raises_on_empty_tournament_date to TestDictToPlan; all 5 tests in class pass
LESSONS: none
**Files:** tests/test_stage4_export.py (+12/-0)
**Commit:** [pending — fill after commit]
