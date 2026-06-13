# Plan: Manual organizer adjustment loop for final season plans
**Goal:** Organizers can lock or ban dates, pin specific tournaments, and force or exclude host clubs, then re-run the final plan/export with those constraints preserved.
**Created:** 2026-06-13
**Intent:** Let the operator make last-mile season-plan corrections without losing the rest of the generated schedule.
**Backlog-ref:** 70

## Tasks
- [x] Persist manual adjustment metadata on the plan and through checkpoint round-trips
  - Files: tournament_scheduler/models.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage4_helpers.py, tournament_scheduler/pipeline/tournament_updater.py, tests/test_stage3_planning.py, tests/test_stage4_export.py, tests/test_tournament_updater.py
  - Approach: add a lightweight manual-adjustments field to SeasonPlan, serialize it in Stage 3 checkpoints, and keep it intact when loading/writing updated plans so later runs can preserve lock/ban/pin/host preferences.
- [x] Implement a manual adjustment workflow that applies locked dates, banned dates, pinned tournaments, and host-club rules
  - Files: tournament_scheduler/pipeline/manual_adjustment_workflow.py, tournament_scheduler/pipeline/tournament_updater.py, tests/test_manual_adjustment_workflow.py
  - Approach: build a small workflow around the existing plan/updater helpers that skips pinned or locked tournaments, moves mutable tournaments off banned dates, reapplies host-club rules, and then recalculates season metrics plus conflict/fairness checks before export.
- [x] Wire the workflow into the CLI as a repeatable organizer adjustment command
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/update_command.py
  - Approach: add an adjust subcommand with repeatable flags for lock/ban/pin/force-host/exclude-host, run the workflow, write the updated checkpoint, and re-export the season plan.
- [x] Add regression coverage for adjustment persistence and plan rewriting
  - Files: tests/test_tournament_updater.py, tests/test_manual_adjustment_workflow.py, tests/test_stage4_export.py
  - Approach: cover checkpoint round-trips, host-rule application, banned-date rescheduling, and export of an adjusted plan so the loop stays stable.

## Notes
- Preserve existing stage/checkpoint semantics; only add a small metadata payload so older plans still load.
- Manual adjustments should be treated as operator intent, not a new optimization pass.
- Keep conflict/fairness validation noisy enough that locked or pinned violations are obvious before export.

## Acceptance Criteria
- [ ] The system preserves manual adjustments when a plan is written to Stage 3 and reloaded from Stage 4.
- [ ] The CLI can lock or ban dates, pin tournaments, and force or exclude host clubs, then save an updated plan and export files.
- [ ] Adjusted plans are revalidated for conflicts and fairness before export.

## Log




### 2026-06-13 — Add regression coverage for adjustment persistence and plan rewriting
**Done:** Added regression tests for Stage 3 manual-adjustment preservation, Stage 4 round-tripping, updater checkpoint reloads, workflow-based banned-date moves/host rewrites, and the end-to-end adjust CLI path.
**Rationale:** The new manual adjustment loop needs coverage across persistence, workflow behavior, and CLI wiring to catch regressions in future plan edits.
**Findings:** Tests confirm manual_adjustments survive checkpoint writes, the workflow moves banned tournaments and reapplies host rules, and the new adjust command runs through export successfully.
**Files:** tests/test_stage3_planning.py; tests/test_stage4_export.py; tests/test_tournament_updater.py; tests/test_manual_adjustment_workflow.py
**Commit:** not committed
### 2026-06-13 — Wire the workflow into the CLI as a repeatable organizer adjustment command
**Done:** Added an adjust subcommand to rvv-miniputt and a reusable AdjustmentCommand that merges repeatable lock/ban/pin/host flags, runs the manual-adjustment workflow, writes the checkpoint, logs the change, and re-exports the plan.
**Rationale:** Operators need a direct command-line loop for last-mile plan edits, not just the underlying workflow API.
**Findings:** The CLI now recognizes repeatable adjustment flags and uses the same checkpoint filename as the pipeline state manager. An end-to-end CLI test exercises the new adjust command and export path.
**Files:** tournament_scheduler/cli/rvv_cli.py; tournament_scheduler/cli/update_command.py; tests/test_manual_adjustment_workflow.py
**Commit:** not committed
### 2026-06-13 — Implement a manual adjustment workflow that applies locked dates, banned dates, pinned tournaments, and host-club rules
**Done:** Added a manual-adjustment workflow that reads persisted organizer rules, moves mutable tournaments off banned dates, reapplies host-club preferences, and recalculates plan metrics/conflicts before export.
**Rationale:** The final-plan loop now has one place to apply operator intent without rewriting the rest of the planning pipeline.
**Findings:** The workflow reuses existing cancellation/date-suggestion logic for safe moves, uses a new host-club setter in TournamentUpdater, and recalculates fairness metadata from the adjusted plan. A focused regression test covers the move + host rewrite path.
**Files:** tournament_scheduler/pipeline/manual_adjustment_workflow.py; tournament_scheduler/pipeline/tournament_updater.py; tests/test_manual_adjustment_workflow.py
**Commit:** not committed
### 2026-06-13 — Persist manual adjustment metadata on the plan and through checkpoint round-trips
**Done:** Added persistent manual-adjustment metadata to SeasonPlan and plan checkpoint serialization, and preserved it across Stage 3 reruns and Stage 4 reloads.
**Rationale:** Manual organizer constraints need to survive checkpoint rewrites so later adjustment/export passes can keep the operator's chosen locks and pins.
**Findings:** Stage 3 now reads any prior manual_adjustments before overwriting the checkpoint, then writes them back onto the regenerated plan. Stage 4 and TournamentUpdater both round-trip the same payload. Regression tests cover Stage 3 preservation, Stage 4 deserialization, and updater checkpoint reloads.
**Files:** tournament_scheduler/models.py; tournament_scheduler/pipeline/stage3_helpers.py; tournament_scheduler/pipeline/stage3_planning.py; tournament_scheduler/pipeline/stage4_helpers.py; tournament_scheduler/pipeline/tournament_updater.py; tests/test_stage3_planning.py; tests/test_stage4_export.py; tests/test_tournament_updater.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
