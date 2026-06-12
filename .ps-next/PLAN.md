# Plan: Refactor pipeline stages into focused helpers
**Goal:** Split the oversized pipeline stage modules into smaller helper modules without changing the public pipeline behavior.
**Created:** 2026-06-12
**Intent:** Make config, scraping, planning, and export code easier to test, extend, and reason about.
**Backlog-ref:** 73

## Tasks
- [x] Split Stage 1 config parsing/validation into helper functions
  - Files: tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage1_helpers.py, tests/test_stage1_config.py
  - Approach: Move JSON loading, date/team validation, and config parsing into a small helper module; keep the public Stage 1 API stable and verify the existing config tests still pass.
- [x] Split Stage 2 scraping orchestration into focused helper modules
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/stage2_helpers.py, tests/test_stage2_scraping.py
  - Approach: Extract cache/result assembly and source-routing helpers out of the main stage file while preserving the current internal function names that the tests patch/import.
- [x] Split Stage 3 planning serialization/builders into helpers
  - Files: tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage3_helpers.py, tests/test_stage3_planning.py, tests/test_tournament_updater.py, tournament_scheduler/html/html_exporter.py
  - Approach: Move plan serialization, roster/planner construction, and tournament reconstruction helpers into a shared module and re-export the functions needed by update/export callers.
- [x] Split Stage 4 export/reconstruction logic into helper functions
  - Files: tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/stage4_helpers.py, tests/test_stage4_export.py
  - Approach: Pull plan deserialization plus per-format export metadata assembly into helper functions so the main export entry point only orchestrates file writes and checkpoint updates.

## Notes
- Preserve the existing stage module APIs because tests and callers import internal helper names such as `_events_to_dicts`, `_plan_to_dict`, and `_dict_to_plan`.
- Keep all behavior changes minimal; this work is a structural refactor, not a feature change.
- Current module sizes are concentrated in Stage 2 (~1.4k lines) with Stage 1/3/4 also carrying mixed responsibilities.

## Acceptance Criteria
- [ ] `pytest tests/test_stage1_config.py tests/test_stage2_scraping.py tests/test_stage3_planning.py tests/test_stage4_export.py tests/test_tournament_updater.py` passes.
- [ ] `python -m compileall tournament_scheduler/pipeline` runs without syntax errors.
- [ ] The four stage modules remain importable and still expose the existing public/internal helper names used by tests and callers.

## Log




### 2026-06-12 — Split Stage 4 export/reconstruction logic into helper functions
**Done:** Stage 4 now pulls plan reconstruction into `stage4_helpers.py` and keeps the export entry point focused on file generation and checkpoint updates.
**Rationale:** This trims the export module and makes the checkpoint-to-plan conversion reusable without mixing it into the orchestration path.
**Findings:** Stage 4 export tests still pass after the deserialisation helper split; exports continue to write the expected files.
**Files:** tournament_scheduler/pipeline/stage4_export.py, tournament_scheduler/pipeline/stage4_helpers.py
**Commit:** not committed
### 2026-06-12 — Split Stage 3 planning serialization/builders into helpers
**Done:** Stage 3 now delegates plan serialization and planner-construction helpers to `stage3_helpers.py` while keeping the planner entry point stable.
**Rationale:** This reduces the size of the planning module and concentrates the reusable roster/plan conversion logic in one place.
**Findings:** Stage 3 planning tests and updater round-trips still pass after moving the builder/serializer helpers out of the main module.
**Files:** tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage3_helpers.py
**Commit:** not committed
### 2026-06-12 — Split Stage 2 scraping orchestration into focused helper modules
**Done:** Stage 2 now reuses `stage2_helpers.py` for cache/result assembly and scraper utilities, while `stage2_scraping.py` keeps the orchestration entry points.
**Rationale:** This separates the long-running orchestration path from reusable scraping helpers and preserves the test-patched function names.
**Findings:** The unified-cache and scraper tests still pass after the refactor; the helper module now owns the shared scraping utilities.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/stage2_helpers.py
**Commit:** not committed
### 2026-06-12 — Split Stage 1 config parsing/validation into helper functions
**Done:** Stage 1 now delegates parsing/validation work to `stage1_helpers.py` while keeping the public config API unchanged.
**Rationale:** This isolates config validation and parsing from checkpoint orchestration, making the stage easier to read and test.
**Findings:** Stage 1 still passes existing config tests after the split; helper module owns JSON loading, validation, and config parsing.
**Files:** tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage1_helpers.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
