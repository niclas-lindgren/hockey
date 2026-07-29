# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| The exported site navigation contains a Påmeldte lag/Input view alongside Sesongplan, Skrapede kalendere, and Rapport when input.html exists. | PASS | `HtmlExporter.export(..., input_html_path=...)` renders `input.html` navbar links via `$INPUT_NAV_ITEM$`; `calendar_viewer.generate_html()` links `input.html` when present. Covered by `tests/test_stage4_export.py::test_input_html_generated_and_linked_when_input_workbook_configured`. |
| Stage 4 generates input.html during normal export from a configured input workbook and records it in output_files. | PASS | `stage4_export.run()` calls `input_viewer.generate_html()` when Stage 1 config has an existing `input_path` and writes `output_files["input_html"]`. Covered by focused pytest. |
| Only explicitly whitelisted worksheets are exported publicly; initially only Lag. | PASS | `PUBLIC_SHEET_WHITELIST == ("Lag",)` and `assert_public_sheet()` rejects internal sheet names. Covered by `tests/test_input_workbook.py`. |
| Aldersgrupper, Innstillinger, Kilder, Datopreferanser, and input.xlsx contents/filename are not exposed by input.html or the public Pages bundle. | PASS | `read_public_teams()` reads only `Lag`; `input_viewer` does not reference the workbook filename; `pages_bundle.DEFAULT_ALLOWED_FILENAMES` includes `input.html` but not `input.xlsx`. Covered by focused pytest. |
| The Lag data renders as read-only HTML with Norwegian headings, totals, search/filter controls, and responsive/mobile-compatible layout. | PASS | `input_viewer.generate_html()` emits Norwegian headings (`Påmeldte lag`, `Klubb`, `Lag`), club/team/age totals, filter controls (`filterAge`, `filterClub`, `filterSearch`), and mobile CSS. Covered by `tests/test_input_viewer.py`. |
| run: pytest tests/test_input_viewer.py tests/test_input_workbook.py tests/test_stage4_export.py tests/test_pages_publish.py -q | PASS | 81 passed. |
| GitHub issue #32 is closed after verification passes. | PASS | `gh issue close 32 ...` succeeded; `gh issue view 32 --json state` reports `CLOSED`. |

## Additional checks
- PASS: `pi_next_quality_gate(level="quick")` — 1129 passed, 1 skipped, 26 deselected.
- NOTE: `pi_next_quality_gate(level="full")` exposed unrelated pre-existing slow/integration failures around the canonical workbook/real roster having no registered teams; focused issue coverage and the quick gate passed.
