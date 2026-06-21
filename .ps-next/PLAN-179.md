# Plan: Fix calendars.html navbar link

**Goal:** Fix calendars.html navbar link — the exported calendars.html is not linked in the navbar; update the HTML generation script to include it
**Created:** 2026-06-21
**Intent:** Ensure organizers can navigate between all exported HTML pages via the navbar, including the scraped-calendars page, without broken or missing links.
**Backlog-ref:** 179

## Tasks
- [x] Moved calendars.html generation inside the HTML try-block, before HtmlExporter().export(), so output_files["calendars_html"] is set when the exporter runs. Updated html_exporter.py to use output_files.get("calendars_html") for the navbar condition instead of the broken has_scrape_data check (meta/_meta sub-dict does not contain total_events). — 2026-06-21
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: Move the calendars.html generation block (currently lines ~243-248) to run before the HtmlExporter().export() call (~line 192), so the file's existence can be used in the navbar condition.

- [x] Added optional calendars_path: str  None  None parameter to HtmlExporter.export(). Replaced output_files.get("calendars_html") check with bool(calendars_path and os.path.exists(calendars_path)) so the navbar link reflects actual file existence on disk. — 2026-06-21
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Add an optional `calendars_path: str | None = None` parameter to `export()`; replace the `has_scrape_data` condition with `bool(calendars_path and os.path.exists(calendars_path))` so the link is shown whenever the file actually exists rather than relying on meta counts.

- [x] stage4_export.py already passes _calendars_path as calendars_path to HtmlExporter().export() — implemented alongside task 2 in commit e67ba38. — 2026-06-21
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: After generating calendars.html, pass its absolute path as `calendars_path=` when calling `HtmlExporter().export()` for both season_plan.html and season_plan_report.html.

- [x] Fixed test_calendars_html_generated_when_scrape_cache_populated: moved total_events and source_count from _meta to top-level in the cache dict (stage4_export checks top-level keys), and added assertion that season_plan.html contains href"calendars.html". — 2026-06-21
  - Files: tests/test_stage4_export.py
  - Approach: In the existing test that checks for calendars.html generation (lines ~665-699), also assert that the rendered season_plan.html content contains an `href="calendars.html"` anchor, covering the previously missing link.

## Notes
Root cause: `html_exporter.export()` is called before `calendars.html` is generated in `stage4_export.py`, and its `has_scrape_data` check uses `meta.get("total_events")` / `meta.get("source_count")` which may be zero or None even when a calendars.html file is successfully produced. Fixing the order and switching to a file-existence check is the minimal, reliable fix.
Constraints: none

## Acceptance Criteria
- [ ] The generated season_plan.html contains an anchor with href="calendars.html" in its navbar when the export pipeline produces a calendars.html file.
- [ ] The generated season_plan_report.html contains an anchor with href="calendars.html" in its navbar when the export pipeline produces a calendars.html file.
- [ ] When no calendars.html is produced by the pipeline, season_plan.html does not contain a navbar link to calendars.html (no broken link).
- [ ] pytest passes with no regressions in tests/test_stage4_export.py after the changes.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-21 — Moved calendars.html generation inside the HTML try-block, before HtmlExporter().export(), so output_files["calendars_html"] is set when the exporter runs. Updated html_exporter.py to use output_files.get("calendars_html") for the navbar condition instead of the broken has_scrape_data check (meta/_meta sub-dict does not contain total_events).
**Rationale:** has_scrape_data used meta (the _meta sub-dict) which never contained total_events/source_count (those are top-level cache keys), so the navbar link was always suppressed even when calendars.html was generated.
**Findings:** Navbar now uses output_files["calendars_html"] presence as ground truth; all 657 tests pass.
LESSONS: The _meta sub-dict from ScrapedDataCache does not carry total_events/source_count — those are top-level. Do not use meta.get(total_events) as a proxy for scrape-data availability.
**Files:** html_exporter.py (+6/-6), stage4_export.py (+16/-16)
**Commit:** 7817b98 (hockey)

### 2026-06-21 — Added optional calendars_path: str  None  None parameter to HtmlExporter.export(). Replaced output_files.get("calendars_html") check with bool(calendars_path and os.path.exists(calendars_path)) so the navbar link reflects actual file existence on disk.
**Rationale:** Using os.path.exists() on the explicit path argument is more reliable than checking the output_files dict key, and avoids coupling the navbar condition to dict naming conventions.
**Findings:** All 657 tests pass. html_exporter.py now accepts explicit calendars_path rather than inferring from output_files.
LESSONS: none
**Files:** html_exporter.py (+9/-3)
**Commit:** e67ba38 (hockey)

### 2026-06-21 — stage4_export.py already passes _calendars_path as calendars_path to HtmlExporter().export() — implemented alongside task 2 in commit e67ba38.
**Rationale:** Implemented together with the calendars_path parameter addition; no separate code change needed.
**Findings:** calendars_path_calendars_path is wired at stage4_export.py line 214.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage4_export.py (+2/-0 in e67ba38)
**Commit:** 4d8a2d2 (hockey)

### 2026-06-21 — Fixed test_calendars_html_generated_when_scrape_cache_populated: moved total_events and source_count from _meta to top-level in the cache dict (stage4_export checks top-level keys), and added assertion that season_plan.html contains href"calendars.html".
**Rationale:** Test was silently broken before — total_events was inside _meta so the top-level check always returned 0 and calendars.html was never generated. Moved keys to top-level to match ScrapedDataCache.build_from_checkpoint() output format.
**Findings:** Both calendars_html tests now pass; full suite 657/657 pass.
LESSONS: test_calendars_html_generated: total_events/source_count must be at top level of cache dict, not inside _meta — stage4_export uses _scrape_cache_data.get("total_events") not _scrape_cache_data["_meta"].get("total_events")
**Files:** tests/test_stage4_export.py (+9/-4)
**Commit:** [pending — fill after commit]
