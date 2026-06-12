# Plan: Export regression coverage for stage 4 outputs
**Goal:** Add regression tests that lock down the generated season-plan HTML and timestamped export layout.
**Created:** 2026-06-12
**Intent:** Prevent future regressions in the user-facing export bundle without changing the export behavior itself.
**Backlog-ref:** 65

## Tasks
- [x] Add HTML regression assertions for the generated season plan page
  - Files: tests/test_stage4_export.py
  - Approach: Extend the Stage 4 export tests to inspect the rendered `season_plan.html` and verify the age-group filter options are derived from the plan data, the theme toggle/export-link assets are present, and no accidental debug-dashboard or emoji regression strings appear in the output.
- [x] Add timestamped export layout assertions for all generated file formats
  - Files: tests/test_stage4_export.py
  - Approach: Exercise `run(..., timestamped_export=True)` and assert that the Excel, iCal, CSV, HTML, and Spond exports are written into the same timestamped subfolder, with matching flat copies still created at the export root when enabled.

## Notes
The current Stage 4 pipeline already exports Excel, iCal, CSV, HTML, and Spond files. These tests should stay offline and use the existing minimal plan fixture.

## Acceptance Criteria
- [ ] `pytest tests/test_stage4_export.py` passes with coverage for HTML regressions and timestamped multi-format exports.
- [ ] Show that the generated `season_plan.html` uses plan-driven filter options and includes the expected export/theme UI.
- [ ] Show that `xlsx`, `ics`, `csv`, `html`, and `spond` land in the same timestamped export directory.

## Log


### 2026-06-12 — Add timestamped export layout assertions for all generated file formats
**Done:** Added a timestamped Stage 4 regression test that checks Excel, iCal, CSV, HTML, and Spond outputs are all emitted under one timestamped subdirectory and that the root-level flat copies are still written.
**Rationale:** This protects the export bundle layout that downstream tooling relies on, including the Spond export added to the pipeline.
**Findings:** The existing Stage 4 implementation already writes all main artifacts into a single timestamped folder and copies them back to the export root when timestamped_export=True; the test now locks that contract down.
**Files:** tests/test_stage4_export.py (+1 test)
**Commit:** not committed
### 2026-06-12 — Add HTML regression assertions for the generated season plan page
**Done:** Added a regression test that renders the Stage 4 HTML export and checks age-group filter options, theme toggle assets, export-link assets, and absence of debug/emoji regressions.
**Rationale:** This locks down the user-facing HTML output without changing export behavior, and it uses a multi-age-group fixture so the filter options are proven to come from the plan data.
**Findings:** The generated page already includes plan-driven filter options and export links; the only adjustment needed was to assert the sorted age-group label order generically. I also confirmed the HTML export is produced through the existing Stage 4 pipeline path.
**Files:** tests/test_stage4_export.py (+1 test helper, +1 regression test, +imports/fixture support)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
