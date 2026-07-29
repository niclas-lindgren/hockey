# Plan: Marker-based activity season overview
**Goal:** Refine the public RVV activity calendar into a compact marker-based Sesongsløp with normalized activity data, accessible details, mobile list fallback, and no legacy year-wheel view.
**Created:** 2026-07-29
**Intent:** GitHub issue #40 reports that the current date-scaled timeline still uses wide event cards and legacy/ambiguous data fields, making the WordPress embed hard to scan and maintain.

## Tasks
- [x] Normalize activity export schema and categories
  - Files: tournament_scheduler/pipeline/activity_export.py, tests/test_activity_export.py
  - Approach: Add central canonical category vocabulary and raw-value mapping; export `schema_version`, `category`, `category_label`, `category_code`, and validation warnings while keeping useful `type` compatibility; keep `age_groups` independent of browser title parsing and never synthesize an `Alle` age-group lane.
- [ ] Replace timeline cards/year wheel with compact marker overview and accessible overlay details
  - Files: tournament_scheduler/pipeline/activity_viewer.py, tests/test_activity_viewer.py
  - Approach: Remove year-wheel controls/SVG/code/styles; render Sesongsløp as point markers with stable category code/shape/color, deterministic collision stacking, keyboard chronological order, accessible labels, overlay dialog/drawer details with focus restoration, and mobile default list view.
- [ ] Update docs and run focused verification
  - Files: docs/rvv-miniputt-pipeline.md, tests/test_activity_viewer.py, tests/test_activity_export.py
  - Approach: Document the normalized activity contract, category vocabulary, marker/list view hierarchy, WordPress embed behavior, and run targeted pytest coverage for activity export/viewer.

## Notes
- Source: GitHub issue #40, https://github.com/niclas-lindgren/hockey/issues/40
- Existing implementation lives in `tournament_scheduler/pipeline/activity_export.py` and `tournament_scheduler/pipeline/activity_viewer.py` from issues #33/#38.
- Preserve deterministic standalone HTML output and relative `../activities.json` loading for timestamped exports and `latest/activities/`.
- Do not parse XLSX in the browser or add a WordPress/plugin runtime dependency.
- An unrelated untracked workbook `Årshjul for aktiviteter.xlsx` existed before this plan and must not be modified.

## Acceptance Criteria
- [ ] `pytest tests/test_activity_export.py tests/test_activity_viewer.py` passes.
- [ ] `activities.json` records contain separate normalized `date`, `age_groups`, `category`, `title`, and `location` fields plus documented category metadata/warnings.
- [ ] The generated activity page contains no `yearWheel`, `wheelView`, or `Årshjul` view controls.
- [ ] The generated activity page renders compact `.timeline-marker` controls, not wide `.timeline-item` cards, with deterministic stack offsets and accessible labels.
- [ ] The generated activity page defaults to a month-grouped list on mobile and uses an overlay dialog for details without consuming timeline layout width.
- [ ] `docs/rvv-miniputt-pipeline.md` documents the marker-based Sesongsløp, category vocabulary, no synthetic `Alle` lane, and WordPress iframe behavior.

## Log

### 2026-07-29 — Normalize activity export schema and categories
**Done:** Added schema_version 2 activity export data with central category vocabulary, legacy raw-category mappings, category metadata on each activity, deterministic unknown fallback warnings, and explicit ALL handling for all-age activities.
**Rationale:** Normalizing during export keeps the browser renderer from inferring category/age-group semantics from display titles and gives the marker view stable codes/labels to render.
**Findings:** Existing tests inferred age groups from title-only legacy rows, so the exporter still supports that compatibility path while explicit malformed age-group values now warn instead of becoming an Alle lane.
**Files:** tournament_scheduler/pipeline/activity_export.py, tests/test_activity_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
