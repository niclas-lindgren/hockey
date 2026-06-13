# Plan: Preserve Stage 3 start times through Stage 4 exports
**Goal:** Stage 4 keeps tournament start times from the checkpoint and exports populated Start/Slutt fields in Excel, iCal, and Spond outputs.
**Created:** 2026-06-13
**Intent:** Prevent deserialization loss so organizers see correct event times in every exported format.
**Backlog-ref:** 68

## Tasks
- [x] Preserve start_time in Stage 4 plan reconstruction and pass round-length config into all time-aware exporters.
  - Files: tournament_scheduler/pipeline/stage4_helpers.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: carry `start_time` through `_dict_to_plan`, instantiate iCal with the configured round lengths, and pass the same mapping to Excel and Spond exports so Start/Slutt fields are computed consistently.
- [x] Add regression coverage for exported Start/Slutt values in Excel, iCal, and Spond outputs.
  - Files: tests/test_stage4_export.py
  - Approach: build a plan checkpoint with explicit `start_time` and per-age-group round lengths, then assert the exported workbook/calendar rows contain populated start/end values rather than blanks.

## Notes
- Stage 3 already serializes `start_time`; the loss happens during Stage 4 reconstruction.
- The existing exporters already know how to compute end times when given `round_length_minutes`.
- Keep the previous Spond event/attachment split intact.

## Acceptance Criteria
- [ ] Stage 4 output contains each tournament's original `start_time` after checkpoint reconstruction.
- [ ] Stage 4 writes populated Start/Slutt values in Excel, iCal, and Spond exports when round lengths are configured.
- [ ] Regression tests assert the exported Start/Slutt fields are populated after the fix.

## Log


### 2026-06-13 — Add regression coverage for exported Start/Slutt values in Excel, iCal, and Spond outputs.
**Done:** Added regression tests that write a Stage 4 config checkpoint with round lengths, then assert Excel overview Start/Slutt cells, iCal DTSTART/DTEND values, and Spond import rows all contain populated times.
**Rationale:** These tests lock in the Stage 4 timing behavior across all exported formats and catch future deserialization or exporter wiring regressions.
**Findings:** The new tests confirm that preserving start_time plus passing round-length config produces non-empty time fields in every time-aware export. The attachment workbook still remains separate from the Spond import workbook.
**Files:** tests/test_stage4_export.py
**Commit:** not committed
### 2026-06-13 — Preserve start_time in Stage 4 plan reconstruction and pass round-length config into all time-aware exporters.
**Done:** Stage 4 now preserves tournament start_time during checkpoint reconstruction and passes configured round lengths into Excel, iCal, and Spond exports so time fields can be computed consistently.
**Rationale:** This fixes the deserialization loss and ensures every time-aware exporter sees the same round-length data.
**Findings:** The Stage 3 checkpoint already contains start_time; the missing piece was Stage 4 reconstruction plus exporter wiring. ICal already emits DTSTART/DTEND from start_time, while Excel and Spond need round lengths to populate Slutt values.
**Files:** tournament_scheduler/pipeline/stage4_helpers.py, tournament_scheduler/pipeline/stage4_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
