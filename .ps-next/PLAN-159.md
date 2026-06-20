# Plan: Fix stage1 verification checklist in opencode run.md
**Goal:** Fix opencode run.md: stage1 verification checklist references fields (age_groups, parallel_games, sources) that do not exist in the current stage1 checkpoint — should match what checkpoint_printer actually shows (teams, target_tournament_count, round_length_minutes, input_path)
**Created:** 2026-06-20
**Intent:** After backlog item 87 moved age_groups, parallel_games, and sources out of the stage1 checkpoint into input.json, the run.md operator guide and checkpoint_printer were not updated, so the verification step instructs operators to check fields that no longer exist.
**Backlog-ref:** 159

## Tasks
- [x] Updated stage1_config key list in _STAGE_SUMMARY_KEYS to match actual checkpoint fields: input_path, teams, round_length_minutes, target_tournament_count. — 2026-06-20
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/cli/checkpoint_printer.py
  - Approach: On line 44, replace the stage1_config key list `["teams", "age_groups", "parallel_games", "target_tournament_count", "sources"]` with `["input_path", "teams", "round_length_minutes", "target_tournament_count"]` to match the actual fields written to the stage1 checkpoint by stage1_config.py.
- [x] Updated stage1 verification checklist in run.md to check actual checkpoint fields (teams, target_tournament_count, round_length_minutes, input_path) and note that age_groups/parallel_games/sources live in input.json. — 2026-06-20
  - Files: /Users/niclasl/src/hockey/.opencode/commands/rvv-miniputt/run.md
  - Approach: Replace line 17 which says "verify: `teams` non-empty (9 RVV clubs), `age_groups` populated, `parallel_games` present, `target_tournament_count` >= 1, `sources` non-empty" with text that checks only the actual checkpoint fields: `teams` non-empty, `target_tournament_count` >= 1, `round_length_minutes` present, `input_path` set — and notes that age_groups/parallel_games/sources live in input.json.

## Notes
Constraints: none

After backlog item 87 (2026-06-11), `stage1_config.json` stores only: `input_path`, `teams`, `round_length_minutes`, `target_tournament_count`. The fields `age_groups`, `parallel_games`, and `sources` were moved to `input.json` exclusively.

Affected files confirmed:
- `/Users/niclasl/src/hockey/.opencode/commands/rvv-miniputt/run.md` line 17 — stale field list
- `/Users/niclasl/src/hockey/tournament_scheduler/cli/checkpoint_printer.py` line 44 — stale `_STAGE_SUMMARY_KEYS["stage1_config"]`

Actual stage1 checkpoint data keys (verified against `.pipeline/stage1_config.json`): `input_path`, `teams`, `round_length_minutes`, `target_tournament_count`.

## Acceptance Criteria
- [ ] The `_STAGE_SUMMARY_KEYS["stage1_config"]` list in checkpoint_printer.py contains `teams`, `round_length_minutes`, `input_path`, and `target_tournament_count`, and does not contain `age_groups`, `parallel_games`, or `sources`.
- [ ] The stage1 verification line in run.md does not contain references to `age_groups`, `parallel_games`, or `sources` as fields to check.
- [ ] The stage1 verification line in run.md contains references to `teams`, `round_length_minutes`, `target_tournament_count`, and `input_path` as the fields to verify.
- [ ] Running `python3 -m tournament_scheduler.cli.checkpoint_printer stage1` against a valid stage1 checkpoint does not print any missing-key warnings for age_groups, parallel_games, or sources.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-20 — Updated stage1_config key list in _STAGE_SUMMARY_KEYS to match actual checkpoint fields: input_path, teams, round_length_minutes, target_tournament_count.
**Rationale:** Direct replacement per plan approach; old fields age_groups, parallel_games, sources do not exist in stage1 checkpoint.
**Findings:** Fixed mismatch between displayed fields and actual stage1 checkpoint data.
LESSONS: none
**Files:** tournament_scheduler/cli/checkpoint_printer.py (+1/-1)
**Commit:** 1e52836 (hockey)

### 2026-06-20 — Updated stage1 verification checklist in run.md to check actual checkpoint fields (teams, target_tournament_count, round_length_minutes, input_path) and note that age_groups/parallel_games/sources live in input.json.
**Rationale:** Direct replacement per plan approach.
**Findings:** Checklist now accurately reflects what is stored in the stage1 checkpoint.
LESSONS: none
**Files:** .opencode/commands/rvv-miniputt/run.md (+1/-1)
**Commit:** [pending — fill after commit]
