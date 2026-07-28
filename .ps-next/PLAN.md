# Plan: Prevent overlapping RVV tournament intervals
**Goal:** Implement GitHub issue 27 so arena tournament intervals cannot overlap and invalid plans cannot be exported or published.
**Created:** 2026-07-28
**Intent:** The public season plan must never contain impossible same-arena schedules, especially when multiple tournaments share a date or cross midnight.

## Tasks
- [x] Add reusable arena interval conflict detection
  - Files: tournament_scheduler/arena_conflicts.py, tests/test_arena_conflicts.py
  - Approach: Create helpers that convert tournaments plus per-age-group round lengths into full datetime intervals, detect same-arena overlaps including overnight spans, and format structured collision dictionaries with arena/date/tournament IDs/intervals.
- [x] Reserve planned tournament intervals during host slot assignment
  - Files: tournament_scheduler/host_assignment.py, tournament_scheduler/scheduler.py, tournament_scheduler/utils/slot_finder.py, tournament_scheduler/season_planner.py, tests/test_season_planner.py, tests/test_slot_finder.py
  - Approach: Extend slot lookup to merge already-planned reservation events with scraped bookings, remove the 16:00 clamp fallback, and derive `arena_day_collisions` from final planned intervals instead of clearing them.
- [ ] Block export and public publish on hard arena conflicts
  - Files: tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/operator_action.py, tests/test_stage4_export.py, tests/test_operator_action.py
  - Approach: Re-check final plan collisions before Stage 4 output and before `operator publish --confirm-public`; fail with actionable arena/date/tournament/interval evidence when any hard conflict remains.
- [ ] Update rules/reporting docs for arena interval validation
  - Files: docs/rvv-miniputt-rules-report.md, tournament_scheduler/rules_report.py
  - Approach: Document that arena conflicts are full interval overlaps, not just same-day counts, and ensure rules report wording matches the new hard validation behavior.

## Notes
GitHub issue 27 reports Jarhallen overlap on 2026-09-05 from run-2026-07-27T22-12-10. Current code sequences same-arena same-day tournaments after assignment, clamps overflow back to 16:00, then clears `arena_day_collisions`; `host_assignment.find_slot_for_tournament` checks scraped bookings but not in-memory tournament reservations. Fairness gate already has a fail-severity `arena_day_collisions` metric, so the main defect is preserving/deriving collisions accurately and blocking downstream export/publish.

## Acceptance Criteria
- [ ] Return tournament occupancy as full date/time intervals, including tournaments crossing midnight.
- [ ] Reserve each planned tournament interval so subsequent placement checks both source bookings and already planned tournaments.
- [ ] Remove the fallback that clamps overflowing start times back to 16:00.
- [ ] Return a hard planning failure when no valid slot remains after re-host/reschedule attempts.
- [ ] Update `arena_day_collisions` from the final plan; do not clear detected collisions unconditionally.
- [ ] Fail export/fairness validation on any arena interval overlap.
- [ ] Return a publish failure for `operator publish --confirm-public` while any hard scheduling conflict remains.
- [ ] Include a useful error containing arena, date, tournament IDs, and overlapping intervals.
- [ ] Create a regression test with three tournaments where the third cannot fit after the first two.
- [ ] Create boundary tests that cover adjacent non-overlapping intervals and overnight tournaments.

## Log


### 2026-07-28 — Reserve planned tournament intervals during host slot assignment
**Done:** Slot lookup now considers already-planned tournament reservations in addition to scraped bookings; same-arena sequencing no longer clamps overflow to 16:00 and final plans preserve interval/overflow/unplaced arena conflicts.
**Rationale:** Reservations prevent later tournaments from being placed into intervals already occupied by the in-memory plan, while hard conflict records make any remaining impossible placement fail the existing fairness gate.
**Findings:** Targeted tests passed. Full quick pytest currently fails in unrelated tests/test_stage2_scraping.py::TestUnifiedCache::test_stale_cache_triggers_rescrape because the mocked Outlook scraper is not called.
**Files:** tournament_scheduler/host_assignment.py; tournament_scheduler/scheduler.py; tournament_scheduler/season_planner.py; tournament_scheduler/utils/slot_finder.py; tests/test_season_planner.py; tests/test_slot_finder.py
**Commit:** not committed
### 2026-07-28 — Add reusable arena interval conflict detection
**Done:** Added arena_conflicts helpers for full datetime tournament occupancy intervals and structured same-arena overlap reports, including overnight spans.
**Rationale:** A shared utility lets planning, export, and publish gates enforce the same hard arena-overlap rule instead of duplicating same-day checks.
**Findings:** Existing model durations expose matchday occupancy via setup-buffer-aware matchday_duration_minutes; collisions can be reported additively without changing SeasonPlan schema.
**Files:** tournament_scheduler/arena_conflicts.py (+155); tests/test_arena_conflicts.py (+100)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
