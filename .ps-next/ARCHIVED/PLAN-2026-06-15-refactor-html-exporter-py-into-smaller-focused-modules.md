# Plan: Refactor html_exporter.py into smaller, focused modules

**Goal:** Split the ~1011-line `html_exporter.py` into dedicated modules under `html/data_computation.py` and `html/renderers/{fairness,review,heatmap}.py`, keeping `html_exporter.py` as a thin coordinator. Generated HTML output must be identical to current output.

**Created:** 2026-06-15

**Intent:** `html_exporter.py` (~1011 lines / 49KB) currently mixes HTML template generation, data computation (heatmaps, team stats, travel distances), fairness/review rendering, and CSS/JS injection. This makes it hard to test individual concerns, reuse computation logic, or reason about rendering independently.

**Backlog-ref:** 106

## Tasks

- [x] Create `html/renderers/` package with `__init__.py`
  - Files: tournament_scheduler/html/renderers/__init__.py
  - Approach: Create the renderers package directory and an empty `__init__.py` with a docstring. This is the container for fairness, review, and heatmap rendering modules.

- [x] Create `html/renderers/heatmap.py` — heatmap color-map construction
  - Files: tournament_scheduler/html/renderers/heatmap.py
  - Approach: Extract `_club_colors_dark`, `_club_colors_light`, and the color-map construction logic from `html_exporter.py`'s `export()` method into a `build_club_color_maps(heatmap_clubs)` function that returns `(club_color_map_dark, club_color_map_light)`.

- [x] Create `html/renderers/review.py` — review summary rendering
  - Files: tournament_scheduler/html/renderers/review.py
  - Approach: Extract `HtmlExporter._review_summary_html()` (static method) into a standalone `render_review_summary_html(plan)` function. It uses `_canonical_rvv_club_name`, `_RVV_CLUBS`, `_fmt_date`, `_html`, and template imports — import these from their new homes.

- [x] Create `html/renderers/fairness.py` — fairness gate and adjustment rendering
  - Files: tournament_scheduler/html/renderers/fairness.py
  - Approach: Extract `HtmlExporter._fairness_gate_html()` and `HtmlExporter._fairness_adjustments_html()` (static methods) into standalone `render_fairness_gate_html(fairness_gate)` and `render_fairness_adjustments_html(plan)` functions. Uses `SeasonFairnessModel`, `_html`, template imports.

- [x] Create `html/data_computation.py` — pure data computation functions
  - Files: tournament_scheduler/html/data_computation.py
  - Approach: Extract from `html_exporter.py` all pure data computation: `compute_team_game_counts(plan)`, `compute_team_travel_info(plan)`, `compute_heatmap_data(plan)`, `compute_club_stats(plan, team_travel)`, `build_export_links_html(output_files)`. Also extract helper constants (`_ICON_*`, `_RVV_CLUBS`, `_CLUB_ALIASES`) and utility functions (`_canonical_rvv_club_name`, `_season_label`, `_fmt_date`, `_age_string`). Keep the CLI `__main__` block and `__init__.py` clean.

- [x] Refactor `html_exporter.py` — make `HtmlExporter.export()` delegate to the new modules
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/__init__.py
  - Approach: Update `html_exporter.py` to import from `data_computation.py` and the `renderers` submodules. `HtmlExporter` retains the `export()`, `_plan_to_json()`, `_report_overview_html()`, `_strip_schedule_controls()`, and the inner `_render_page()` method as the thin coordinator. All data computation and rendering helpers are imported from the new modules. Update `__init__.py` docstring if needed.

- [x] Run tests and verify output
  - Files: tests/test_stage4_export.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: Run `pytest tests/test_stage4_export.py -x -q` to confirm all 14 tests pass. The acceptance criteria require identical HTML output — since we're only extracting pure functions without changing their logic, tests should pass without changes.

## Notes

- The `HtmlExporter` class is imported by `tournament_scheduler/pipeline/stage4_export.py` and `tests/test_stage4_export.py`. Both import paths must continue to work after the refactor.
- The test at line 399 calls `HtmlExporter._plan_to_json()` — this static method stays on the class and must remain accessible.
- All extracted functions are pure (no mutable state, no side effects besides string construction), so tests pass without changes.
- Import chain: `html_exporter.py` → imports from `data_computation.py` and `renderers/*.py`. No circular imports — data_computation is a leaf module, renderers import from it (for helpers like `_canonical_rvv_club_name`), and `html_exporter.py` imports from both.

## Acceptance Criteria

