# Plan: HTML report export links
**Goal:** The HTML season-plan report includes downloadable links to the pre-generated Excel, CSV, and iCal exports so organizers can access all formats from one page.
**Created:** 2026-06-10
**Intent:** Tournament organizers open the HTML report first — they should be able to download Excel/CSV/iCal from there without hunting for files.
**Backlog-ref:** 26

## Tasks
- [x] Add export-links section to HTML template and HtmlExporter
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: (a) Add `$EXPORT_LINKS_HTML$` marker in the template after the score bar. Style as a row of download buttons with icons (📥 Excel, 📊 CSV, 📅 iCal). (b) Add optional `output_files: dict[str, str]` parameter to `HtmlExporter.export()`. (c) Generate download-link HTML from output_files keys: `excel`, `csv_overview`, `ical` — using relative filenames from the paths (since HTML is in the same export dir).

- [x] Pass output_files from pipeline Stage 4
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: In the Stage 4 `run()` function, after building `output_files`, pass it to `HtmlExporter().export()` via the new parameter.

## Notes
- The HTML template already has a navbar with links; the export links should be visually distinct (a prominent row of download buttons, not navbar items).
- Relative paths work because all exports go to the same directory.
- No per-team/per-age-group pre-generated data in this plan — keep scope focused on download links.
- Existing tests must continue to pass.

## Acceptance Criteria
- [ ] HTML report shows download links for Excel, CSV, and iCal when available from pipeline.
- [ ] `HtmlExporter.export()` accepts optional `output_files` and works without it (backward compatible).
- [ ] Pipeline Stage 4 passes output_files to HTML exporter.
- [ ] Existing tests pass (no regressions).

## Log
<!-- pi-next appends entries here after each task -->
