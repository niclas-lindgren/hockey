# Plan: Split HTML JavaScript bundles
**Goal:** `season_plan_report.html` embeds only shared/report JavaScript while `season_plan.html` keeps schedule timeline and filter code.
**Created:** 2026-06-15
**Intent:** Prevent schedule-only UI fragments and timeline/filter behavior from leaking into the diagnostics report page as the generated HTML evolves.
**Backlog-ref:** 94

## Tasks
- [x] Split the HTML template JavaScript into shared and schedule-only fragments
  - Files: tournament_scheduler/html/templates/script.js, tournament_scheduler/html/templates/script_shared.js, tournament_scheduler/html/templates/script_schedule.js, tournament_scheduler/html/templates/__init__.py
  - Approach: Move theme initialization, embedded data constants, shared helpers, diagnostic table/heatmap/dashboard behavior, and theme toggle into a shared script fragment. Move filter select population, timeline rendering, filter event listeners, match HTML rendering, and the final `render()` call into a schedule-only fragment. Keep `script.js` as a compatibility wrapper or remove schedule-specific loading from report rendering via new template exports.
- [x] Render page-specific JavaScript bundles from the HTML exporter
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/page_template.html, tests/test_stage4_export.py
  - Approach: Update `_render_page` to compose `$SCRIPT$` from shared JavaScript plus schedule JavaScript only when `include_timeline` is true. Add regression assertions that the report HTML contains shared behavior such as theme toggle data but not `filterAge`, `timeline`, `buildMatchHTML`, or schedule render code.

## Notes
- `season_plan.html` intentionally remains interactive with filters, count bar, timeline cards, and expandable match rows.
- `season_plan_report.html` should keep diagnostics, team/travel tables, heatmap, club dashboard data, and theme toggle behavior, but must not embed schedule filtering/timeline code.
- Existing tests already assert report markup excludes filters/count bar/timeline; this plan adds stronger checks for the embedded JavaScript bundle.

## Acceptance Criteria
- [ ] `pytest tests/test_stage4_export.py` passes.
- [ ] Generated `season_plan_report.html` does not contain schedule-only JavaScript identifiers `filterAge`, `timeline`, `buildMatchHTML`, or `function render()`.
- [ ] Generated `season_plan.html` still contains the timeline/filter JavaScript and existing schedule UI tests pass.

## Log


### 2026-06-15 — Render page-specific JavaScript bundles from the HTML exporter
**Done:** Composed page JavaScript from shared plus schedule-only bundles only for the schedule page, and added regression checks for report-page script contents.
**Rationale:** The report page now embeds diagnostics/theme behavior without the schedule render/filter bundle; tests lock down both absence on report and presence on season plan.
**Findings:** `page_template.html` did not need structural changes because `$SCRIPT# Plan: Split HTML JavaScript bundles
**Goal:** `season_plan_report.html` embeds only shared/report JavaScript while `season_plan.html` keeps schedule timeline and filter code.
**Created:** 2026-06-15
**Intent:** Prevent schedule-only UI fragments and timeline/filter behavior from leaking into the diagnostics report page as the generated HTML evolves.
**Backlog-ref:** 94

## Tasks
- [x] Split the HTML template JavaScript into shared and schedule-only fragments
  - Files: tournament_scheduler/html/templates/script.js, tournament_scheduler/html/templates/script_shared.js, tournament_scheduler/html/templates/script_schedule.js, tournament_scheduler/html/templates/__init__.py
  - Approach: Move theme initialization, embedded data constants, shared helpers, diagnostic table/heatmap/dashboard behavior, and theme toggle into a shared script fragment. Move filter select population, timeline rendering, filter event listeners, match HTML rendering, and the final `render()` call into a schedule-only fragment. Keep `script.js` as a compatibility wrapper or remove schedule-specific loading from report rendering via new template exports.
- [x] Render page-specific JavaScript bundles from the HTML exporter
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/page_template.html, tests/test_stage4_export.py
  - Approach: Update `_render_page` to compose `$SCRIPT$` from shared JavaScript plus schedule JavaScript only when `include_timeline` is true. Add regression assertions that the report HTML contains shared behavior such as theme toggle data but not `filterAge`, `timeline`, `buildMatchHTML`, or schedule render code.

## Notes
- `season_plan.html` intentionally remains interactive with filters, count bar, timeline cards, and expandable match rows.
- `season_plan_report.html` should keep diagnostics, team/travel tables, heatmap, club dashboard data, and theme toggle behavior, but must not embed schedule filtering/timeline code.
- Existing tests already assert report markup excludes filters/count bar/timeline; this plan adds stronger checks for the embedded JavaScript bundle.

## Acceptance Criteria
- [ ] `pytest tests/test_stage4_export.py` passes.
- [ ] Generated `season_plan_report.html` does not contain schedule-only JavaScript identifiers `filterAge`, `timeline`, `buildMatchHTML`, or `function render()`.
- [ ] Generated `season_plan.html` still contains the timeline/filter JavaScript and existing schedule UI tests pass.

 already provided a page-specific injection point; `templates/__init__.py` changed in the prior split task to export the new fragments.
**Files:** tournament_scheduler/html/html_exporter.py; tests/test_stage4_export.py; tournament_scheduler/html/templates/__init__.py
**Commit:** not committed
### 2026-06-15 — Split the HTML template JavaScript into shared and schedule-only fragments
**Done:** Added shared and schedule-only JavaScript template fragments and exported them from the template package.
**Rationale:** Separating the bundles at the template level gives the exporter a clean way to embed only page-relevant JavaScript.
**Findings:** The original script mixed shared diagnostics/theme behavior with schedule filter/timeline rendering; untracked new template files are expected for the split.
**Files:** tournament_scheduler/html/templates/__init__.py; tournament_scheduler/html/templates/script_shared.js; tournament_scheduler/html/templates/script_schedule.js
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
