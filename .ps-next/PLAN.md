# Plan: Earliest tournament start at 10:00
**Goal:** Generated tournaments should never start before 10:00.
**Created:** 2026-06-16
**Intent:** Push the default and computed tournament start window later so the season plan matches the organizer's earliest acceptable start time.

## Tasks
- [ ] Raise generated tournament start times to 10:00 minimum
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/scheduler.py, tournament_scheduler/conflict_checkers/timeslot_checker.py, tournament_scheduler/utils/slot_finder.py, tests/test_season_planner.py
  - Approach: Update the planner fallback start time and arena-slot search lower bound to 10:00, keep conflict-checker messaging aligned, and adjust regression tests that assert the default generated start time.

## Notes
The change should affect generated plans, not manually constructed test fixtures or explicit caller-provided times. Keep the slot-finder helper consistent with the planner defaults so future call sites do not drift.

## Acceptance Criteria
- [ ] Newly generated tournaments have `start_time` at or after `10:00`.
- [ ] The planner fallback no longer uses `09:00`.
- [ ] Relevant tests pass with the updated default.

## Log
<!-- pi-next appends entries here after each task -->
