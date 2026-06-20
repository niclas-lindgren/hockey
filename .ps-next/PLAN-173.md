# Plan: Wrap state.py file writes in try/except

**Feature:** Wrap state.py file writes in try/except — write_stage, write_judgment, write_approval, _set_status, _invalidate_downstream all write JSON without catching OSError or json.JSONDecodeError, risking silent data loss mid-pipeline
**Goal:** Wrap state.py file writes in try/except — write_stage, write_judgment, write_approval, _set_status, _invalidate_downstream all write JSON without catching OSError or json.JSONDecodeError, risking silent data loss mid-pipeline
**Backlog-ref:** 173
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Prevent silent data loss and pipeline corruption when filesystem writes fail during checkpoint updates.

---

## Tasks

- [x] Added _write_envelope helper in state.py that centralises path.write_text inside try/except catching OSError and ValueError, raising RuntimeError on failure. All five write methods now delegate to this helper. — 2026-06-20
  - Files: `tournament_scheduler/pipeline/state.py`
  - Approach: Add a private `_write_envelope(self, path, envelope)` method that wraps the write_text call with `try/except (OSError, ValueError) as exc` and re-raises as `RuntimeError(f"Failed to write checkpoint {path}: {exc}")`. All five write methods call this helper instead of writing inline.

- [x] Replaced bare write_text call in write_stage with self._write_envelope(path, envelope). — 2026-06-20
  - Files: `tournament_scheduler/pipeline/state.py`
  - Approach: Replace the bare `path.write_text(json.dumps(...))` call in `write_stage` with a call to `self._write_envelope(path, envelope)` so OSError and json serialisation errors are surfaced immediately.

- [x] Replaced bare write_text calls in write_judgment and write_approval with self._write_envelope(path, envelope). — 2026-06-20
  - Files: `tournament_scheduler/pipeline/state.py`
  - Approach: Replace the bare `path.write_text(json.dumps(...))` calls in both `write_judgment` and `write_approval` with `self._write_envelope(path, envelope)`.

- [x] Replaced bare write_text calls in _set_status and _invalidate_downstream with self._write_envelope(path, envelope). — 2026-06-20
  - Files: `tournament_scheduler/pipeline/state.py`
  - Approach: Replace the bare `path.write_text(json.dumps(...))` calls in `_set_status` and `_invalidate_downstream` with `self._write_envelope(path, envelope)`.

- [x] Added 7 new tests in TestWriteEnvelopeErrorHandling class in test_pipeline_state.py covering OSError and ValueError injection for all five write methods, and verifying the error message contains the file path. — 2026-06-20
  - Files: `tests/test_state.py`
  - Approach: Use `unittest.mock.patch.object` to make `Path.write_text` raise `OSError` or `ValueError`, then assert that each of the five methods raises `RuntimeError` with a message containing the path — confirming no silent swallowing.

- [x] Reviewed stage1-4, tournament_updater, and pipeline_orchestrator. No caller adds extra try/except for write errors. The orchestrator already has broad except Exception handlers that log errors visibly. RuntimeError propagates with a visible message — acceptable per plan. — 2026-06-20
  - Files: `tournament_scheduler/pipeline/stage1_config.py`, `tournament_scheduler/pipeline/stage2_scraping.py`, `tournament_scheduler/pipeline/stage3_planning.py`, `tournament_scheduler/pipeline/stage4_export.py`, `tournament_scheduler/pipeline/tournament_updater.py`, `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Approach: Review each call site — if the caller already wraps with a broad `except Exception`, confirm the error is logged before re-raise; where no handler exists the RuntimeError propagates to the CLI and prints a visible traceback, which is acceptable.

---

## Log

- 2026-06-20 Plan created

---

## Acceptance Criteria

Each of the five write methods in state.py has a try/except block (or delegates to a helper that has one) catching OSError and ValueError.
When a simulated OSError is injected via mocking, pytest tests for write_stage, write_judgment, write_approval, _set_status, and _invalidate_downstream all pass without silent failure.
Calling any write method when the target path is not writable raises a RuntimeError that contains the file path in its message instead of silently swallowing the error.
The pipeline reports a visible error message and does not produce a zero-byte or partially-written checkpoint file when a write fails.
No new try/except blocks are added to caller files (stage1–4, tournament_updater) — error handling is centralised in state.py.

### 2026-06-20 — Added _write_envelope helper in state.py that centralises path.write_text inside try/except catching OSError and ValueError, raising RuntimeError on failure. All five write methods now delegate to this helper.
**Rationale:** Centralising error handling in one place avoids duplicating try/except blocks across five methods.
**Findings:** All five write methods now use _write_envelope; pytest passes.
LESSONS: none
**Files:** tournament_scheduler/pipeline/state.py (+19/-5)
**Commit:** [pending — fill after commit]

### 2026-06-20 — Replaced bare write_text call in write_stage with self._write_envelope(path, envelope).
**Rationale:** Delegate to centralized helper.
**Findings:** write_stage now raises RuntimeError on OSError/ValueError.
LESSONS: none
**Files:** tournament_scheduler/pipeline/state.py (+3/-1)
**Commit:** [pending]

### 2026-06-20 — Replaced bare write_text calls in write_judgment and write_approval with self._write_envelope(path, envelope).
**Rationale:** Delegate to centralized helper.
**Findings:** Both methods now raise RuntimeError on OSError/ValueError.
LESSONS: none
**Files:** tournament_scheduler/pipeline/state.py (+4/-2)
**Commit:** [pending]

### 2026-06-20 — Replaced bare write_text calls in _set_status and _invalidate_downstream with self._write_envelope(path, envelope).
**Rationale:** Delegate to centralized helper.
**Findings:** Both methods now raise RuntimeError on OSError/ValueError.
LESSONS: none
**Files:** tournament_scheduler/pipeline/state.py (+4/-2)
**Commit:** [pending]

### 2026-06-20 — Added 7 new tests in TestWriteEnvelopeErrorHandling class in test_pipeline_state.py covering OSError and ValueError injection for all five write methods, and verifying the error message contains the file path.
**Rationale:** Tests cover each write method via monkeypatching Path.write_text to raise OSError or ValueError.
**Findings:** All 22 tests pass including 7 new error-handling tests.
LESSONS: none
**Files:** tests/test_pipeline_state.py (+84/-0)
**Commit:** [pending]

### 2026-06-20 — Reviewed stage1-4, tournament_updater, and pipeline_orchestrator. No caller adds extra try/except for write errors. The orchestrator already has broad except Exception handlers that log errors visibly. RuntimeError propagates with a visible message — acceptable per plan.
**Rationale:** Caller files do not need changes; propagation to the orchestrators existing error handling is sufficient.
**Findings:** All callers let RuntimeError propagate; pipeline_orchestrator logs it visibly.
LESSONS: none
**Files:** no files changed
**Commit:** [pending]
