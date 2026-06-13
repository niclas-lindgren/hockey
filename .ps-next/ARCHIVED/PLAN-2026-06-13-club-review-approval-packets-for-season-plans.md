# Plan: Club review/approval packets for season plans
**Goal:** Generate per-club review packets from the season plan and let club responses feed back into replanning.
**Created:** 2026-06-13
**Intent:** Give each club a focused approval package with just their relevant schedule, hosting, travel, and attachment data, then make change requests actionable without starting over manually.
**Backlog-ref:** 71

## Tasks
- [x] Build per-club review packet exports from the final season plan
  - Files: tournament_scheduler/review/__init__.py, tournament_scheduler/review/review_packet_exporter.py, tournament_scheduler/spond/spond_exporter.py, tournament_scheduler/pipeline/stage4_export.py
  - Approach: add a small review-packet exporter that reuses the existing Spond/game-attachment data paths, filters to one club at a time, and writes a club folder containing a manifest plus workbook/attachment artifacts with proposed events, hosting duties, travel summary, and game schedule.
- [x] Add an accept/change-request response workflow that can re-enter the adjustment/replanning loop
  - Files: tournament_scheduler/review/review_packet_exporter.py, tournament_scheduler/pipeline/manual_adjustment_workflow.py, tournament_scheduler/pipeline/tournament_updater.py, tournament_scheduler/cli/review_command.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: define a compact response format (accept vs change-request with requested locks/bans/pins/host changes), parse club responses, map change requests onto existing manual-adjustment metadata or targeted tournament updates, and rerun the existing adjustment/export path so the plan can be replanned from the request.
- [x] Add regression coverage for packet contents and response application
  - Files: tests/test_review_packets.py, tests/test_stage4_export.py, tests/test_manual_adjustment_workflow.py, tests/test_tournament_updater.py
  - Approach: verify each club packet only includes that club's relevant tournaments and attachments, confirm the manifest/response files are written, and exercise an accept/change-request round-trip that updates the Stage 3 checkpoint and triggers re-export.

## Notes
Reuse the existing Spond export and printable game-schedule workbook where possible; the new feature should mostly orchestrate filtered exports, not invent a second schedule representation.

## Acceptance Criteria
- [ ] Stage 4 writes a per-club review packet for each club with only that club's proposed events, hosting duties, travel summary, and schedule attachment.
- [ ] A club response marked as a change request can update the season plan inputs and rerun the adjustment/export flow without manual file surgery.
- [ ] Run regression tests that verify the packet contents and the response-to-replan path.

## Log



### 2026-06-13 — Add regression coverage for packet contents and response application
**Done:** Added regression tests that verify per-club review packet contents and exercise a change-request round-trip through the review CLI.
**Rationale:** The new packet export and response workflow need coverage for both file contents and the end-to-end replan path.
**Findings:** The review packet test checks that club-specific Spond imports, schedule attachments, manifests, and response templates are written, and the CLI test proves a change request updates the Stage 3 checkpoint and triggers re-export.
**Files:** tests/test_review_packets.py; tournament_scheduler/pipeline/stage4_export.py
**Commit:** not committed
### 2026-06-13 — Add an accept/change-request response workflow that can re-enter the adjustment/replanning loop
**Done:** Added a review-response CLI flow that loads packet responses, normalizes accept/change-request payloads, merges requested adjustments, reapplies the existing manual-adjustment workflow, and re-exports the plan.
**Rationale:** Club responses now feed back into the same checkpoint/update/export path used for organizer adjustments, so change requests can trigger replanning without manual file surgery.
**Findings:** Response templates use alias-friendly keys (for example pin_tournaments and force_host_clubs), which are normalized to the manual-adjustment schema before replanning. The new review command supports packet directories or response files, and the existing Stage 4 export is re-run after any change request is applied.
**Files:** tournament_scheduler/review/review_packet_exporter.py; tournament_scheduler/pipeline/manual_adjustment_workflow.py; tournament_scheduler/pipeline/tournament_updater.py; tournament_scheduler/cli/review_command.py; tournament_scheduler/cli/rvv_cli.py; tournament_scheduler/pipeline/stage4_export.py
**Commit:** not committed
### 2026-06-13 — Build per-club review packet exports from the final season plan
**Done:** Added per-club review packet generation to Stage 4.
**Rationale:** The final export step now emits a club-specific packet folder with a review workbook, filtered Spond import workbook, filtered game-schedule attachment, a manifest, and a response template.
**Findings:** Review packets are written under <export>/review_packets/<club>/ and reuse the existing Spond export paths plus a club-filtered attachment. The change stayed backward-compatible with the existing Spond workbook and Stage 4 tests after adjusting the attachment exporter to accept an optional club filter.
**Files:** tournament_scheduler/review/__init__.py; tournament_scheduler/review/review_packet_exporter.py; tournament_scheduler/spond/spond_exporter.py; tournament_scheduler/pipeline/stage4_export.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
