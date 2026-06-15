# Plan: Simplify season-plan report page
**Goal:** Make `season_plan_report.html` understandable for club and organizer review with clear top-level status, actions, summaries, and secondary diagnostics.
**Created:** 2026-06-15
**Intent:** Organizers should be able to see whether the plan is usable, what needs attention, and what each club should review without interpreting raw fairness metrics first.
**Backlog-ref:** 102

## Tasks
- [x] Restructure the report page around organizer questions
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/report_overview.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/__init__.py, tournament_scheduler/html/templates/styles.css
  - Approach: Add a report-only overview fragment above existing diagnostics with Norwegian executive summary, status cards, prioritized warnings/actions, per-age-group summary, and per-club review summary. Generate fragment HTML from `HtmlExporter` using existing plan/fairness/travel/club data; keep detailed metrics below as secondary diagnostics.
- [x] Cover report structure with regression assertions
  - Files: tests/test_stage4_export.py
  - Approach: Extend existing HTML export tests to assert the report contains the new main sections above detailed diagnostics, uses plain Norwegian labels, keeps diagnostics secondary, and does not leak schedule controls.

## Notes
- Top backlog item 102 requests an information-hierarchy redesign for the generated RVV season-plan report page.
- Recent archived work already split `season_plan_report.html` from `season_plan.html`, removed schedule filters, standardized Norwegian fairness terminology, and made a static all-club summary reachable.
- Existing generated artifacts and pipeline cache files are dirty in the worktree; avoid touching export/cache/input artifacts for this plan.
- `openspec/AGENTS.md` was referenced by project instructions but is not present in this checkout.

## Acceptance Criteria
- [ ] `season_plan_report.html` shows an executive summary, clear status cards, prioritized warnings/actions, per-age-group summary, per-club review summary, and detailed tournament/diagnostic content in that order.
- [ ] Critical warnings/actions are visible before raw fairness metrics in the report HTML.
- [ ] Low-level diagnostics remain available but secondary on the report page.
- [ ] `pytest tests/test_stage4_export.py` passes.

## Log


### 2026-06-15 — Cover report structure with regression assertions
**Done:** Extended the Stage 4 HTML export regression test to assert the new report overview sections, Norwegian review labels, and ordering before raw fairness metrics.
**Rationale:** These assertions lock the intended report hierarchy so future template changes do not regress to diagnostics-first output.
**Findings:** Targeted `pytest tests/test_stage4_export.py -q` passes. Plan drift warning is expected because previous report implementation files remain uncommitted in the same working tree. Full pytest still fails in unrelated pre-existing planner tests as noted in the prior log entry.
**Files:** tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-15 — Restructure the report page around organizer questions
**Done:** Added a report-only overview above existing diagnostics with an executive answer, status cards, prioritized action list, age-group summary, club review summary, and tournament review table.
**Rationale:** The report now answers organizer questions before exposing raw fairness metrics, while keeping existing diagnostic sections below as secondary details.
**Findings:** Targeted stage4 export tests pass. Full pytest/quick gate currently fails in pre-existing season-planner/stage3 tests unrelated to report files: no plan generated for two small planner cases in tests/test_season_planner.py and tests/test_stage3_planning.py.
**Files:** tournament_scheduler/html/html_exporter.py; tournament_scheduler/html/templates/report_overview.html; tournament_scheduler/html/templates/__init__.py; tournament_scheduler/html/templates/page_template.html; tournament_scheduler/html/templates/styles.css
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
