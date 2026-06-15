# Plan: Standardize Norwegian report terminology
**Goal:** Generated HTML and Excel reports use consistent Norwegian wording for fairness diagnostics without mixed English/Norwegian labels like `Fairness-justeringer` or `Rettferdighetsgate`.
**Created:** 2026-06-15
**Intent:** Make organizer-facing report language coherent and professional across export formats.
**Backlog-ref:** 95

## Tasks
- [x] Replace mixed fairness labels in HTML and Excel exporters
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/excel/plan_exporter.py
  - Approach: Rename user-facing labels/sheet titles/descriptions to consistent Norwegian terms such as `Rettferdighetskontroll` and `Rettferdighetsjusteringer`, while leaving internal class/CSS identifiers unchanged unless user-visible.
- [x] Update regression tests for standardized terminology
  - Files: tests/test_stage4_export.py, tests/test_plan_exporter.py, tournament_scheduler/html/templates/scores.html
  - Approach: Adjust existing Stage 4/plan-exporter assertions to require the new Norwegian labels and explicitly reject the old mixed labels; update the shared score template label if tests reveal stale report wording.

## Notes
Backlog item #95 targets generated report terminology only. Keep internal code identifiers like `fairness_gate` and CSS classes stable to avoid unnecessary churn. `openspec/AGENTS.md` was not present in this repo.

## Acceptance Criteria
- [ ] Generated report HTML contains `Rettferdighetskontroll` and `Rettferdighetsjusteringer` on `season_plan_report.html`.
- [ ] Generated Excel workbook contains `Rettferdighetsjusteringer` instead of `Fairnessjusteringer` for sheet/title text.
- [ ] Tests pass with `pytest tests/test_stage4_export.py`.
- [ ] Source no longer contains user-facing strings `Fairness-justeringer`, `Rettferdighetsgate`, or `Fairnessjusteringer`.

## Log


### 2026-06-15 — Update regression tests for standardized terminology
**Done:** Updated Stage 4 and plan-exporter regression tests for the standardized Norwegian fairness labels, and fixed the shared score template label exposed by those tests.
**Rationale:** Tests now assert the new organizer-facing terms and build old mixed labels dynamically to avoid reintroducing exact stale strings into source text.
**Findings:** Plan drift reported the exporter files from the prior completed task in the combined working diff; current-task work added tests and the shared score template needed for report output.
**Files:** tests/test_stage4_export.py; tests/test_plan_exporter.py; tournament_scheduler/html/templates/scores.html; prior exporter diffs retained
**Commit:** not committed
### 2026-06-15 — Replace mixed fairness labels in HTML and Excel exporters
**Done:** Replaced user-facing mixed English/Norwegian fairness labels in HTML diagnostics and Excel workbook sheet/title text with Norwegian terms.
**Rationale:** Kept internal identifiers and CSS classes stable while standardizing organizer-facing terminology.
**Findings:** Source exporter labels no longer include the targeted old mixed terms; tests still need assertion updates in the next task.
**Files:** tournament_scheduler/html/html_exporter.py; tournament_scheduler/excel/plan_exporter.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
