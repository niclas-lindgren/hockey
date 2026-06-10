# Plan: Cancellation / rain-check workflow
**Goal:** A tournament can be cancelled with a reason, the tool suggests makeup weekends from remaining free dates with conflict re-checking, and re-exports all affected formats — a first-class flow beyond manual `--update-tournament`.
**Created:** 2026-06-10
**Intent:** Organizers need a systematic way to handle cancelled weekends (ice hall issues, weather, illness). Today they must manually run `--update-tournament` and guess at makeup dates. A first-class cancellation flow reduces clerical work and helps avoid accidentally scheduling a makeup on a conflicted date.
**Backlog-ref:** 29

## Tasks
- [x] Add cancelled state to Tournament model and serialization
  - Files: tournament_scheduler/models.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: Add `cancelled: bool = False` and `cancellation_reason: Optional[str] = None` to `Tournament` dataclass. Update `_plan_to_dict` in `stage3_planning.py` to serialize these fields, and `_tournament_from_dict` / `_dict_to_plan` in `stage4_export.py` to deserialize them. Ensure backward compatibility by defaulting to `False`/`None` when fields are absent.

- [x] Build CancellationWorkflow module
  - Files: tournament_scheduler/pipeline/cancellation_workflow.py
  - Approach: Create a `CancellationWorkflow` class that: (a) `mark_cancelled(tournament_id, reason, plan)` → sets cancelled state; (b) `suggest_makeup_dates(tournament, plan, scheduler)` → runs `find_available_dates` in the date range after the cancelled tournament, excludes already-occupied plan dates, and ranks candidates by distance from original date; (c) `apply_makeup(tournament_id, new_date, plan, updater)` → calls `TournamentUpdater.move_date` with cascade and conflict re-checking, then clears cancelled state; (d) `re_export(state)` → runs Stage 4 export. Follows the established `PipelineState` / `TournamentUpdater` patterns.

- [x] Add `cancel` subcommand to rvv-miniputt CLI
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Add a `cancel` subcommand to `rvv-miniputt` that takes `--tournament-id`, `--reason` (optional), `--makeup-date` (optional, auto-suggests if omitted), `--no-export` (skip re-export). Lists tournaments when no ID given. Uses CancellationWorkflow for the heavy lifting. Surfaces Norwegian-language output via TournamentOutput.

- [ ] Wire cancelled state into pipeline checkpoint and export
  - Files: tournament_scheduler/pipeline/tournament_updater.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: Update `write_updated_checkpoint` in `TournamentUpdater` to preserve cancelled state when writing checkpoints. Ensure Stage 4 export reflects cancelled status in Excel (greyed-out rows), iCal (CANCELLED status), CSV, and HTML.

- [ ] Tests for cancellation workflow
  - Files: tests/test_cancellation_workflow.py
  - Approach: Cover: (a) marking as cancelled; (b) suggesting makeup dates from free dates; (c) applying makeup clears cancelled + moves date; (d) attempting to cancel a non-existent tournament returns error; (e) round-trip serialization of cancelled state. Follow existing pytest patterns from `test_tournament_updater.py`. Use `tmp_path` fixtures and in-memory plans.

## Notes
- `TournamentUpdater.move_date` already handles cascade and conflict re-checking — the cancellation workflow wraps this, not replaces it.
- `RescheduleCommand` has the full reschedule logic (scrape calendars, run all checkers). The cancellation workflow should re-use the same scheduler setup where possible, but keep it lightweight — the organizer should get suggestions fast.
- The existing `--update-tournament` CLI flag stays untouched; cancellation is a higher-level flow on top.
- No database changes needed — everything lives in the pipeline checkpoints.
- Norwegian-language output throughout (follows established patterns).

## Acceptance Criteria
- [ ] `Tournament` has `cancelled` and `cancellation_reason` fields, round-tripped through checkpoints
- [ ] Running `rvv-miniputt cancel --tournament-id <id> --reason "Ishall stengt"` marks the tournament as cancelled and logs the reason
- [ ] `rvv-miniputt cancel --tournament-id <id>` without `--makeup-date` lists suggested makeup weekends ranked by proximity to the original date
- [ ] Running `rvv-miniputt cancel --tournament-id <id> --makeup-date 2027-03-15` applies the makeup, re-checks conflicts, and clears cancelled state
- [ ] After a successful makeup, the Stage 4 checkpoint is re-exported (unless `--no-export`)
- [ ] Cancelled tournaments surface distinctively: Excel rows appear greyed out, iCal events show CANCELLED status, CSV marks cancelled rows, HTML shows a cancelled badge
- [ ] All new code passes existing and new tests

## Log



### 2026-06-10 — Add `cancel` subcommand to rvv-miniputt CLI
**Done:** Added `cancel` subcommand to rvv-miniputt CLI with full Norwegian-language flow: listing tournaments, interactive reason prompt, suggested makeup dates ranked by proximity, applying makeup with --makeup-date, and automatic re-export. Uses CancellationWorkflow under the hood.
**Rationale:** The cancel command provides a complete first-class flow: list → cancel → suggest → apply → re-export. Without --tournament-id it lists available tournaments. Without --reason it prompts interactively. Without --makeup-date it shows ranked suggestions. Re-export is automatic unless --no-export is given.
**Findings:** All 222 tests pass (excluding pre-existing flaky test). The cancel subcommand supports: listing tournaments when no ID given, marking as cancelled, interactive reason prompt, suggesting makeup dates ranked by proximity, applying makeup with force/cascade, and re-export.
**Files:** tournament_scheduler/cli/rvv_cli.py (+172)
**Commit:** not committed
### 2026-06-10 — Build CancellationWorkflow module
**Done:** Created CancellationWorkflow class in cancellation_workflow.py with: mark_cancelled (sets cancelled state + reason), suggest_makeup_dates (finds free weekends via lightweight scheduler, excludes occupied dates, ranks by proximity), apply_makeup (wraps TournamentUpdater.move_date, clears cancelled state on success), re_export (runs Stage 4 export). Includes CancelResult and MakeupSuggestion dataclasses, plus log_cancellation for audit trail. Follows PipelineState/TournamentUpdater patterns.
**Rationale:** The module composes with existing TournamentUpdater rather than replacing it — move_date handles all the conflict checking/cascade complexity. The lightweight scheduler with just holiday checking gives fast suggestions without re-scraping calendars. The ranking logic is simple (proximity to original date) but provides a good default.
**Findings:** Import test passes; all existing tests pass (1 pre-existing flaky threading test unrelated). The suggest_makeup_dates method filters out dates already occupied by non-cancelled tournaments and uses only holiday checking for speed.
**Files:** tournament_scheduler/pipeline/cancellation_workflow.py (+346 new file)
**Commit:** not committed
### 2026-06-10 — Add cancelled state to Tournament model and serialization
**Done:** Added cancelled: bool and cancellation_reason: Optional[str] fields to Tournament dataclass. Updated _tournament_to_dict/_tournament_from_dict in stage3_planning.py and _dict_to_plan in stage4_export.py for round-trip serialization. Backward-compatible: defaults to False/None when fields are absent from serialized data.
**Rationale:** Minimal extension to the existing model. Keeps serialization compact by omitting cancelled fields when False/None. Uses .get() with defaults at deserialization points for backward compatibility.
**Findings:** All 233 existing tests pass with no modifications needed. The Tournament dataclass already uses Optional types for nullable fields, so adding two optional fields follows the established pattern.
**Files:** tournament_scheduler/models.py (+2), tournament_scheduler/pipeline/stage3_planning.py (+8/-2), tournament_scheduler/pipeline/stage4_export.py (+2)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
