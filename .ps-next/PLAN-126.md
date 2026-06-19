# Plan: Fix scrape_age always empty in stage4_export.py
**Goal:** Fix scrape_age always empty in stage4_export.py by switching from read_stage to read_envelope for the SCRAPING stage so updated_at is accessible.
**Created:** 2026-06-19
**Intent:** updated_at lives in the envelope wrapper, not the data payload, so read_stage silently drops it and scrape_age is always empty in the exported HTML.
**Backlog-ref:** 126

## Tasks
- [x] Replaced read_stage(StageName.SCRAPING) with read_envelope(StageName.SCRAPING) and extracted data from the envelope wrapper; updated_at is now read from the envelope top level. — 2026-06-19
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: On line 156, replace `state.read_stage(StageName.SCRAPING)` with `state.read_envelope(StageName.SCRAPING)`. The envelope dict contains updated_at at the top level, so the existing `.get("updated_at", "")` on line 167 will now resolve correctly.
- [x] Audited all scraping_ckpt usages in stage4_export.py; confirmed task 1 already correctly separates scraping_ckpt (data payload) from scraping_envelope (wrapper) so sources and blocked go through the data dict and updated_at goes through the envelope. — 2026-06-19
  - Files: tournament_scheduler/pipeline/stage4_export.py
  - Approach: Audit all usages of `scraping_ckpt` in stage4_export.py; any access to data payload fields (e.g. events list) must be redirected to `scraping_ckpt["data"]` since read_envelope returns the full envelope, not the payload directly.
- [ ] Add or update tests to cover scrape_age population from envelope updated_at
  - Files: tests/test_stage4_export.py
  - Approach: Write a test that constructs a fake pipeline state with a known updated_at in the SCRAPING envelope, runs the export stage, and asserts that the returned pipeline_meta contains a non-empty scrape_age string matching the expected elapsed time format (e.g. "Xm siden").

## Notes
Constraints: none

Root cause: `state.read_stage(stage)` returns `envelope["data"]` only. `updated_at` is a top-level envelope field. Switching to `state.read_envelope(stage)` returns the full dict including `updated_at`, `status`, `stale`, and `data`. After the switch, payload fields previously accessed directly from `scraping_ckpt` must be accessed via `scraping_ckpt["data"]`.

Key files:
- `tournament_scheduler/pipeline/stage4_export.py` — lines 156, 167-177 (read and compute scrape_age)
- `tournament_scheduler/pipeline/state.py` — read_stage vs read_envelope implementations
- `tournament_scheduler/html/html_exporter.py` — consumes scrape_age from pipeline meta (no change needed)

## Acceptance Criteria
- [ ] When stage4_export.py processes a scraping stage envelope with a valid updated_at timestamp, the pipeline_meta dict returned contains a non-empty scrape_age value.
- [ ] The scrape_age value produced by stage4_export.py matches the elapsed time between the scraping envelope's updated_at and the export time, formatted as "Xm siden", "Xt siden", or "Xd siden".
- [ ] Running pytest on the test suite passes with no regressions in pipeline state or export tests.
- [ ] stage4_export.py calls state.read_envelope(StageName.SCRAPING) rather than state.read_stage(StageName.SCRAPING) to obtain the scraping checkpoint.
- [ ] The HTML output produced by html_exporter.py contains a non-empty scrape_age value in the Data-alder metrics group when the scraping stage has a valid updated_at in its envelope.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Replaced read_stage(StageName.SCRAPING) with read_envelope(StageName.SCRAPING) and extracted data from the envelope wrapper; updated_at is now read from the envelope top level.
**Rationale:** read_envelope returns the full wrapper dict including updated_at; read_stage only returns the data payload, silently dropping updated_at
**Findings:** scrape_age now resolves correctly because updated_at is accessible from the envelope wrapper
LESSONS: updated_at lives in the envelope wrapper, not the data payload; always use read_envelope when you need metadata fields like updated_at
**Files:** stage4_export.py (+4/-3)
**Commit:** 4852389 (hockey)

### 2026-06-19 — Audited all scraping_ckpt usages in stage4_export.py; confirmed task 1 already correctly separates scraping_ckpt (data payload) from scraping_envelope (wrapper) so sources and blocked go through the data dict and updated_at goes through the envelope.
**Rationale:** Task 1 implementation was complete and correct; scraping_ckpt already points to envelope['data'] for payload fields
**Findings:** All downstream accesses to data payload fields (sources, blocked) correctly use scraping_ckpt; updated_at correctly uses scraping_envelope
LESSONS: none
**Files:** no files changed (audit only)
**Commit:** [pending — fill after commit]