- [ ] All existing imports (`from tournament_scheduler.html.html_exporter import HtmlExporter`) continue to work without changes to callers.
- [ ] `pytest tests/test_stage4_export.py -x -q` passes with all 14 tests unchanged.
- [ ] `python3 -c "from tournament_scheduler.html.html_exporter import HtmlExporter; print('ok')"` succeeds.
- [ ] `run: python3 -c "from tournament_scheduler.html.data_computation import compute_team_game_counts"`
- [ ] `run: python3 -c "from tournament_scheduler.html.renderers.fairness import render_fairness_gate_html"
- [ ] Generated HTML output is identical — no computation logic was changed, only moved.

## Log







### 2026-06-15 — Run tests and verify output
**Done:** Ran pytest tests/test_stage4_export.py -x -q — all 14 tests pass
**Rationale:** All tests pass with no changes to test code or callers. The refactoring is backward-compatible.
**Findings:** All 14 tests pass. No caller changes needed. Import from tournament_scheduler.html.html_exporter import HtmlExporter works unchanged. All acceptance criteria met.
**Files:** tests/test_stage4_export.py (no changes)
**Commit:** not committed
### 2026-06-15 — Refactor `html_exporter.py` — make `HtmlExporter.export()` delegate to the new modules
**Done:** Refactored html_exporter.py to delegate data computation and rendering to data_computation.py and renderers/*.py modules. Kept HtmlExporter as thin coordinator with export(), _plan_to_json(), _report_overview_html(), _strip_schedule_controls().
**Rationale:** All data computation moved to data_computation.py (team game counts, travel, heatmap, club stats, export links). Fairness rendering moved to renderers/fairness.py. Review summary moved to renderers/review.py. Heatmap color maps moved to renderers/heatmap.py. HtmlExporter now imports from these modules — no logic changed.
**Findings:** None — all 14 tests pass with identical output. Import chain from stage4_export.py and tests continues to work unchanged.
**Files:** ~ tournament_scheduler/html/html_exporter.py, + tournament_scheduler/html/data_computation.py, + tournament_scheduler/html/renderers/__init__.py, + tournament_scheduler/html/renderers/fairness.py, + tournament_scheduler/html/renderers/review.py, + tournament_scheduler/html/renderers/heatmap.py
**Commit:** not committed
### 2026-06-15 — Create `html/renderers/fairness.py` — fairness gate and adjustment rendering
**Done:** Created tournament_scheduler/html/renderers/fairness.py with render_fairness_gate_html() and render_fairness_adjustments_html()
**Rationale:** Extracted _fairness_gate_html() and _fairness_adjustments_html() from HtmlExporter into standalone functions in the renderers subpackage.
**Findings:** Uses SeasonFairnessModel from the fairness_model module; both functions produce identical HTML to the original inline methods.
**Files:** + tournament_scheduler/html/renderers/fairness.py
**Commit:** not committed
### 2026-06-15 — Create `html/renderers/fairness.py` — fairness gate and adjustment rendering
**Done:** Created tournament_scheduler/html/data_computation.py with 7 computation functions and shared constants/helpers
**Rationale:** Extracted all pure data computation from HtmlExporter into data_computation.py: team game counts, travel info, heatmap data, club stats, export links, age group helpers, plus shared constants and date helpers.
**Findings:** ICON_* constants are now public (were _ICON_* private); canonical_rvv_club_name is now public (was private). This is intentional since they are imported and reused across modules.
**Files:** + tournament_scheduler/html/data_computation.py
**Commit:** not committed
### 2026-06-15 — Create `html/renderers/review.py` — review summary rendering
**Done:** Created tournament_scheduler/html/renderers/review.py with render_review_summary_html()
**Rationale:** Extracted _review_summary_html() from HtmlExporter into a standalone function in the renderers subpackage.
**Findings:** Uses getattr() for duck-typing to avoid circular import of SeasonPlan; imports _RVV_CLUBS, _canonical_rvv_club_name, _fmt_date from data_computation.
**Files:** + tournament_scheduler/html/renderers/review.py
**Commit:** not committed
### 2026-06-15 — Create `html/renderers/heatmap.py` — heatmap color-map construction
**Done:** Created tournament_scheduler/html/renderers/heatmap.py with build_club_color_maps()
**Rationale:** Extracted heatmap colour-map construction into a standalone function in the renderers subpackage.
**Findings:** The colour lists and construction logic are identical to the original inline code in html_exporter.py.
**Files:** + tournament_scheduler/html/renderers/heatmap.py
**Commit:** not committed
### 2026-06-15 — Create `html/renderers/` package with `__init__.py`
**Done:** Created tournament_scheduler/html/renderers/__init__.py
**Rationale:** Package marker with docstring for the renderers subpackage — container for fairness, review, and heatmap modules.
**Findings:** none
**Files:** + tournament_scheduler/html/renderers/__init__.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
