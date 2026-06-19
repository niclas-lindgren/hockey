# Plan: Move calendar heatmap above the fold in the report
**Goal:** Move the calendar heatmap immediately after the hero block in the report — it is the fastest way to see the season shape at a glance but currently appears well below the fold.
**Created:** 2026-06-19
**Intent:** Surface the season-shape heatmap at the top of the report so organizers see the full calendar density without scrolling past cards, actions, and tables.
**Backlog-ref:** 139

## Tasks
- [x] Separated heatmap_html from diagnostics_html in _report_overview_html; added $REPORT_HEATMAP$ placeholder to the template immediately after the hero block. — 2026-06-19
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: In `html_exporter.py`, split the `diagnostics_html` concatenation (line ~535) so `heatmap_html` is assigned its own `parts` key (e.g. `$REPORT_HEATMAP$`) instead of being bundled inside `REPORT_DIAGNOSTICS` alongside `team_stats_html` and `travel_stats_html`.

- [x] Already completed as part of task 1 — $REPORT_HEATMAP$ was inserted on line 13 of report_overview.html immediately after the hero block closing tag. — 2026-06-19
  - Files: tournament_scheduler/html/templates/report_overview.html
  - Approach: Insert `$REPORT_HEATMAP$` as a new section directly after the closing tag of the hero block (before `$REPORT_STATUS_CARDS$`), so the heatmap renders first in the visual flow without scrolling.

- [ ] Wire the new placeholder in html_exporter.py parts dict
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Add `"$REPORT_HEATMAP$": heatmap_html` to the `parts` dict in `_render_page` (or equivalent assembly point) and verify `heatmap_html` is still passed through correctly when `include_diagnostics` is False (render empty string).

- [ ] Update regression test assertions for report HTML structure
  - Files: tests/test_stage4_export.py
  - Approach: Update any test that checks the order or presence of heatmap content in the rendered HTML so it expects the heatmap to appear before (not after) status cards and other report sections.

## Notes
Constraints: none

Codebase context:
- `tournament_scheduler/html/html_exporter.py` line ~216: `heatmap_html` built from `heatmap.html` template; line ~535: bundled into `diagnostics_html` with `team_stats_html` + `travel_stats_html`; line ~549: injected as `$REPORT_DIAGNOSTICS$`.
- `tournament_scheduler/html/templates/report_overview.html`: hero block first, then `$REPORT_STATUS_CARDS$`, then priority actions, rule transparency, age group summary, club review, advisory, tournament table, and `$REPORT_DIAGNOSTICS$` last (line ~91).
- The placeholder substitution system is plain `$KEY$` string replacement — no Jinja2.

## Acceptance Criteria
- [ ] The generated `season_plan_report.html` contains the heatmap section before the status cards section in document order.
- [ ] The `report_overview.html` template has a `$REPORT_HEATMAP$` placeholder that appears immediately after the hero block and before `$REPORT_STATUS_CARDS$`.
- [ ] The `REPORT_DIAGNOSTICS` value in `html_exporter.py` no longer contains `heatmap_html` — it is injected via a separate placeholder.
- [ ] Running `pytest tests/test_stage4_export.py` passes with the updated report structure.
- [ ] The generated HTML report shows the calendar heatmap without the team stats or travel stats sections appearing above it.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Separated heatmap_html from diagnostics_html in _report_overview_html; added $REPORT_HEATMAP$ placeholder to the template immediately after the hero block.
**Rationale:** Straightforward split — heatmap was concatenated as third item in diagnostics_html string; removed it from there and added a dedicated replacement key and template slot.
**Findings:** Heatmap now has its own template placeholder and appears right after the hero block; diagnostics section only contains team_stats and travel_stats.
LESSONS: none
**Files:** html_exporter.py (+3/-1), report_overview.html (+2/-0)
**Commit:** b6d77b7 (hockey)

### 2026-06-19 — Already completed as part of task 1 — $REPORT_HEATMAP$ was inserted on line 13 of report_overview.html immediately after the hero block closing tag.
**Rationale:** Task was performed atomically with the preceding extraction task.
**Findings:** Placeholder confirmed at line 13 of report_overview.html, between hero block and card-grid.
LESSONS: none
**Files:** tournament_scheduler/html/templates/report_overview.html (already staged in prior commit)
**Commit:** [pending — fill after commit]
