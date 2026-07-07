# Plan: Stage 2 event-count expectations
**Goal:** Stage 2 computes per-source expected event-count ranges from season date range and age-group configuration, stores them in checkpoints, and surfaces suspiciously sparse sources in summaries.
**Created:** 2026-07-07
**Intent:** Operators and harnesses need an early signal when a calendar scrape technically succeeds but returns too few events to be trustworthy.
**Backlog-ref:** 7

## Tasks
- [x] Add deterministic Stage 2 event expectation calculation
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tests/test_stage2_scraping.py
  - Approach: Derive a lightweight expected event count from configured age groups/targets and the scrape date range; attach `event_expectation` metadata to every source result and checkpoint-level `event_expectation_warnings` for sources below the threshold, without blocking successful runs.
- [x] Surface sparse-source warnings in status and checkpoint summaries
  - Files: tournament_scheduler/cli/reporting.py, tournament_scheduler/cli/checkpoint_printer.py, tests/test_stage2_scraping.py
  - Approach: Include expectation warnings in `rvv-miniputt status` Stage 2 output and in `checkpoint_printer` summaries so harnesses and humans see suspicious event counts without reading raw JSON.
- [x] Document the Stage 2 expectation signal
  - Files: docs/rvv-miniputt-pipeline.md, docs/rvv-miniputt-rules-report.md
  - Approach: Add concise docs explaining that Stage 2 now flags low event counts as recovery-priority warnings, distinct from hard blocked sources.

## Notes
- Keep this as a warning/signal only; a source with events should not become blocked solely because the heuristic thinks the count is low.
- Use existing Stage 2 checkpoint schema style: per-source dictionaries plus top-level summary lists.
- Avoid LLM calls; this must be deterministic and testable.
- Existing backlog has items #207–#209 from project review; do not implement them here.

## Acceptance Criteria
- [ ] Stage 2 checkpoint contains per-source `event_expectation` fields and a top-level `event_expectation_warnings` list when a source returns suspiciously few events.
- [ ] `rvv-miniputt status` / reporting output mentions sparse Stage 2 sources when warnings are present.
- [ ] Tests pass for sources below and above the expected-event threshold without requiring live calendar access.
- [ ] Documentation contains the new sparse-source warning and recovery use case.

## Log



### 2026-07-07 — Document the Stage 2 expectation signal
**Done:** Documented Stage 2 sparse event-count warning metadata and status behavior in the pipeline guide and rules report.
**Rationale:** The expectation signal is intentionally advisory, so docs need to distinguish it from blocked sources and explain the recovery use case.
**Findings:** Docs now mention event_expectation, event_expectation_warnings, and the status summary label.
**Files:** docs/rvv-miniputt-pipeline.md, docs/rvv-miniputt-rules-report.md
**Commit:** not committed
### 2026-07-07 — Surface sparse-source warnings in status and checkpoint summaries
**Done:** Added Stage 2 sparse-event warning output to status text and checkpoint summaries, with regression tests.
**Rationale:** Operators need the warning visible in normal status/checkpoint review flows instead of only in raw checkpoint JSON.
**Findings:** Status now prints up to three sparse-source messages; checkpoint printer includes the top-level event_expectation_warnings summary.
**Files:** tournament_scheduler/cli/reporting.py, tournament_scheduler/cli/checkpoint_printer.py, tests/test_stage2_scraping.py
**Commit:** not committed
### 2026-07-07 — Add deterministic Stage 2 event expectation calculation
**Done:** Added deterministic Stage 2 event-count expectation metadata and sparse-source warnings based on scrape date range and active age groups.
**Rationale:** This keeps suspicious low event counts as a non-blocking recovery signal while preserving existing blocked-source semantics.
**Findings:** A full September-December test range with four active age groups yields a warning for one event but not for eight events; Stage 2 test module passes.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py, tests/test_stage2_scraping.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
