# Plan: GitHub issue 33 activity year wheel export
**Goal:** Implement GitHub issue #33 so Stage 4 publishes normalized activity data and a standalone, embeddable activity year-wheel/list page.
**Created:** 2026-07-29
**Intent:** Make the RVV activity/year-wheel workbook publishable on GitHub Pages and WordPress without exposing the full Excel workbook or requiring browser-side XLSX parsing.

## Tasks
- [x] Add workbook activity extraction and JSON normalization
  - Files: tournament_scheduler/pipeline/activity_export.py, tests/test_activity_export.py
  - Approach: Add a small workbook reader for the intended activity table only. Support Norwegian/English header aliases for date/month/title/activity/location/type/age groups, normalize dates to ISO, infer year from activity dates, skip obvious example/help rows, and raise actionable WorkbookInputError messages with sheet and source row references for malformed dates or missing titles.
- [x] Generate the standalone activity page
  - Files: tournament_scheduler/pipeline/activity_viewer.py, tests/test_activity_viewer.py
  - Approach: Write activities.json plus activities/index.html from normalized records. Keep assets local/inline, load ../activities.json relatively, provide Norwegian labels, age-group filters, accessible activity buttons/details, chronological month-grouped list, mobile list default, year-wheel date positioning, today/next markers, and iframe height postMessage.
- [x] Integrate activity artifacts with Stage 4 export and Pages publishing
  - Files: tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/pages_bundle.py, tournament_scheduler/pipeline/pages_publish.py, tests/test_stage4_export.py, tests/test_pages_bundle.py, tests/test_operator_action.py
  - Approach: Generate activity artifacts when the configured input workbook contains an activity table, record them in the Stage 4 checkpoint, keep existing exports unchanged when no activity sheet exists, allow activities.json and activities/ through the sanitized public bundle, and make Pages fingerprint/diff/publish logic recurse into public subdirectories.
- [x] Document the WordPress embed flow and verify issue coverage
  - Files: docs/rvv-miniputt-pipeline.md, .ps-next/PLAN.md
  - Approach: Add a concise documentation section with published URLs and iframe snippet, then run targeted pytest coverage plus quick quality/safety/diff checks before marking complete.

## Notes
GitHub issue: https://github.com/niclas-lindgren/hockey/issues/33
The current input.xlsx does not contain an activity sheet, so Stage 4 must remain no-op for activities unless a supported sheet is present. Candidate public activity sheets should be intentionally narrow (for example Aktiviteter/Aktivitetsplan/Årshjul/Activities) and must not parse or expose internal workbook sheets in the browser. Existing issue #32 safeguards around input.html and workbook privacy must be preserved. When changing export/publish behavior, ensure the rules/pipeline docs mention the new artifacts.

## Acceptance Criteria
- [ ] run: python3 -m pytest tests/test_activity_export.py tests/test_activity_viewer.py tests/test_stage4_export.py tests/test_pages_bundle.py tests/test_operator_action.py -q
- [ ] grep contains: docs/rvv-miniputt-pipeline.md Aktivitetskalender
- [ ] The export pipeline reads only the intended activity table and excludes example/help data.
- [ ] It writes valid normalized activities.json and standalone activities/index.html artifacts when an activity sheet exists.
- [ ] The activity page supports date-positioned year-wheel, chronological month-grouped list, age-group filtering, keyboard/touch/mouse details, mobile list default, and responsive iframe embedding.
- [ ] Timestamped and latest Pages publishing include the activity artifacts while existing plan, calendar, report, and input exports continue to pass tests.

## Log




### 2026-07-29 — Document the WordPress embed flow and verify issue coverage
**Done:** Documented the new activity artifacts, published GitHub Pages URLs, WordPress iframe snippet, and optional postMessage height behavior in the RVV pipeline guide.
**Rationale:** The docs now tell operators how to embed the generated static activity page without exposing the workbook or requiring a WordPress plugin.
**Findings:** Targeted issue coverage passed and docs contain the required Aktivitetskalender section. Current quick gate also passes.
**Files:** docs/rvv-miniputt-pipeline.md (+22), .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-29 — Integrate activity artifacts with Stage 4 export and Pages publishing
**Done:** Integrated activity artifact generation into Stage 4 for configured input workbooks with supported activity sheets, added output_files checkpoint entries, and extended the sanitized Pages bundle/publish preview path to include activities.json plus activities/index.html recursively.
**Rationale:** Stage 4 is the single export integration point, while the public bundle remains the privacy gate before anything reaches GitHub Pages latest/runs paths.
**Findings:** Existing input workbooks without an activity sheet remain unchanged. pi_next_diff_review warned on the word 'placeholder' from existing pages_publish docstring context in a modified function, not a new TODO/FIXME placeholder implementation.
**Files:** tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/pages_bundle.py, tournament_scheduler/pipeline/pages_publish.py, tests/test_stage4_export.py, tests/test_pages_bundle.py, tests/test_operator_action.py, .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-29 — Generate the standalone activity page
**Done:** Added activity_viewer artifact generation for activities.json plus activities/index.html with a vanilla SVG year wheel, chronological list, age-group filter, accessible detail interactions, mobile list default, and iframe height messaging.
**Rationale:** A standalone static page keeps WordPress embedding lightweight and avoids browser-side workbook parsing while still providing both visual and text-first presentations.
**Findings:** The page intentionally loads ../activities.json with relative paths so it works in local exports and GitHub Pages latest/runs folders.
**Files:** tournament_scheduler/pipeline/activity_viewer.py (+373), tests/test_activity_viewer.py (+87), .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-29 — Add workbook activity extraction and JSON normalization
**Done:** Added a public activity workbook reader that detects supported activity sheets, locates the intended table, normalizes records into the issue #33 JSON shape, and writes deterministic activities.json output.
**Rationale:** Keeping extraction in a narrow pipeline helper avoids browser-side XLSX parsing and preserves existing workbook privacy boundaries by only reading supported public activity sheets.
**Findings:** The repository's current input.xlsx has no activity sheet, so activity export must stay optional until a workbook/source contains Aktiviteter/Aktivitetsplan/Årshjul-style data. URLs containing example.com must not be treated as example/help rows.
**Files:** tournament_scheduler/pipeline/activity_export.py (+340), tests/test_activity_export.py (+194), .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
