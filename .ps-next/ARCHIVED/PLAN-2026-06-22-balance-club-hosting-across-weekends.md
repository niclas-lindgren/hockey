# Plan: Balance club hosting across weekends
**Goal:** The planner spreads hosting load more evenly across consecutive weekends and holiday-heavy stretches, not just month-by-month.
**Created:** 2026-06-22
**Intent:** Reduce clustered hosting burden for clubs when tournaments land back-to-back or around holiday periods.
**Backlog-ref:** 196

## Tasks
- [x] Add weekend/holiday host-load balancing to host assignment and fairness scoring
  - Files: tournament_scheduler/host_assignment.py, tournament_scheduler/warnings.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/season_planner.py
  - Approach: Track per-club recent hosting streaks and holiday-heavy hosting counts while assigning hosts; prefer clubs with lower recent weekend burden; add fairness-gate metrics and thresholds for consecutive-weekend and holiday-stretch load.
- [x] Update the rules report to explain the new weekend-balance constraints
  - Files: tournament_scheduler/rules_report.py
  - Approach: Document that host assignment now considers back-to-back weekends and holiday-heavy stretches, and surface the new fairness thresholds in the rules summary.
- [x] Add regression tests for consecutive-weekend and holiday-stretch balancing
  - Files: tests/test_season_planner.py, tests/test_stage3_planning.py
  - Approach: Cover the new fairness-gate metrics and ensure a crafted plan/host assignment triggers the new warnings when clubs are clustered across adjacent weekends or holiday periods.

## Notes
The existing fairness gate already covers month balance and same-weekend load; this plan extends the host-load view to date-adjacent weekends and holiday-heavy windows without changing the round-robin game logic.

## Acceptance Criteria
- [ ] The fairness gate reports weekend-balance metrics for consecutive weekends and holiday-heavy stretches.
- [ ] Host assignment returns a host sequence that avoids consecutive-weekend clumping when multiple valid hosts exist.
- [ ] Tests pass for the new weekend-balance regression coverage.

## Log



### 2026-06-22 — Add regression tests for consecutive-weekend and holiday-stretch balancing
**Done:** Added regression coverage for weekend host-balance scoring and fairness-gate reporting.
**Rationale:** Lock down the new host-rotation behavior so future changes do not reintroduce consecutive-weekend clumping or hide the new metrics.
**Findings:** A six-tournament alternating schedule is needed to exercise the new host-rotation preference without breaking the existing per-age-group hosting guarantees.
**Files:** tests/test_season_planner.py, tests/test_stage3_planning.py
**Commit:** not committed
### 2026-06-22 — Update the rules report to explain the new weekend-balance constraints
**Done:** Documented the new weekend-balance host-selection rules in the planner rules report.
**Rationale:** Operators need the deterministic rules summary to match the updated host-selection and fairness-gate behavior.
**Findings:** The fairness-threshold summary now surfaces the new consecutive-weekend and holiday-stretch limits automatically; the rules report adds an explicit explanation of the new host-burden balancing rule.
**Files:** tournament_scheduler/rules_report.py
**Commit:** not committed
### 2026-06-22 — Add weekend/holiday host-load balancing to host assignment and fairness scoring
**Done:** Added global weekend-balance awareness to host assignment and fairness scoring.
**Rationale:** Keep host selection proportional while reducing back-to-back weekend burden and holiday-heavy clustering.
**Findings:** Holiday-heavy weekends are derived from the Norwegian holiday calendar; consecutive-weekend load is best tracked globally per club while still preserving per-age-group host targets.
**Files:** tournament_scheduler/host_assignment.py, tournament_scheduler/warnings.py, tournament_scheduler/fairness_scoring.py, tournament_scheduler/season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
