# Plan: Consolidate pipeline config into one input file
**Goal:** `input.json` is self-contained, with roster and calendar sources living together.
**Created:** 2026-06-13
**Intent:** Remove the split between the root pipeline config and the separate roster file so the default run input is one editable source of truth.
**Backlog-ref:** 75

## Tasks
- [x] Inline the roster into `input.json` and keep the calendar sources in the same file
  - Files: input.json, .pipeline/stage2_scraping.json, .ps-next/BACKLOG.md, .ps-next/.lock
  - Approach: Expand `documentation/input.json` club/team data into an inline `teams` list in the root config, preserve the existing dates, age groups, parallel-games, sources, and current stage-2 checkpoint state, clear the stale lock file, then validate the resulting JSON shape with the stage-1 config loader and mark the backlog item complete.

## Notes
- `tournament_scheduler.pipeline.stage1_config` already accepts either an inline team list or a roster file path, so this is a data-shape cleanup rather than a parser change.
- Leave `documentation/input.json` in place for tests/docs that intentionally reference the roster fixture.

## Acceptance Criteria
- [ ] `input.json` no longer points at `documentation/input.json`, and stage 1 accepts the file as a self-contained config.

## Log

### 2026-06-13 — Inline the roster into `input.json` and keep the calendar sources in the same file
**Done:** Expanded the root pipeline config into a self-contained `input.json` with 35 inline team entries, preserving the existing sources and season settings.
**Rationale:** This removes the split between the default pipeline input and the separate roster file, so the primary config now keeps team settings and calendar sources together as intended.
**Findings:** The stage-1 config loader already accepts inline team lists, so no parser change was needed. `tests/test_stage1_config.py` passed against the updated config.
**Files:** input.json (+35 team objects), .pipeline/stage2_scraping.json (kept matching the disabled Sandefjord source), .ps-next/BACKLOG.md (task tracking), .ps-next/.lock (stale lock cleared)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
