# Plan: Make report club summary reachable
**Goal:** The generated season-plan report shows club summary information without relying on removed schedule filters.
**Created:** 2026-06-15
**Intent:** Keep the diagnostics report internally consistent after schedule-only filter controls were removed from the report page.
**Backlog-ref:** 91

## Tasks
- [x] Replace hidden report club dashboard with a static all-club summary table
  - Files: tournament_scheduler/html/templates/club_dashboard.html, tournament_scheduler/html/templates/script_shared.js, tournament_scheduler/html/templates/styles.css
  - Approach: Change the dashboard fragment from a selector-driven hidden panel into an always-visible report section with a table body rendered from CLUB_STATS/ALL_CLUBS in shared JavaScript, and add minimal table styling.
- [x] Add report regression coverage for the static club summary
  - Files: tests/test_stage4_export.py
  - Approach: Extend the existing HTML export test to assert the report contains the all-club summary table, has no hidden club dashboard, and still has no schedule filters.

## Notes
- Backlog item allows three approaches; choose the static all-club summary because the report page intentionally no longer has schedule filters or a club selector.
- `season_plan.html` does not include diagnostics, so the static report summary should only appear on `season_plan_report.html` via the existing `include_diagnostics` path.
- `openspec/AGENTS.md` was requested by project instructions but is absent in this checkout.

## Acceptance Criteria
- [ ] `season_plan_report.html` contains a visible all-club summary table rather than an unreachable hidden club dashboard.
- [ ] `season_plan_report.html` does not contain schedule filter controls, count bar, or selector-only dashboard behavior.
- [ ] `pytest tests/test_stage4_export.py` passes.

## Log


### 2026-06-15 — Add report regression coverage for the static club summary
**Done:** Extended the Stage 4 HTML regression test to assert the report contains a static club summary table and no hidden selector-only club dashboard.
**Rationale:** The regression locks the chosen static-table behavior and prevents reintroducing unreachable club dashboard UI on the report page.
**Findings:** Targeted `python3 -m pytest -q tests/test_stage4_export.py` passed.
**Files:** tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-15 — Replace hidden report club dashboard with a static all-club summary table
**Done:** Changed the report diagnostics club section from a hidden selector-driven dashboard into an always-visible all-club summary table rendered from CLUB_STATS/ALL_CLUBS.
**Rationale:** The report page intentionally has no schedule filters, so a static aggregate table makes the club summary reachable without reintroducing report-page filter controls.
**Findings:** club_dashboard.html is ignored by the repo-wide *.html rule, so drift tools do not see it as a tracked diff; it must be force-added if committed.
**Files:** tournament_scheduler/html/templates/club_dashboard.html, tournament_scheduler/html/templates/script_shared.js, tournament_scheduler/html/templates/styles.css
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
