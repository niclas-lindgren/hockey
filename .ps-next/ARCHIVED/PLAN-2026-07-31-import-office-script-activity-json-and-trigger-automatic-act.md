# Plan: Import Office Script activity JSON and trigger automatic activity generation
**Goal:** Power Automate sync issues containing `content_json` are imported, validated, written to `inputs/activities/activities.json`, and automatically trigger activity generation + publishing to GitHub Pages.
**Created:** 2026-07-31
**Intent:** Power Automate now sends the Årshjul worksheet as plain JSON (`content_json`) instead of an XLSX download URL. The importer must accept this new contract, validate it, write a canonical JSON file, and then call the activity-publish workflow directly (since GITHUB_TOKEN commits do not trigger push events reliably).
**Backlog-ref:** 55

## Tasks
- [x] Update sharepoint-import.yml to accept content_json instead of download_url
  - Files: .github/workflows/sharepoint-import.yml
  - Approach: Replace the parse step to extract `content_json` (not `download_url`) from the issue body. Replace the download+validate step with JSON contract validation: root is object, schemaVersion==1, worksheet=="Årshjul", values is 2D array of scalars. Write deterministic JSON to `inputs/activities/activities.json` instead of XLSX. Remove the XLSX download, openpyxl, magic-bytes, and temp-file logic. After commit, invoke `activity-publish.yml` via `workflow_call` instead of relying on push event. Update success/failure comment text for the new contract.

- [x] Add schema-v1 JSON → schema-v2 activity payload transformation
  - Files: tournament_scheduler/pipeline/activity_export.py, tests/test_activity_export.py
  - Approach: Add a `build_activities_payload_from_values(values, worksheet, default_year, generated_at)` function that takes a 2D list (the Power Automate `values` array) and produces the same schema-v2 dict that `build_activities_payload` returns. Reuse the existing `_find_header` / `_read_activity_rows` logic by adapting them to work on list-of-lists instead of openpyxl Worksheet. Keep `build_activities_payload` unchanged for XLSX backward compat.

- [x] Update activity-publish.yml with workflow_call trigger and JSON input support
  - Files: .github/workflows/activity-publish.yml
  - Approach: Add `workflow_call` as a trigger with an `activity_input` string parameter and an optional `activity_input_format` parameter (default `xlsx`). When called with `format=json`, use the JSON input path. Add `issues: write` permission. Keep existing `push` and `workflow_dispatch` triggers for backward compat. The `publish-activity-calendar` job should detect the input format and call the appropriate pipeline path.

- [x] Add tests for Power Automate JSON parsing, validation, and transformation
  - Files: tests/test_activity_export.py
  - Approach: Add test functions covering: valid content_json with schema v1, missing schemaVersion, wrong worksheet name, values not a 2D array, cells with non-scalar values, empty values, transformation to schema v2 matches existing XLSX-based output for the same data. Use pytest parametrize for invalid payloads.

- [x] Update documentation for the new content_json contract
  - Files: docs/power-automate-github-sync.md
  - Approach: Update "Flyt A" section to describe the new `content_json` contract instead of `download_url`. Document the issue body format with `content_json`, the validation rules, the canonical JSON destination, and the workflow_call integration. Keep the XLSX flow as a historical note or remove it.

## Notes
- The Office Script must remain unchanged — this work adapts the repository side only.
- `target_path` from the issue body is never used as a write destination; the canonical path is hard-coded.
- `content_json` is plain JSON, never Base64-encoded.
- The `activity-publish.yml` workflow currently triggers on `push` to `inputs/activities/activities.xlsx`. We keep that trigger for manual XLSX uploads but the import workflow uses `workflow_call` to guarantee execution.
- The existing `build_activities_payload` function and its openpyxl dependency remain for manual XLSX-based workflows (Makefile, workflow_dispatch).
- The HTML consumer (`activities/index.html`) already loads `activities.json` and expects schema v2 — no frontend changes needed.
- Deterministic JSON serialization: `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True) + "\n"` — matches what `write_activities_json` already does.

## Acceptance Criteria
- [ ] Run the import workflow with the current Power Automate payload (schemaVersion=1, worksheet=Årshjul, values as 2D array) and verify it succeeds without Office Script changes.
- [ ] Valid `content_json` is imported to `inputs/activities/activities.json`.
- [ ] Invalid JSON, schema version, worksheet name, or `values` shape is rejected with a clear error.
- [ ] The issue-provided `target_path` cannot cause writes outside the canonical destination.
- [ ] An unchanged payload creates no commit.
- [ ] A changed payload creates a deterministic commit.
- [ ] Activity generation and publishing run automatically after a changed import (via workflow_call, not push event).
- [ ] A successful or unchanged run comments on and closes the sync issue.
- [ ] A failed run leaves the sync issue open with a useful failure comment and Actions link.
- [ ] Run `pytest tests/test_activity_export.py -v` and confirm tests pass for parsing, validation, canonical serialization, unchanged imports, changed imports, and issue-closing behavior.

