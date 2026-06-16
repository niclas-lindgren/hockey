# Plan: Collapse redundant advisory review content
**Goal:** The exported HTML report keeps a concise advisory summary, but removes the separate post-export review block when it only repeats findings already shown elsewhere.
**Created:** 2026-06-16
**Intent:** Reduce duplicated guidance in the report so the main assessment is the single source of truth, while still surfacing any genuinely new advisory notes.
**Backlog-ref:** 117

## Tasks
- [x] Refactor the review-summary renderer to expose structured findings and a compact fallback format
  - Files: tournament_scheduler/html/renderers/review.py, tournament_scheduler/html/html_exporter.py
  - Approach: Split the current HTML-only review summary into reusable data + render helpers, so the exporter can decide whether the findings add anything new beyond the main overview/judgment sections.

- [x] Collapse the report’s advisory section when the review findings are fully overlapping, and keep only a brief advisory note when needed
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/report_overview.html, tests/test_stage4_export.py
  - Approach: Compare the review findings against the existing report summary/judgment content; if they are redundant, omit the separate block entirely, otherwise render a short advisory subsection with only the unique items. Add a regression test for the collapsed HTML output.

## Notes
The current report already has a main overview plus an opinionated judgment section; the extra advisory control is only useful when it adds genuinely new signal. Keep the Norwegian wording and the current report layout intact aside from the deduplication.

## Acceptance Criteria
- [ ] Exported report HTML no longer shows a separate full advisory review block when it only repeats the main assessment.
- [ ] Exported report HTML still includes a small advisory subsection when the review finds new, non-duplicative issues.
- [ ] Relevant HTML export tests pass.

## Log


### 2026-06-16 — Collapse the report’s advisory section when the review findings are fully overlapping, and keep only a brief advisory note when needed
**Done:** Added a collapsed advisory regression test and kept the report’s advisory block in compact form when the review adds no unique signal.
**Rationale:** The exporter now renders a short advisory note instead of the full review panel whenever the review findings are fully covered by the main overview/judgment sections.
**Findings:** A dedicated regression test now checks the compact review panel path. The exporter chooses the compact rendering when review findings have no unique non-overlapping warnings. Existing .ps-next/HISTORY.md changes predated this task, and the report template did not need markup changes.
**Files:** tests/test_stage4_export.py (+12), tournament_scheduler/html/html_exporter.py (+8/-1), tournament_scheduler/html/renderers/review.py (+carryover from task 1)
**Commit:** not committed
### 2026-06-16 — Refactor the review-summary renderer to expose structured findings and a compact fallback format
**Done:** Added structured review-summary analysis and a compact fallback renderer so the exporter can collapse redundant advisory output.
**Rationale:** The review panel needed reusable data so the export layer can decide when the advisory block is genuinely new versus repeating the main overview/judgment.
**Findings:** The report already had the needed advisory content; the new helper now classifies findings into overlapping vs unique topics and the compact path keeps a short advisory note instead of a full block. Existing working-tree changes in .ps-next/HISTORY.md predated this task.
**Files:** tournament_scheduler/html/renderers/review.py (+146/-0), tournament_scheduler/html/html_exporter.py (+8/-1)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
