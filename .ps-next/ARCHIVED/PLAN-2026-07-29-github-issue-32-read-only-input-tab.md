# Plan: GitHub issue #32 read-only Input tab
**Goal:** Verify and complete GitHub issue #32 so the exported season site publishes a safe read-only Påmeldte lag/Input view from the workbook Lag sheet.
**Created:** 2026-07-29
**Intent:** Give organizers a public team-registration overview in the same exported site while preventing internal workbook sheets or the workbook file from being published.

## Tasks
- [x] Audit and finalize the Input tab implementation for issue #32
  - Files: tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/pipeline/input_viewer.py, tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/html/html_exporter.py, tournament_scheduler/pipeline/calendar_viewer.py, tournament_scheduler/pipeline/pages_bundle.py, tests/test_input_viewer.py, tests/test_input_workbook.py, tests/test_stage4_export.py, tests/test_pages_publish.py, .ps-next/PLAN.md
  - Approach: Compare the current implementation with GitHub issue #32; make any missing code/test adjustments so Stage 4 emits input.html from only the whitelisted Lag worksheet, the navigation links it alongside Plan/Calendars/Report, and the public Pages bundle includes it while excluding internal sheets and input.xlsx.
- [x] Verify acceptance and close GitHub issue #32
  - Files: tests/test_input_viewer.py, tests/test_input_workbook.py, tests/test_stage4_export.py, tests/test_pages_publish.py, .ps-next/PLAN.md
  - Approach: Run focused pytest coverage plus the pi-next quality gate; if all criteria pass, close GitHub issue #32 with a concise implementation summary.

## Notes
- Source: https://github.com/niclas-lindgren/hockey/issues/32 — [P1] Add read-only Input tab to the exported season site.
- Existing code already contains an input_viewer module, Stage 4 integration, navbar hooks, a Pages bundle allowlist entry, and regression tests. First task should verify whether any gap remains before changing source.
- The workbook itself and internal sheets (Aldersgrupper, Innstillinger, Kilder, Datopreferanser) must remain private; only Lag is whitelisted for public HTML rendering.
- `/rvv-miniputt` is a Pi slash command/tool, not a shell binary; use normal pytest checks for this verification plan.

## Acceptance Criteria
- [ ] The exported site navigation contains a Påmeldte lag/Input view alongside Sesongplan, Skrapede kalendere, and Rapport when input.html exists.
- [ ] Stage 4 generates input.html during normal export from a configured input workbook and records it in output_files.
- [ ] Only explicitly whitelisted worksheets are exported publicly; initially only Lag.
- [ ] Aldersgrupper, Innstillinger, Kilder, Datopreferanser, and input.xlsx contents/filename are not exposed by input.html or the public Pages bundle.
- [ ] The Lag data renders as read-only HTML with Norwegian headings, totals, search/filter controls, and responsive/mobile-compatible layout.
- [ ] run: pytest tests/test_input_viewer.py tests/test_input_workbook.py tests/test_stage4_export.py tests/test_pages_publish.py -q
- [ ] GitHub issue #32 is closed after verification passes.

## Log


### 2026-07-29 — Verify acceptance and close GitHub issue #32
**Done:** Ran focused and quick verification and closed GitHub issue #32 with the passing evidence.
**Rationale:** Acceptance was met by the current code and regression tests; closing the issue records the verified implementation upstream.
**Findings:** Focused pytest passed (81 tests). pi-next quick gate passed (1129 passed, 1 skipped, 26 deselected). gh issue close 32 succeeded.
**Files:** No source changes; .ps-next/PLAN.md updated for task tracking.
**Commit:** 9c04a66
### 2026-07-29 — Audit and finalize the Input tab implementation for issue #32
**Done:** Audited issue #32 against the current implementation. No source changes were needed: the code already whitelists Lag, renders input.html with Norwegian headings/totals/filters, wires Stage 4 and navbar links, includes input.html in the public Pages bundle, and covers the behavior with regression tests.
**Rationale:** The safest completion path was verification rather than rewriting working code. Existing tests directly exercise the public-sheet whitelist, Stage 4 generation/linking, internal-sheet exclusion, and Pages bundle allowlist.
**Findings:** Focused pytest passed (81 tests). pi-next quick quality gate passed (1129 passed, 1 skipped, 26 deselected).
**Files:** No source changes; .ps-next/PLAN.md updated for task tracking.
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
