# Plan: Tournament update and rescheduling

**Goal:** Support modifying specific tournaments after the season plan is generated — drop a team from a tournament (rebalancing round-robin games) and move a tournament to a different weekend (with conflict re-checking and cascade handling).

**Created:** 2026-06-09
**Intent:** After a season plan is generated, organisers need to handle real-world changes: a team drops out, an arena becomes unavailable. This feature adds CLI and interactive support for targeted tournament modifications without regenerating the entire plan from scratch.

**Backlog-ref:** 23

## Tasks

- [x] Add `id` field to the `Tournament` model and propagate it through checkpoint serialisation
  - Files: `tournament_scheduler/models.py`, `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: Add an `id: str` field to `Tournament` with a default factory generating UUIDs (`field(default_factory=lambda: uuid.uuid4().hex[:8])`). Update `_plan_to_dict` in `stage3_planning.py` to serialise the id, and the `_tournament_from_dict` (new) helper to reconstruct it. The id should also be stored in the Stage 3 checkpoint JSON so downstream tools can reference tournaments by stable ID.

- [x] Create `tournament_updater.py` with a `TournamentUpdater` class supporting (a) team-drop and (b) date-move operations
  - Files: `tournament_scheduler/pipeline/tournament_updater.py`, `tournament_scheduler/pipeline/__init__.py`
  - Approach: Create a new module `tournament_updater.py` in the pipeline subpackage with a `TournamentUpdater` class. It reads a `SeasonPlan` from a Stage 3 checkpoint, resolves a tournament by ID, and supports two operations:
    - `drop_team(tournament_id, team_label)`: removes the team from `t.teams`, regenerates round-robin games via `SeasonPlanner.generate_round_robin_games`, and re-scores the plan (diversity, month-balance). Returns a diff summary.
    - `move_date(tournament_id, new_date, scheduler)`: updates `t.date`, re-runs conflict checking against the new date, and optionally cascades to downstream tournaments if the date is occupied. Conflict re-checking uses `TournamentScheduler.find_available_dates` with the specific tournament's date excluded. Returns a diff summary and conflict report.
    Both operations write a structured log entry (JSON) to the pipeline logs directory for traceability in `/rvv-miniputt logs`.

- [x] Add `--update-tournament` CLI flag to `tournament_scheduler.py` with tournament ID, update type (team-drop or new-date), and related options
  - Files: `tournament_scheduler.py`, `tournament_scheduler/cli/update_command.py`, `tournament_scheduler/cli/__init__.py`
  - Approach: Add a new `UpdateCommand` class in `cli/update_command.py` following the `SeasonCommand`/`RescheduleCommand` pattern. The CLI flag signature is `--update-tournament ID --team-drop TeamLabel` (drop a team) or `--update-tournament ID --new-date YYYY-MM-DD` (move date). The command reads the latest Stage 3 checkpoint from `.pipeline/`, applies the update via `TournamentUpdater`, writes a new Stage 3 checkpoint, and prints a summary (Norwegian) of what changed. Wire the flag into `tournament_scheduler.py`'s `build_arg_parser` and `main`.

- [x] Add interactive tournament update flow to `tournament_scheduler_interactive.py`
  - Files: `tournament_scheduler_interactive.py`
  - Approach: Add a new menu option "Oppdater turnering" after the season plan is generated (mode "3"). The interactive flow first checks for a Stage 3 checkpoint, lists tournaments with their IDs, dates, age groups, and teams, then lets the user select a tournament and choose: (a) drop a team — pick from the team list, or (b) flytt dato — enter a new date. Shows a diff summary and asks for confirmation before applying. Logs the operation via the pipeline logging system.

- [x] Ensure pipeline logging surfaces tournament modifications in `/rvv-miniputt logs`
  - Files: `.pi/extensions/rvv-miniputt.ts`
  - Approach: The `TournamentUpdater` already writes structured log entries to the pipeline logs directory. Extend the `/rvv-miniputt logs show <run-id>` output to display tournament-update events (type `tournament_update`) alongside stage meta and LLM interactions. Also add a `logs show latest` shorthand that shows the most recent run.

- [x] Test tournament update and rescheduling with 4 scenarios
  - Files: `tests/test_tournament_updater.py`
  - Approach: Create `tests/test_tournament_updater.py` with tests for: (1) dropping a team from a 6-team tournament generates correct round-robin games (5 teams, full round-robin), (2) dropping a non-existent team raises clear error, (3) moving a date re-checks conflicts and returns a conflict report, (4) cascading move — moving tournament A to tournament B's date updates both. Mock the `TournamentScheduler` for date-move tests.

## Notes
- Tournament IDs are 8-char hex UUIDs generated at plan creation time, stable across checkpoint writes.
- Team-drop re-generates round-robin games using the existing `SeasonPlanner.generate_round_robin_games` static method — no new game-generation code needed.
- Date-move re-runs conflict checking via `TournamentScheduler.find_available_dates` with the new date as target and the tournament's current date as excluded. If the new date has conflicts, they are surfaced but the user can still force the move with `--force`.
- Cascade handling: when moving a tournament to a date that another existing tournament already occupies, the user can opt to swap dates (the displaced tournament gets the original tournament's old date) or to re-schedule the displaced tournament on the next available free date.
- The interactive flow shows changes as a Rich diff table before applying.
- Log entries for updates go to `.pipeline/logs/<run-id>.jsonl` with type `tournament_update` so `/rvv-miniputt logs show` can display them.

## Acceptance Criteria
- [ ] A `Tournament` model has an `id` field populated during plan generation, serialised in the Stage 3 checkpoint, and reconstructable when reading a checkpoint.
- [ ] Running `python3 -m tournament_scheduler.pipeline.tournament_updater --plan <checkpoint> --tournament-id <id> --drop-team "Jar 1"` removes the team and writes an updated checkpoint.
- [ ] Running `--update-tournament <id> --new-date 2027-02-20` on the CLI entry point reads the latest checkpoint, applies the date-move with conflict re-checking, and writes an updated checkpoint.
- [ ] The interactive flow (mode "3" → "Oppdater turnering") lists tournaments from the checkpoint, accepts user selection, applies the update, and shows a Norwegian-language summary of what changed.
- [ ] `/rvv-miniputt logs show latest` displays tournament-update events when the most recent run includes them.
- [ ] All update operations are logged as `tournament_update` entries in `.pipeline/logs/` and are visible via `/rvv-miniputt logs show <run-id>`.

## Log






### 2026-06-09 — Test tournament update and rescheduling with 4 scenarios
**Done:** Created tests/test_tournament_updater.py with 10 tests covering: (1) dropping a team from 6-team tourn. produces correct 5-team round-robin (10 games, all 10 unique pairings), (2) dropping non-existent team returns non-success with descriptive message, (3) dropping too many teams (only 1 left) is rejected, (4) date move without conflicts succeeds, (5) non-weekend date is blocked without force, (6) force=True overrides non-weekend conflict, (7) plan-internal date conflict is detected, (8) cascade swaps dates between displaced tournaments, (9) no-cascade keeps both on same date, (10) checkpoint write + re-read round-trips correctly, (11) log_update writes valid JSONL.
**Rationale:** Each test covers a specific acceptance criterion from the plan. The round-robin verification (test 1) checks every pair of teams plays exactly once using Counter. A bug was found and fixed during testing: _check_date_conflicts was gated behind if self.scheduler, causing weekend/plan-internal checks to be skipped when no scheduler was available.
**Findings:** Bug fix: moved conflict checking outside the `if self.scheduler:` guard so weekend and plan-internal checks always run. 171/172 tests pass (1 pre-existing skip).
**Files:** tests/test_tournament_updater.py (+317), tournament_scheduler/pipeline/tournament_updater.py (+2/-2)
**Commit:** not committed
### 2026-06-09 — Ensure pipeline logging surfaces tournament modifications in `/rvv-miniputt logs`
**Done:** Extended /rvv-miniputt logs show to display tournament_update entries (loadTournamentUpdates loader, rendered with operation type icons and first-line summary). Added "show latest" shorthand that resolves to the most recent run log file. Updated the logs command description to mention both features.
**Rationale:** TournamentUpdater already writes structured tournament_update entries to .pipeline/logs/. The extension needed to surface them in the log display. The latest shorthand uses cwd() + .pipeline/logs/ to find the most recent file.
**Findings:** TypeScript extension compiles without syntax errors. All 36 Python tests pass.
**Files:** .pi/extensions/rvv-miniputt.ts (+40)
**Commit:** not committed
### 2026-06-09 — Add interactive tournament update flow to `tournament_scheduler_interactive.py`
**Done:** Added `run_tournament_update()` function to the interactive CLI and a new main menu option "Oppdater turnering i sesongplanen" (mode 4). The flow: lists all tournaments from the Stage 3 checkpoint with IDs, dates, age groups, arenas, teams, and game counts; lets the user select a tournament; offers team-drop or date-move with confirmation before persisting.
**Rationale:** The function follows the existing interactive patterns (ask_choice, ask_text, ask_date, ask_yes_no). Uses TournamentUpdater from the pipeline subpackage. Checks for Stage 3 checkpoint before showing the menu. All operations are confirmed before writing back. Norwegian-language throughout.
**Findings:** The interactive module imports correctly. All 36 pipeline tests pass. The update flow handles the common edge cases: no checkpoint found, invalid tournament selection, team not found, cancellation at any step.
**Files:** tournament_scheduler_interactive.py (+147)
**Commit:** not committed
### 2026-06-09 — Add `--update-tournament` CLI flag to `tournament_scheduler.py` with tournament ID, update type (team-drop or new-date), and related options
**Done:** Added --update-tournament, --team-drop, --new-date, --force, --no-cascade, and --work-dir CLI flags to tournament_scheduler.py. Created cli/update_command.py with UpdateCommand class following SeasonCommand/RescheduleCommand pattern, dispatching to TournamentUpdater and printing Norwegian-language results.
**Rationale:** The new flags follow the existing CLI pattern: parse in build_arg_parser, validate in _validate_args, dispatch in main(). UpdateCommand reads Stage 3 checkpoint, applies update via TournamentUpdater, writes back. All 36 pipeline tests pass.
**Findings:** Mutually exclusive validation works: --team-drop and --new-date cannot be used together. At least one must be specified. --update-tournament without either produces a clear error. All flag names use lowercase with hyphens (e.g. --no-cascade) matching the existing convention.
**Files:** tournament_scheduler/cli/update_command.py (+82), tournament_scheduler.py (+19)
**Commit:** not committed
### 2026-06-09 — Create `tournament_updater.py` with a `TournamentUpdater` class supporting (a) team-drop and (b) date-move operations
**Done:** Created tournament_scheduler/pipeline/tournament_updater.py with TournamentUpdater class supporting drop_team (removes team, regenerates round-robin) and move_date (conflict re-checking, cascade/swap handling). Includes CLI entry point (--tournament-id, --drop-team, --new-date, --force), structured JSON logging to pipeline logs dir, and write_updated_checkpoint for persisting modified plans.
**Rationale:** TournamentUpdater reads a SeasonPlan from the Stage 3 checkpoint, resolves tournaments by their UUID id, applies modifications in-place, and writes back. drop_team reuses the existing SeasonPlanner.generate_round_robin_games static method. move_date uses the TournamentScheduler.find_available_dates with a narrow date window for conflict re-checking. Cascade handling swaps dates between displaced tournaments.
**Findings:** The update module compiles and drop_team works correctly in smoke tests. The tournament_updater.py includes a rich CLI entry point for python3 -m invocation. Pipeline __init__.py updated to export TournamentUpdater and UpdateResult.
**Files:** tournament_scheduler/pipeline/tournament_updater.py (+371), tournament_scheduler/pipeline/__init__.py (+5)
**Commit:** not committed
### 2026-06-09 — Add `id` field to the `Tournament` model and propagate it through checkpoint serialisation
**Done:** Added `id: str` field (8-char hex UUID) to Tournament model; updated `_plan_to_dict` serialisation and added `_tournament_from_dict`/`_find_team` helpers for checkpoint round-tripping.
**Rationale:** The id field uses a UUID hex default factory so existing code that creates Tournament objects without specifying id continues to work. Serialised and deserialised through the Stage 3 checkpoint so downstream tools (updater, interactive flow) can reference tournaments by stable ID.
**Findings:** Dataclass ordering requires defaultless fields (date, arena, age_group) before defaulted field (id). All 26 pipeline tests pass.
**Files:** tournament_scheduler/models.py (+1/-1), tournament_scheduler/pipeline/stage3_planning.py (+39)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
