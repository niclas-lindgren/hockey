# Plan: Season timeline activity visualization
**Goal:** Replace the default activity year-wheel experience with a data-driven `Sesongsløp` swimlane timeline that remains accessible, responsive, and embeddable.
**Created:** 2026-07-29
**Intent:** GitHub issue #38 asks for the public RVV activity export to explain the season by age-group tracks instead of forcing users to inspect unlabeled year-wheel dots.

## Tasks
- [x] Implement data-driven Sesongsløp UI and regression tests
  - Files: tournament_scheduler/pipeline/activity_viewer.py, tests/test_activity_viewer.py
  - Approach: Refactor the generated standalone HTML/JS so `Sesongsløp` is the default non-mobile view, derive swimlanes from unique `activities.json` age groups, position activities by real date across the activity year, render readable labels with same/near-date offsets, add activity-type filtering and legend cues beyond color, keep `Årshjul` secondary, default mobile to a month-grouped list, preserve accessible details/keyboard interactions, and cover issue #38 edge cases with deterministic tests.
- [x] Document WordPress embedding expectations for the responsive activity page
  - Files: docs/rvv-miniputt-pipeline.md, tests/test_activity_viewer.py
  - Approach: Update the WordPress embed section with the `Sesongsløp` default behavior, parent-side `postMessage` listener snippet, and manual theme/layout follow-up caveat for sidebar-constrained pages; assert the documented listener contract remains present in generated HTML/tests.

## Notes
- Source issue: https://github.com/niclas-lindgren/hockey/issues/38 (`[P1] Replace the default activity year wheel with an informative season timeline`).
- Reading this as a public, accessibility-critical sports-calendar embed for organizers/parents: functional analytics over decorative dashboard, restrained RVV palette, high density but readable.
- Reuse the existing static HTML/CSS/vanilla JS generator in `activity_viewer.py`; do not parse XLSX in the browser and do not add a WordPress runtime dependency.
- Keep relative `../activities.json` paths working for local, timestamped, and `latest/activities/` exports.
- Pre-existing dirty worktree note: untracked `Årshjul for aktiviteter.xlsx` was present before this plan and should not be touched or committed.

## Acceptance Criteria
- [ ] `Sesongsløp` is the default desktop/tablet view and `Liste` remains available.
- [ ] The timeline shows one lane per age group from JSON and positions activities by actual date, including leap-year-safe date math.
- [ ] Activity frequency, gaps, same/near-date overlaps, and multi-age-group activities are visible without opening every activity.
- [ ] Activity types have a visible legend and a second non-color cue.
- [ ] Activity details and all controls are operable by mouse, touch, and keyboard with meaningful accessible names.
- [ ] Age-group and activity-type filters work consistently across `Sesongsløp`, `Liste`, and retained `Årshjul`.
- [ ] Mobile shows a vertical chronological month-grouped presentation by default without nested horizontal page scrolling.
- [ ] Iframe height behavior is reliable and documented with a parent-side listener snippet.
- [ ] HTML contains data-driven deterministic rendering logic and the existing activity export artifacts still generate.
- [ ] run: pytest tests/test_activity_viewer.py tests/test_activity_export.py

## Log


### 2026-07-29 — Document WordPress embedding expectations for the responsive activity page
**Done:** Updated the RVV pipeline guide to describe the new Sesongsløp desktop/tablet default, mobile Liste default, iframe embed markup, parent-side rvv-activities-height postMessage listener, and manual WordPress theme/sidebar follow-up boundary. Added a regression assertion that the documented resize contract remains present.
**Rationale:** The generated component can stay repository-owned and plugin-free while WordPress handles only iframe sizing and optional page-template layout choices.
**Findings:** Targeted pytest tests/test_activity_viewer.py tests/test_activity_export.py passed: 20 passed. Quick pi-next quality gate passed: 1155 passed, 1 skipped, 26 deselected.
**Files:** docs/rvv-miniputt-pipeline.md (+21/-3), tests/test_activity_viewer.py (+10)
**Commit:** not committed
### 2026-07-29 — Implement data-driven Sesongsløp UI and regression tests
**Done:** Reworked the standalone activity export page so desktop/tablet defaults to Sesongsløp swimlanes, with derived age-group lanes, date-positioned activities, labels, same/near-date stacking, type legend/shape cues, type+age filters, shared details, retained Årshjul, and mobile month-grouped list default. Added deterministic regression assertions for the issue #38 rendering contract.
**Rationale:** Keeping the existing static vanilla HTML generator preserves GitHub Pages/WordPress portability and avoids new browser/runtime dependencies while making the primary view informative without interaction.
**Findings:** Quick gate ran the Python non-slow/non-integration suite successfully: 1154 passed, 1 skipped, 26 deselected. Targeted pytest tests/test_activity_viewer.py tests/test_activity_export.py passed: 19 passed.
**Files:** tournament_scheduler/pipeline/activity_viewer.py (+349/-77), tests/test_activity_viewer.py (+64/-4)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
