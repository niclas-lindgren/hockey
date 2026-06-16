# Plan: Matchday duration and travel-aware start times
**Goal:** Tournament slots account for full matchday time, including setup buffers, and long-travel tournaments avoid overly early starts.
**Created:** 2026-06-16
**Intent:** Prevent tournaments from being scheduled into slots that are too short or too early for away teams with long travel.
**Backlog-ref:** 110

## Tasks
- [x] Add a full matchday-duration helper and use it for slot fitting
  - Files: tournament_scheduler/models.py, tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py, tournament_scheduler/utils/slot_finder.py
  - Approach: Add a helper that computes the occupied hall time from the round-robin schedule plus setup buffers, then use that required minute count when finding arena slots and when sequencing tournaments that share an arena/day.
- [x] Make slot selection prefer later starts for long-distance tournaments and add regression tests
  - Files: tournament_scheduler/scheduler.py, tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py, tournament_scheduler/models.py, tournament_scheduler/utils/slot_finder.py, tests/test_models.py, tests/test_scheduler.py, tests/test_season_planner.py
  - Approach: Let the scheduler score candidate slots against a caller-provided preferred start time, derive that preferred start from the furthest-traveling team in the tournament, and add tests covering the duration helper plus the travel-aware start-time bias.

## Notes
The existing `Tournament.duration_minutes()` API should stay stable for playtime-only calculations; the new scheduling helper can layer setup time on top without breaking older callers. Keep the default start-time behavior unchanged when travel is local or no calendar slot data is available.

## Acceptance Criteria
- [ ] Generated tournament slots only use calendar gaps that are long enough for the computed matchday duration.
- [ ] A tournament with a far-traveling visiting team shows a later start than the earliest available slot.
- [ ] Existing scheduling tests still pass.

## Log


### 2026-06-16 — Make slot selection prefer later starts for long-distance tournaments and add regression tests
**Done:** Added travel-aware preferred-start scoring to arena slot selection and backed it with regression tests for both the scheduler and the season planner.
**Rationale:** Long-distance tournaments now bias toward later slots when the host calendar offers a choice, which reduces overly early starts for traveling teams.
**Findings:** The host-assignment helper can derive travel bias from the participating teams already present in the generated games, so no new roster plumbing was needed. The scheduler now accepts a preferred start time and picks the closest fitting slot deterministically.
**Files:** tournament_scheduler/scheduler.py; tournament_scheduler/host_assignment.py; tournament_scheduler/models.py; tournament_scheduler/utils/slot_finder.py; tests/test_models.py; tests/test_scheduler.py; tests/test_season_planner.py; tournament_scheduler/season_planner.py; .ps-next/PLAN.md
**Commit:** 00a23d0
### 2026-06-16 — Add a full matchday-duration helper and use it for slot fitting
**Done:** Added a reusable matchday-duration helper, wired it into host slot fitting and same-arena sequencing, and kept the playtime-only duration API intact.
**Rationale:** Tournament occupancy now accounts for round setup/changeover time when choosing and sequencing time slots, without breaking older callers that still need playtime-only duration math.
**Findings:** A separate helper was the cleanest way to add setup time without changing existing export/end_time semantics. The planner's same-day sequencing also needed the same occupancy calculation to avoid overlaps.
**Files:** tournament_scheduler/models.py; tournament_scheduler/utils/slot_finder.py; tournament_scheduler/host_assignment.py; tournament_scheduler/season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
