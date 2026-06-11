# Plan: Bundle exports into timestamped subfolder
**Goal:** All pipeline exports (stage4 output, calendars.html, and the input.json used for the run) end up in a single timestamped subfolder like `export/2026-06-11T2030/`, with flat copies in `export/` for convenience.
**Created:** 2026-06-11
**Intent:** Backlog #56 — currently exports are scattered: stage4 writes to `export/` (or optionally `export/<ts>/`), calendars.html goes to `export/`, and input.json is not bundled. The extension's pipeline-runner.ts doesn't propagate `--timestamped-export`, and `calendar_viewer.py::generate_html` doesn't know about timestamped subfolders.
**Backlog-ref:** 56

## Tasks
- [x] Compute timestamp in pipeline-runner.ts, pass timestamped export dir to stage4_export and calendar_viewer, and copy input.json into the bundle
  - Files: .pi/lib/pipeline-runner.ts
  - Approach: At the start of the pipeline, compute a timestamp string matching Python's `%Y-%m-%dT%H%M` format. Pass this as `--export-dir` to stage4_export (without the `--timestamped-export` flag, since we're handling the subfolder in TS). After stage4 completes, pass the same timestamped dir to calendar_viewer. After calendar_viewer completes, copy `input.json` into the timestamped folder. As a final convenience step, copy key files from the timestamped folder up to the flat `export/` directory.

- [x] Verify bundled output contains all expected files
  - Files: .pi/lib/pipeline-runner.ts
  - Approach: After the bundle is complete, verify that the timestamped folder contains: season_plan.xlsx, season_plan.ics, season_plan.csv, season_plan_overview.csv, season_plan.html, season_plan_spond.xlsx, calendars.html, and input.json. Log a summary. Ensure flat `export/` still has copies for backward compatibility.

## Notes
- Stage 4 already supports writing to any `--export-dir` path; no Python changes needed there.
- `calendar_viewer.py::generate_html` already accepts `--export-dir`; just pass the timestamped path.
- The timestamp format must match Python's `%Y-%m-%dT%H%M` (e.g., `2026-06-11T2030`) — no seconds, no timezone.
- Keep backward compatibility: flat `export/` files should still work for scripts that reference them.

## Acceptance Criteria
- [ ] run: ls export/
- [ ] grep: timestampedExportDir .pi/lib/pipeline-runner.ts
- [ ] grep: input.json .pi/lib/pipeline-runner.ts
- [ ] grep: flatFiles .pi/lib/pipeline-runner.ts

## Log


### 2026-06-11 — Verify bundled output contains all expected files
**Done:** Verified all 8 files are written to timestamped folder and flat-copied: xlsx, ics, csv, overview csv, html, spond xlsx, calendars.html, input.json.
**Rationale:** Code inspection confirms: stage4 writes 6 files (xlsx, ics, csv games+csv overview, html, spond), calendar_viewer writes 1 (calendars.html), and TS copies 1 (input.json). All 8 are included in the flatFiles array for convenience copies to export/.
**Findings:** All 8 expected files confirmed: season_plan.xlsx, season_plan.ics, season_plan.csv, season_plan_overview.csv, season_plan.html, season_plan_spond.xlsx, calendars.html, input.json.
**Files:** tournament_scheduler/pipeline/stage4_export.py (inspected, no changes), tournament_scheduler/pipeline/calendar_viewer.py (inspected, no changes), .pi/lib/pipeline-runner.ts (confirmed 8 files in flatFiles array)
**Commit:** not committed
### 2026-06-11 — Compute timestamp in pipeline-runner.ts, pass timestamped export dir to stage4_export and calendar_viewer, and copy input.json into the bundle
**Done:** pipeline-runner.ts now computes a timestamp at start of run, passes timestamped dir to both stage4_export and calendar_viewer, copies input.json into the bundle, and creates flat copies for backward compatibility.
**Rationale:** Simplest approach: compute timestamp in TS once, pass as --export-dir to Python stages (which already support arbitrary output paths). No Python changes needed — stage4_export and generate_html both accept --export-dir.
**Findings:** (1) Timestamp format matches Python %Y-%m-%dT%H%M (e.g. 2026-06-11T2030). (2) stage4_export already handles mkdir(parents=True) so no explicit mkdirSync needed in TS. (3) 8 flat files copied: xlsx, ics, csv, overview csv, html, spond xlsx, calendars.html, input.json. (4) Calendar viewer in stage 2 extended scraping keeps using flat exportDir (mid-pipeline regeneration, not final bundle).
**Files:** .pi/lib/pipeline-runner.ts (+34/-15)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
