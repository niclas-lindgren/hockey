# Plan: GitHub issue #34 reproducible Stage 4 exports
**Goal:** Implement GitHub issue #34 so Stage 4 exports can produce byte-stable public bundle artifacts for identical inputs and an explicit build timestamp.
**Created:** 2026-07-30
**Intent:** Avoid unnecessary public bundle fingerprint churn, review approvals, and gh-pages commits when the generated season content has not changed.

## Tasks
- [x] Add a canonical Stage 4 build timestamp contract
  - Files: tournament_scheduler/pipeline/stage4_export.py, tests/test_stage4_export.py
  - Approach: Introduce a small timestamp resolver used for both timestamped export directory naming and `generated_at`, honoring an explicit `build_timestamp` argument and `SOURCE_DATE_EPOCH` while preserving current wall-clock defaults. Add focused tests for stable checkpoint metadata and directory naming without changing existing callers.
- [x] Normalize generated artifact bytes for reproducible exports
  - Files: tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/ical/ical_exporter.py, tournament_scheduler/review/review_packet_exporter.py, tests/test_stage4_export.py
  - Approach: After Stage 4 writes XLSX outputs, normalize workbook core properties and ZIP member timestamps/order for files in the export surface using the canonical build timestamp; also remove other volatile generated artifact fields found by the regression (for example random ICS UIDs and absolute review packet paths). Cover the main workbook plus Spond/review workbooks with a reproducibility regression that hashes exported files across two runs.
- [x] Stabilize public bundle fingerprint behavior and document the contract
  - Files: tests/test_stage4_export.py, docs/rvv-miniputt-pipeline.md
  - Approach: Add/extend an end-to-end-style test that builds a public bundle from two identical Stage 4 outputs and asserts matching per-file hashes plus bundle fingerprints via the existing pages_publish helper; also assert a meaningful plan/input change changes at least the relevant hashes. Document `build_timestamp`/`SOURCE_DATE_EPOCH`, stable `generated_at`, and which operational timestamps remain intentionally outside content identity.

## Notes
Selected open GitHub issue: https://github.com/niclas-lindgren/hockey/issues/34 (`[P1] Make Stage 4 export artifacts reproducible`). Recent history shows issues #45/#46 were already implemented/documented, so this plan avoids duplicating those open-but-completed items. Stage 4 currently calls `datetime.now()` for timestamped export directories and UTC `generated_at`; `pages_publish.bundle_fingerprint()` hashes bundle paths and bytes only, so stabilizing export bytes should stabilize the public content identity. Keep publication/audit timestamps in operator logs/history as operational metadata, not content metadata.

## Acceptance Criteria
- [ ] Stage 4 can run with an explicit build timestamp or `SOURCE_DATE_EPOCH` and writes stable `generated_at` metadata.
- [ ] Two Stage 4 runs with identical inputs and build timestamp produce identical file bytes for JSON/HTML, ICS, report, and XLSX outputs where present.
- [ ] The public bundle fingerprint is identical for unchanged content and changes when a meaningful plan input changes.
- [ ] XLSX/ZIP container metadata is normalized enough that workbook exports no longer drift solely because of write time.
- [ ] The reproducibility contract and intentional operational timestamp exceptions are documented.
- [ ] Relevant tests pass via `pytest tests/test_stage4_export.py`.

## Log



### 2026-07-30 — Stabilize public bundle fingerprint behavior and document the contract
**Done:** Added a public-bundle reproducibility regression proving identical Stage 4 exports yield matching file hashes and bundle fingerprints while a meaningful plan change changes the fingerprint. Documented the Stage 4 reproducibility contract, SOURCE_DATE_EPOCH usage, standalone --build-timestamp flag, and operational timestamp exceptions.
**Rationale:** The existing bundle_fingerprint helper already hashes paths and bytes deterministically; the missing piece was stable exported bytes plus tests and operator-facing documentation for the contract.
**Findings:** `pytest tests/test_stage4_export.py tests/test_pages_bundle.py tests/test_review_packets.py -q` and `pytest tests/test_ical_exporter.py tests/test_stage4_export.py -q` pass.
**Files:** tests/test_stage4_export.py; docs/rvv-miniputt-pipeline.md; .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-30 — Normalize generated artifact bytes for reproducible exports
**Done:** Normalized Stage 4 workbook ZIP/core metadata after export, made iCal UIDs deterministic, removed absolute review-packet paths from generated manifests, and added a regression comparing file hashes across identical exports.
**Rationale:** The first reproducibility test exposed drift outside XLSX files (random ICS UIDs and absolute packet paths), so the normalization task was broadened to remove all volatile artifact fields found by the regression.
**Findings:** `pytest tests/test_stage4_export.py tests/test_review_packets.py -q` passes. Diff review warning is from an existing 'placeholder' string in not_started logic context, not new TODO/FIXME text.
**Files:** tournament_scheduler/pipeline/stage4_export.py; tournament_scheduler/ical/ical_exporter.py; tournament_scheduler/review/review_packet_exporter.py; tests/test_stage4_export.py; .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-30 — Add a canonical Stage 4 build timestamp contract
**Done:** Added a canonical UTC build timestamp resolver for Stage 4, wired it into timestamped export directory naming, generated_at metadata, and the standalone CLI via --build-timestamp.
**Rationale:** A single content timestamp keeps existing wall-clock behavior by default while enabling deterministic runs through an explicit value or SOURCE_DATE_EPOCH.
**Findings:** Focused Stage 4 tests pass; diff review warning is from an existing 'placeholder' string in unchanged not_started logic context, not a new TODO/FIXME.
**Files:** tournament_scheduler/pipeline/stage4_export.py; tests/test_stage4_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
