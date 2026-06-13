# Plan: Group HTML tournament matches by round
**Goal:** The season-plan HTML tournament details pane shows each tournament's games grouped under round headings instead of one flat match list.
**Created:** 2026-06-13
**Intent:** Make per-tournament game schedules easier to scan and line up with the round-robin structure organizers already use in exports.
**Backlog-ref:** 74

## Tasks
- [x] Serialize round numbers into the HTML tournament JSON and render grouped round sections in the details pane
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/html/templates/script.js, tournament_scheduler/html/templates/styles.css
  - Approach: include each game's round number in the embedded tournament JSON, update the client-side match renderer to bucket matches and bye rows by round, add round headings/counts above each group, and style the grouped sections so they still fit the existing card layout.
- [x] Add regression coverage for round-grouped tournament details output
  - Files: tests/test_stage4_export.py
  - Approach: extend the HTML export regression test to assert the embedded script/data now carries round numbers and the grouped-round markup/labels are present, protecting the details pane from reverting to an ungrouped list.

## Notes
Existing HTML export already preserves `Game.round_number` in the model and stage 4 checkpoint; the missing piece is the HTML pane's serialized payload and renderer. Keep the rest of the timeline/filter UI unchanged.

## Acceptance Criteria
- [ ] Exported season_plan.html shows round headings for a tournament's games, with games visually grouped under their round in the details pane.
- [ ] The HTML export regression test fails if the round-grouping markup/labels disappear.

## Log


### 2026-06-13 — Add regression coverage for round-grouped tournament details output
**Done:** Added an HTML export regression test that verifies the serialized tournament payload carries round numbers and that the generated HTML includes the round-group renderer markers.
**Rationale:** The grouped-round UI is client-rendered, so the regression locks down both the embedded data shape and the renderer hooks needed to keep the details pane grouped by round.
**Findings:** The existing export tests already cover the season-plan HTML output path, making it a good place to guard this UI behavior without adding a separate browser harness.
**Files:** tests/test_stage4_export.py (+44/-0)
**Commit:** not committed
### 2026-06-13 — Serialize round numbers into the HTML tournament JSON and render grouped round sections in the details pane
**Done:** The HTML tournament details pane now serializes each game's round number and renders matches in round-grouped sections with per-round headers and bye placement.
**Rationale:** Grouping games by round matches the existing round-robin structure and makes the tournament detail pane easier to scan without changing the overall card layout.
**Findings:** The planner already carries round_number on Game objects, and bye data was already keyed by round; the missing piece was the HTML payload and client-side renderer. The updated renderer now buckets matches by round before emitting the match grid.
**Files:** tournament_scheduler/html/html_exporter.py (+1), tournament_scheduler/html/templates/script.js (+48/-12), tournament_scheduler/html/templates/styles.css (+5)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
