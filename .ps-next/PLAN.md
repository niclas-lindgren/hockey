# Plan: Simplify season-plan report page
**Goal:** Make `season_plan_report.html` understandable for club and organizer review with clear top-level status, actions, summaries, and secondary diagnostics.
**Created:** 2026-06-15
**Intent:** Organizers should be able to see whether the plan is usable, what needs attention, and what each club should review without interpreting raw fairness metrics first.
**Backlog-ref:** 102

## Tasks
- [ ] Restructure the report page around organizer questions
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/report_overview.html, tournament_scheduler/html/templates/page_template.html, tournament_scheduler/html/templates/__init__.py, tournament_scheduler/html/templates/styles.css
  - Approach: Add a report-only overview fragment above existing diagnostics with Norwegian executive summary, status cards, prioritized warnings/actions, per-age-group summary, and per-club review summary. Generate fragment HTML from `HtmlExporter` using existing plan/fairness/travel/club data; keep detailed metrics below as secondary diagnostics.
- [ ] Cover report structure with regression assertions
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
<!-- pi-next appends entries here after each task -->
