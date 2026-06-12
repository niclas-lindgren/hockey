# Plan: Stale downstream checkpoint invalidation
**Goal:** When an upstream pipeline stage changes or fails, downstream checkpoints become stale/failed and are no longer reusable without rerunning the pipeline.
**Created:** 2026-06-12
**Intent:** Prevent older Stage 3/4 outputs from masquerading as current after Stage 1/2/3 changes or failures.
**Backlog-ref:** 62

## Tasks
- [x] Teach PipelineState to invalidate downstream checkpoints
  - Files: tournament_scheduler/pipeline/state.py
  - Approach: Mark later stage checkpoints as stale failed outputs when an upstream stage is written as done or failed, preserving the old payload but adding stale metadata and a failure status so downstream reuse is blocked.
- [x] Add regression coverage for stale checkpoint invalidation
  - Files: tests/test_pipeline_state.py
  - Approach: Add tests that simulate Stage 2 failure and Stage 1 config changes, then assert downstream Stage 3/4 envelopes are marked stale/failed and no longer report as done.

## Notes
The Stage 2 strict-failure behavior was already fixed in backlog item 61; this task focuses on preventing old downstream checkpoints from being reused after any upstream change. Keep the implementation in the shared PipelineState layer so stage modules do not need bespoke stale handling.

## Acceptance Criteria
- [ ] run: pytest tests/test_pipeline_state.py
- [ ] run: pytest
- [ ] grep: tournament_scheduler/pipeline/state.py contains stale_from
- [ ] grep: tests/test_pipeline_state.py contains is_stale(StageName.PLANNING)
- [ ] run: python3 - <<'PY'
from pathlib import Path
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus

work = Path('.tmp-pi-next-stale-check')
if work.exists():
    import shutil
    shutil.rmtree(work)
state = PipelineState(work)
state.write_stage(StageName.CONFIG, {'teams': ['A']}, status=StageStatus.DONE)
state.write_stage(StageName.SCRAPING, {'sources': ['old']}, status=StageStatus.DONE)
state.write_stage(StageName.PLANNING, {'plan': {'id': 1}}, status=StageStatus.DONE)
state.write_stage(StageName.EXPORT, {'output_files': {'excel': 'x.xlsx'}}, status=StageStatus.DONE)
state.write_stage(StageName.SCRAPING, {'sources': ['new']}, status=StageStatus.FAILED)
state.mark_failed(StageName.SCRAPING, error='stage 2 failed')
assert state.is_failed(StageName.PLANNING)
assert state.is_failed(StageName.EXPORT)
assert state.is_stale(StageName.PLANNING)
assert state.read_envelope(StageName.PLANNING)['stale_from'] == StageName.SCRAPING.value
print('ok')
PY

## Log


### 2026-06-12 — Add regression coverage for stale checkpoint invalidation
**Done:** Added PipelineState regression tests for Stage 2 failure and Stage 1 config changes, asserting downstream checkpoints become stale failed outputs and are no longer reusable.
**Rationale:** The invalidation rule needs direct coverage so future changes do not silently restore stale downstream reuse.
**Findings:** tests/test_pipeline_state.py now covers both upstream-failure and input-change invalidation paths.
**Files:** tests/test_pipeline_state.py
**Commit:** not committed
### 2026-06-12 — Teach PipelineState to invalidate downstream checkpoints
**Done:** Added downstream invalidation to PipelineState so upstream done/failed writes mark later checkpoints as stale failed outputs, preserving payloads but blocking reuse.
**Rationale:** Centralizing stale invalidation in the shared state layer ensures every stage benefits from the rule without bespoke cleanup code.
**Findings:** pytest tests/test_pipeline_state.py passed and full pytest passed (344 passed, 1 skipped).
**Files:** tournament_scheduler/pipeline/state.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