## Log





### 2026-07-31 — Update documentation for the new content_json contract
**Done:** Updated docs/power-automate-github-sync.md: updated architecture diagram to show Office Script → content_json flow, replaced download_url with content_json in the issue contract, added content_json contract documentation with validation rules, updated "Hva skjer etter" to describe JSON validation and workflow_call, updated security section to remove download URL references, and fixed recovery/manual sections to reference JSON paths.
**Rationale:** Documentation must match the current contract. The new content_json flow is the primary documented path; XLSX remains as a manual fallback.
**Findings:** The documentation now accurately describes the current stable contract. XLSX paths remain documented in recovery sections as a legacy fallback.
**Files:** docs/power-automate-github-sync.md (updated multiple sections)
**Commit:** not committed
### 2026-07-31 — Update activity-publish.yml with workflow_call trigger and JSON input support
**Done:** Added workflow_call trigger to activity-publish.yml with activity_input (required) and activity_input_format (optional, default xlsx) parameters. Added inputs/activities/activities.json to the push path trigger alongside the existing XLSX path. Added a resolve_input step that auto-detects format from file extension when not explicitly set. The publish step passes --input to rvv-miniputt activities which now handles JSON via the updated build_activities_payload dispatcher.
**Rationale:** Kept backward compatibility: push trigger still fires on XLSX changes, workflow_dispatch still accepts XLSX input, and the new workflow_call allows the import workflow to trigger publishing deterministically without relying on GITHUB_TOKEN push events.
**Findings:** The existing rvv-miniputt activities command works with JSON input because build_activities_payload now detects .json extension and delegates to the JSON path. No changes needed to the CLI layer. The workflow_call path works for both XLSX and JSON inputs.
**Files:** .github/workflows/activity-publish.yml (rewritten)
**Commit:** not committed
### 2026-07-31 — Update sharepoint-import.yml to accept content_json instead of download_url
**Done:** Rewrote sharepoint-import.yml: replaced download_url parsing with content_json extraction and validation, replaced XLSX download/openpyxl logic with JSON contract validation (via validate_content_json), writes deterministic JSON to inputs/activities/activities.json (hard-coded canonical path, never uses issue target_path), commits only on change, calls activity-publish.yml via workflow_call, and updates success/failure comments with the new contract terminology and Actions run link on failure.
**Rationale:** Completely replaced the download-based flow with the JSON-based flow as specified. All XLSX-specific logic (download, redirects, magic bytes, openpyxl, temp files) removed. The target_path from the issue body is parsed but never used for writing — the canonical path is hard-coded as inputs/activities/activities.json.
**Findings:** The content_json value is parsed with json.loads() for validation, then written to a temp JSON file for the validate step to read via the Python pipeline. The RUNNER_TEMP dir is used for the intermediate file. The workflow_call invocation passes activity_input and activity_input_format=json parameters.
**Files:** .github/workflows/sharepoint-import.yml (rewritten)
**Commit:** not committed
### 2026-07-31 — Update sharepoint-import.yml to accept content_json instead of download_url
**Done:** Added 20 tests in two new test classes: TestValidateContentJSON (12 tests covering valid payloads, wrong schemaVersion, wrong worksheet, missing values, non-list values, nested objects/arrays, null/bool/numeric cells) and TestBuildActivitiesPayloadFromValues (8 tests covering schema-v2 transformation, year inference, empty values, header detection, XLSX equivalence, and help row skipping).
**Rationale:** Tests are co-located with the implementation changes in the same file pair. No separate test file needed — the new classes in test_activity_export.py cover all the validation and transformation cases required by the acceptance criteria.
**Findings:** All 33 tests pass (13 existing + 20 new). The smoke test confirms that the JSON path and XLSX path produce identical schema-v2 output for equivalent data.
**Files:** tests/test_activity_export.py (+193/-0)
**Commit:** not committed
### 2026-07-31 — Update sharepoint-import.yml to accept content_json instead of download_url
**Done:** Added validate_content_json(), build_activities_payload_from_values(), _find_header_in_rows(), _read_activity_rows_from_list(), and _process_activity_row() to activity_export.py. The new functions accept the Power Automate 2D values array and produce the same schema-v2 output as the existing XLSX path, reusing the same row-processing logic via the extracted _process_activity_row() helper.
**Rationale:** Extracted row processing into _process_activity_row() to avoid duplicating the 60+ line record-building block. Both _read_activity_rows (XLSX) and _read_activity_rows_from_list (JSON) now delegate to it. Added ActivityJSONValidationError and validate_content_json() for the contract validation layer. 20 new tests cover all validation cases and equivalence with XLSX path.
**Findings:** The help row regex requires word boundaries, so 'eksempelrad' doesn't match but standalone 'Example'/'Help' do. The XLSX and JSON paths produce identical output for the same data as verified by the smoke test.
**Files:** tournament_scheduler/pipeline/activity_export.py (+108/-55), tests/test_activity_export.py (+193/-0)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
