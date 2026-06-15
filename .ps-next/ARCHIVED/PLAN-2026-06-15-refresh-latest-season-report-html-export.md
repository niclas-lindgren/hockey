# Plan: Refresh latest season report HTML export
**Goal:** The latest exported `season_plan_report.html` reflects the current report-page templates and no longer contains stale schedule filters/count bar markup.
**Created:** 2026-06-15
**Intent:** Organizers should open the latest export folder and see the cleaned diagnostics report, not an older report artifact generated before the UI fixes.
**Backlog-ref:** 92

## Tasks
- [x] Regenerate the latest RVV Miniputt export artifacts from the existing pipeline checkpoints
  - Files: export/2026-06-15T0822/season_plan_report.html, export/2026-06-15T0822/season_plan.html, .pipeline/stage4_export.json
  - Approach: Use the RVV Miniputt extension runner to rerun Stage 4 from existing Stage 3 data (`rvv_miniputt_run --resume-from 4`) so exported HTML is produced by the current templates without reimplementing the pipeline.
- [x] Verify the refreshed report artifact no longer contains schedule-only report-page UI
  - Files: export/2026-06-15T0822/season_plan_report.html, tests/test_stage4_export.py
  - Approach: Inspect the refreshed report HTML for absence of `class="filters"`, `class="count-bar"`, `filterAge`, `Nullstill filter`, and `id="timeline"`; run the existing Stage 4 regression test that locks this behavior down.

## Notes
Latest status originally pointed Stage 4 at `export/2026-06-15T0718/season_plan_report.html`, which still contained stale schedule filter/count bar markup even though `tests/test_stage4_export.py` now asserts report pages exclude it. Rerunning Stage 4 creates a refreshed timestamped export folder, currently `export/2026-06-15T0822/`. This plan is artifact refresh/verification only unless regeneration reveals a code regression.

## Acceptance Criteria
- [ ] `export/2026-06-15T0822/season_plan_report.html` does not contain `class="filters"`, `class="count-bar"`, `filterAge`, `Nullstill filter`, or `id="timeline"`.
- [ ] `export/2026-06-15T0822/season_plan.html` still contains schedule UI such as `class="filters"`, `class="count-bar"`, and `id="timeline"`.
- [ ] `python3 -m pytest tests/test_stage4_export.py -q` passes.

## Log


### 2026-06-15 — Verify the refreshed report artifact no longer contains schedule-only report-page UI
**Done:** Verified the refreshed 2026-06-15T0822 report artifact excludes schedule-only UI while the companion season plan still includes the schedule controls.
**Rationale:** The direct artifact inspection covers the stale-markup regression, and the existing Stage 4 test suite locks the same behavior down for future exports.
**Findings:** `python3 -m pytest tests/test_stage4_export.py -q` passed (14 tests). Plan drift warning is expected because export artifacts are git-ignored and `.pipeline/stage4_export.json` was changed by the preceding regeneration task.
**Files:** export/2026-06-15T0822/season_plan_report.html (inspected), export/2026-06-15T0822/season_plan.html (inspected), tests/test_stage4_export.py (existing regression), .ps-next/PLAN.md
**Commit:** not committed
### 2026-06-15 — Regenerate the latest RVV Miniputt export artifacts from the existing pipeline checkpoints
**Done:** Reran the RVV Miniputt pipeline from Stage 4 using existing Stage 3 data, creating refreshed timestamped artifacts under export/2026-06-15T0822 and updating the Stage 4 checkpoint to point at them.
**Rationale:** Using the extension runner preserves checkpointing and structured logs while regenerating HTML from the current templates without re-scraping or re-planning.
**Findings:** Stage 4 writes a new timestamped export folder instead of overwriting the previous 2026-06-15T0718 folder; generated export files are ignored by git, while .pipeline/stage4_export.json records the new output paths.
**Files:** export/2026-06-15T0822/* (ignored artifact refresh), .pipeline/stage4_export.json, .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
