# Plan: Consolidate team config — single source of truth
**Goal:** `start_date`, `end_date`, `age_groups`, `parallel_games`, and `sources` live only in `input.json`; `stage1_config.json` stores only computed fields (`teams`, `round_length_minutes`) plus an `input_path` reference, and all downstream consumers merge them transparently.
**Created:** 2026-06-11
**Intent:** Stop the duplication and potential drift between `input.json` and `.pipeline/stage1_config.json`. Without this, changing a value in one but not the other silently produces inconsistent pipeline runs.
**Backlog-ref:** 55

## Tasks
- [x] Modify `stage1_config.py` — store only computed fields + `input_path` in checkpoint, and add `load_effective_config()` merger
  - Files: tournament_scheduler/pipeline/stage1_config.py
  - Approach: Change `_parse_config()` to exclude `start_date`, `end_date`, `age_groups`, `parallel_games`, `sources`. Add `input_path` field. In `run()`, pass the input path through. Add a module-level function `load_effective_config(state, input_path=None)` that reads the Stage 1 checkpoint, gets `input_path`, loads `input.json`, and merges the computed fields on top. The merged dict matches the current shape so downstream code sees no API change.

- [x] Update downstream Python stages to use `load_effective_config()`
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/tools/calendar_compare.py
  - Approach: Replace `state.read_stage(StageName.CONFIG)` calls (where the result is used as `config`) with `load_effective_config(state)` from `stage1_config`. For `calendar_compare.py`, update `_load_sources()` to prefer input.json directly.

- [x] Update TypeScript `pipeline-helpers.ts` `estimateDataVolume()` for new checkpoint shape
  - Files: .pi/lib/pipeline-helpers.ts
  - Approach: `estimateDataVolume` currently accesses `data.sources`, `data.age_groups` from the Stage 1 checkpoint. After the change these keys won't be in the Stage 1 data dict. Keep the function robust — check for the fields and fall back gracefully if absent. The Stage 1 checkpoint will have `teams` and `round_length_minutes` which are fine.

## Notes
- `round_length_minutes` IS computed (federation defaults + overrides) — it stays in the checkpoint.
- `teams` IS computed (file expansion) — it stays in the checkpoint.
- `age_groups` is a special case: when not present in input.json, it's derived from teams in Stage 1. The merger should handle this: use input.json's `age_groups` if present, otherwise fall back to the `age_groups` that Stage 1 computed (which would need to be stored in the checkpoint).
- The TypeScript pipeline-runner.ts doesn't read Stage 1 data directly for config values — it only reads Stage 2 data for blocked/cached/sources. No changes needed there.
- The `rvv_cli.py` single-club scrape (`_cmd_scrape`) reads `cfg.get("sources")` — after the change this will come from `input.json` via the merger.

## Acceptance Criteria
- [ ] `input.json` is the only place where `start_date`, `end_date`, `age_groups`, `parallel_games`, and `sources` are defined
- [ ] `stage1_config.json` does NOT contain `start_date`, `end_date`, `age_groups`, `parallel_games`, or `sources` in its `data` envelope
- [ ] `stage1_config.json` contains `input_path`, `teams`, and `round_length_minutes` in its `data` envelope
- [ ] Pipeline stages 2, 3, and 4 can still read all config values correctly (via the merger)
- [ ] `run: python3 -m tournament_scheduler.pipeline.stage1_config --input input.json --work-dir .pipeline` succeeds
- [ ] `grep: start_date` in `.pipeline/stage1_config.json` returns 0 matches (outside the envelope metadata)
- [ ] `input.json` and `stage1_config.json` have no overlapping/duplicate configuration fields

## Log



### 2026-06-11 — Update TypeScript `pipeline-helpers.ts` `estimateDataVolume()` for new checkpoint shape
**Done:** Added `round_length_minutes` key counting to `estimateDataVolume()` for the new Stage 1 checkpoint shape. The function already handles missing fields gracefully via Array.isArray checks, so `sources` and `age_groups` being absent from Stage 1 data is safe — they'll still be counted when reading Stage 2.
**Rationale:** The function is called for all checkpoint files. After consolidation, Stage 1 data no longer has `sources`/`age_groups` arrays, but the function already uses `Array.isArray` guards so it silently skips those. Added `round_length_minutes` object-key counting as it's now a meaningful Stage 1 computed field.
**Findings:** Pre-existing test failure in `test_zero_events_blocks_source` confirmed unrelated (fails on clean main too). All other 320 tests pass.
**Files:** .pi/lib/pipeline-helpers.ts (+4)
**Commit:** not committed
### 2026-06-11 — Update downstream Python stages to use `load_effective_config()`
**Done:** Updated stage2_scraping.py, stage3_planning.py, rvv_cli.py (3 call sites), and calendar_compare.py to use load_effective_config() or read directly from input.json. Stage 2 runs successfully with the merged config.
**Rationale:** All downstream consumers now get their config through `load_effective_config()` which merges input.json (canonical) with stage1 checkpoint (computed). The API shape is unchanged — every caller still gets `start_date`, `end_date`, `age_groups`, `parallel_games`, `sources`, `teams`, `round_length_minutes`.
**Findings:** `calendar_viewer.py` reads `sources` from stage2 checkpoint, not stage1 — no change needed. `cache_manager.py` `build_from_checkpoint()` receives config from the caller (which now uses `load_effective_config`). The `calendar_compare.py` `_load_sources()` had a fallback to stage1_config.json which would now return empty — simplified to only read input.json.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+1/-1), tournament_scheduler/pipeline/stage3_planning.py (+1/-1), tournament_scheduler/cli/rvv_cli.py (+3/-3), tournament_scheduler/tools/calendar_compare.py (+1/-8)
**Commit:** not committed
### 2026-06-11 — Modify `stage1_config.py` — store only computed fields + `input_path` in checkpoint, and add `load_effective_config()` merger
**Done:** Changed `_parse_config()` to exclude duplicated fields (start_date, end_date, age_groups, parallel_games, sources) from the checkpoint. Added `input_path` field. Added `load_effective_config()` merger function that loads input.json for canonical values and merges computed fields from the checkpoint. Updated `run()` docstring. Updated CLI __main__ block to read date display from input.json directly. Stage 1 runs successfully (35 lag, 2026-09-01 til 2027-04-30) and checkpoint has 0 duplicated fields.
**Rationale:** `input.json` is now the single source of truth for human-editable config. `stage1_config.json` stores only computed outputs (teams expanded from file, round_length_minutes with federation defaults). The `load_effective_config()` merger provides backward compatibility for downstream consumers.
**Findings:** The `_parse_config` function previously parsed dates unnecessarily (only passed through strings). Removed that dead computation. The `derived_age_groups` field is only stored when input.json has no explicit `age_groups` key — avoids duplicating when it's present.
**Files:** tournament_scheduler/pipeline/stage1_config.py (+83/-43)
**Commit:** not committed
