# Plan: Log malformed events in _build_events_by_club
**Goal:** Add logging in stage3_helpers._build_events_by_club when malformed events are silently dropped — bare except/continue hides calendar conflicts from operators.
**Created:** 2026-06-19
**Intent:** Make calendar data quality issues visible to operators by replacing the silent bare-except in _build_events_by_club with warning-level log messages that capture the club name and exception details.
**Backlog-ref:** 129

## Tasks
- [x] Added import logging and module-level logger  logging.getLogger(__name__) to stage3_helpers.py. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage3_helpers.py
  - Approach: Import the `logging` module and add `logger = logging.getLogger(__name__)` at the module level, following the pattern used in llm_scraper.py and cancellation_workflow.py.

- [ ] Replace bare except/continue with logged warning in _build_events_by_club
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage3_helpers.py
  - Approach: Bind the caught exception to a variable (`except (KeyError, ValueError) as exc:`) and call `logger.warning("Dropped malformed event for club %r: %s — raw: %s", club_name, exc, e)` before `continue`, giving operators the club name, error, and raw event dict.

- [ ] Write unit tests for _build_events_by_club logging
  - Files: /Users/niclasl/src/hockey/tests/test_stage3_helpers.py
  - Approach: Create a new test file that patches the logger and asserts a warning is emitted (with the correct club name) when a malformed event dict (missing `datetime` key or bad ISO string) is passed to `_build_events_by_club`. Also assert that well-formed events in the same club list are still returned.

## Notes
Constraints: none

The bare `except (KeyError, ValueError): continue` block is at lines 153-154 of stage3_helpers.py. At the exception site the available context is `e` (the raw event dict from the checkpoint), `club_name` (the RVV club name string), and `exc` (the caught exception). The log level should be `warning` — this is data loss that an operator should notice in production logs, not just a debug trace.

## Acceptance Criteria
- [ ] Code search in stage3_helpers.py shows that the except block now contains a logger.warning call that includes the club name and exception details.
- [ ] Running pytest passes with a new test that asserts a warning is emitted when _build_events_by_club receives an event dict with a missing or malformed datetime field.
- [ ] The function still returns valid CalendarEvent objects for well-formed events in the same club list even when malformed events are present — no regression in return value.
- [ ] Running the pipeline with a checkpoint that contains a malformed event produces a warning-level log line that is visible in the application log output.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Added import logging and module-level logger  logging.getLogger(__name__) to stage3_helpers.py.
**Rationale:** Follows the same pattern used in llm_scraper.py and cancellation_workflow.py.
**Findings:** Logger is now available for use in _build_events_by_club and other helpers.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage3_helpers.py (+3/-0)
**Commit:** [pending — fill after commit]
