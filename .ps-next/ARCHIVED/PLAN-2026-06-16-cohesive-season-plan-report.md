# Plan: Cohesive season-plan report
**Goal:** Turn the generated plan report into one cohesive, run-specific assessment with compact metrics and granular comparisons.
**Created:** 2026-06-16
**Intent:** Remove duplicated boilerplate and make the report read like one narrative assessment instead of several overlapping blocks.
**Backlog-ref:** 119

## Tasks
- [x] Rebuild the report overview into one cohesive assessment flow
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/report_overview.html, tournament_scheduler/html/templates/review_summary.html, tournament_scheduler/html/templates/club_dashboard.html
  - Approach: Reorganize the report page so the summary, rule transparency, metrics, advisory checks, and judgment sit in one ordered structure with clear subheadings; remove redundant intro text and duplicated labels/boilerplate.
- [x] Make the report comparisons granular by club and age group where relevant
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/renderers/review.py, tournament_scheduler/html/renderers/judgment.py, tournament_scheduler/html/renderers/fairness.py, tournament_scheduler/html/templates/report_overview.html, tournament_scheduler/html/templates/review_summary.html, tournament_scheduler/html/templates/club_dashboard.html, tests/test_stage4_export.py
  - Approach: Split any aggregated comparisons into per-club/per-age-group rows or callouts so hosting, travel, load, and outlier summaries reflect the actual tournament groups instead of blended club-level totals; update the regression assertions to match the new report text.
- [x] Compact the metrics UI and align the styling with the new structure
  - Files: tournament_scheduler/html/templates/styles.css, tournament_scheduler/html/templates/report_overview.html
  - Approach: Reduce visual noise in the metrics blocks, tighten spacing and wording, and use smaller summary cards/tables so the report stays readable while carrying the same information.
- [x] Update regression tests for the new report shape
  - Files: tests/test_stage4_export.py
  - Approach: Adjust HTML assertions to the new structure, cover the granular club/age-group output, and assert that removed boilerplate/duplicate sections no longer appear.

## Notes
The current report page already has separate review, fairness, club, and judgment fragments; the main work is to merge them into one cohesive narrative without losing the existing diagnostics.

## Acceptance Criteria
- [ ] The exported report reads as one cohesive assessment with no duplicated advisory blocks.
- [ ] The report shows granular club and age-group comparisons where those metrics matter.
- [ ] Existing export tests pass with the updated report structure.
- [ ] Boilerplate phrases and overlapping report sections are removed from the diagnostics page.

## Log




### 2026-06-16 — Update regression tests for the new report shape
**Done:** Rewrote the stage 4 HTML regression assertions to follow the new single-overview report layout and the granular advisory wording, while keeping the existing export coverage intact.
**Rationale:** The HTML structure and copy changed materially, so the regression checks had to move with it to keep the new report shape locked down.
**Findings:** The stage4 export tests now validate the cohesive report overview, the new advisory section order, the per-age-group hosting wording, and the shorter metrics labels. They still confirm the schedule page keeps its timeline/filter UI while the report page stays diagnostics-only.
**Files:** tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-16 — Compact the metrics UI and align the styling with the new structure
**Done:** Tightened the report’s visual density by shortening the compact metrics labels, shrinking card/table paddings, and reducing the spacing around the assessment blocks so the same information fits into fewer vertical rows.
**Rationale:** The report now has a single cohesive structure, so the remaining polish was to make the cards, tables, and status blocks feel less bulky without hiding any information.
**Findings:** The report overview now reads more tightly on screen; metrics/score bars and fairness/review panels use smaller gaps, paddings, and labels. The report text also uses shorter metric terms ('Blokkert', 'Periode', 'Reise') to match the compact layout.
**Files:** tournament_scheduler/html/templates/styles.css; tournament_scheduler/html/templates/report_overview.html
**Commit:** not committed
### 2026-06-16 — Make the report comparisons granular by club and age group where relevant
**Done:** Added age-group-specific host/load callouts to the report’s advisory text and judgment, and tightened the fairness breakdown label so the report now reads comparisons in club/age-group terms rather than only aggregate totals.
**Rationale:** The remaining aggregated summaries were hiding which age group was actually driving the warning. Surfacing per-age-group host and load context makes the report more actionable without changing the underlying scoring.
**Findings:** Review summary now adds per-age-group host and game-spread callouts; the opinionated judgment now mentions the worst age-group load and the farthest-traveling team’s age group; fairness breakdown text is explicit about per-age-group and club context. Regression assertions were updated to match the new wording.
**Files:** tournament_scheduler/html/html_exporter.py; tournament_scheduler/html/renderers/review.py; tournament_scheduler/html/renderers/judgment.py; tournament_scheduler/html/renderers/fairness.py; tournament_scheduler/html/templates/report_overview.html; tournament_scheduler/html/templates/review_summary.html; tournament_scheduler/html/templates/club_dashboard.html; tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-16 — Rebuild the report overview into one cohesive assessment flow
**Done:** Reworked the report page so the assessment reads as one ordered flow: summary cards, priority actions, rule transparency, age-group and club summaries, advisory review, tournament table, and embedded diagnostics now live together in the report overview.
**Rationale:** The previous report split the same story across separate blocks and duplicated headings. Collapsing the core report sections into one structured overview makes the output easier to read without losing the existing diagnostics.
**Findings:** The report no longer needs separate top-level fairness/review/judgment panels; those sections are now embedded inside the overview. The old 'Kvalitetsgjennomgang' label was replaced with 'Rådgivende kontroll'. The club dashboard fragment is retained as a reusable compact component but is no longer rendered as a separate report block.
**Files:** tournament_scheduler/html/html_exporter.py; tournament_scheduler/html/templates/report_overview.html; tournament_scheduler/html/templates/review_summary.html; tournament_scheduler/html/templates/club_dashboard.html; tests/test_stage4_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
