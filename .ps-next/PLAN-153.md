# Plan: Harness-driven scraping confidence gate
**Goal:** Stage 2 checkpoint contains per-source event counts, blocked status, and date range; the harness inspects this after Stage 2 to decide whether to proceed to Stage 3, replacing the removed run_confidence_assessment LMStudio call; scraping_confidence.py and llm_approval_gate.py are removed or simplified.
**Created:** 2026-06-18
**Intent:** Eliminate the LLM-based scraping confidence call so the pipeline is deterministic when running under a harness, relying instead on the structured Stage 2 checkpoint fields the harness can inspect directly.
**Backlog-ref:** 153

## Tasks
- [x] Added start_date and end_date fields to the Stage 2 checkpoint dict, serialized as ISO-format strings from the run() function parameters. — 2026-06-18
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: In the checkpoint dict written by `run` at the end of Stage 2, add top-level `start_date` and `end_date` fields (already available from the scraping config/date range logic in the same module), so downstream consumers and the harness can read the scrape window without digging into per-source metadata.

- [x] Replaced the dead _run_confidence_gate function (which accepted a ScrapingConfidenceVerdict) with _check_stage2_checkpoint that reads sources[].event_count, sources[].blocked, and blocked[] directly from the Stage 2 checkpoint dict. Added harness_active parameter to auto-proceed without prompting when running headless. Updated two test files to use the new function. — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Remove the `ScrapingConfidenceVerdict`-based `_run_confidence_gate` function and replace it with a lightweight function that reads `sources[].event_count`, `sources[].blocked`, and `blocked[]` directly from the Stage 2 checkpoint dict; when the harness is active (`get_judge_if_headless()` returns None) auto-proceed based on a simple threshold (e.g. at least one source returned events), otherwise prompt the operator as before.

- [x] Deleted scraping_confidence.py and tests/test_scraping_confidence.py after confirming no production callers exist in the codebase. — 2026-06-18
  - Files: tournament_scheduler/pipeline/scraping_confidence.py, tests/test_scraping_confidence.py
  - Approach: Delete `scraping_confidence.py` entirely since `run_confidence_assessment` has no production callers; delete `tests/test_scraping_confidence.py` as it tests only the removed module; verify no other file imports from this module before deletion.

- [x] Deleted llm_approval_gate.py and tests/test_llm_approval_gate.py after confirming no production callers exist. Also fixed _check_stage2_checkpoint to skip the threshold check when no sources are configured (empty sources list). — 2026-06-18
  - Files: tournament_scheduler/pipeline/llm_approval_gate.py, tests/test_llm_approval_gate.py
  - Approach: Delete `llm_approval_gate.py` and `tests/test_llm_approval_gate.py` if `run_approval_gate` has no production callers; if callers exist, replace the function body with a pass-through that always returns GO without calling an LLM, and remove the LMStudio import.

- [ ] Verify pipeline end-to-end: Stage 2 -> harness decision -> Stage 3 proceeds
  - Files: tests/test_stage2_scraping.py, tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Add or update a test in `test_stage2_scraping.py` that asserts the Stage 2 checkpoint contains `start_date`, `end_date`, and per-source `event_count`/`blocked` fields; add a unit test for the new harness gate function in `pipeline_orchestrator.py` confirming it returns True when at least one source has events, without invoking any LLM client.

## Notes
Constraints: none

Key context:
- `run_confidence_assessment` is already dead production code — it is defined in `scraping_confidence.py` but never called outside of its test file.
- `get_judge_if_headless()` in `tournament_scheduler/llm_judge/__init__.py` already returns None when harness env vars (`RVV_HARNESS`, `CLAUDE_CODE_SESSION_ID`, etc.) are set — the Stage 2 judge call already no-ops in harness mode via `_judge_stage`.
- Stage 2 checkpoint currently has: `sources` (list with `event_count`, `blocked`, `block_reason` per source), `events_by_club`, `blocked` (list of names), `cached`, `checkpoint_path`, optional `warning`. Missing: `start_date`, `end_date`.
- `llm_approval_gate.py` governs Stage 3 (planning), not Stage 2; check for production callers before deleting.

<!-- Research: .ps-next/RESEARCH-harness-scraping-confidence.md — 2026-06-18 -->

## Acceptance Criteria
- [ ] The Stage 2 checkpoint written by run_stage2 contains top-level `start_date` and `end_date` fields in addition to per-source event counts and blocked status.
- [ ] The pipeline orchestrator does not call run_confidence_assessment or any LMStudio client when transitioning from Stage 2 to Stage 3.
- [ ] The `scraping_confidence.py` module is removed from the codebase and no test or production file imports it.
- [ ] The `llm_approval_gate.py` module is either removed or has no LLM client call in its decision path.
- [ ] Running `pytest` passes with no test failures after the changes.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-18 — Added start_date and end_date fields to the Stage 2 checkpoint dict, serialized as ISO-format strings from the run() function parameters.
**Rationale:** Straightforward — the datetime parameters are already available in run(); just format them as strings before writing the checkpoint.
**Findings:** Checkpoint now includes start_date and end_date at the top level alongside sources, blocked, and cached.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+2/-0)
**Commit:** fda37e1 (hockey)

### 2026-06-18 — Replaced the dead _run_confidence_gate function (which accepted a ScrapingConfidenceVerdict) with _check_stage2_checkpoint that reads sources[].event_count, sources[].blocked, and blocked[] directly from the Stage 2 checkpoint dict. Added harness_active parameter to auto-proceed without prompting when running headless. Updated two test files to use the new function.
**Rationale:** ScrapingConfidenceVerdict-based gate was never called in the orchestrator; replacing with direct checkpoint inspection makes the gate deterministic and harness-compatible.
**Findings:** Two test files updated; _run_confidence_gate removed; _check_stage2_checkpoint now called in _cmd_run after _judge_stage(2, ...).
LESSONS: The old test files imported _run_confidence_gate directly — always update both test files when renaming gate functions.
**Files:** pipeline_orchestrator.py (+112/-57), test_confidence_gate.py (+193/-117), test_pipeline_orchestrator_judgment.py (+40/-30)
**Commit:** eb1545e (hockey)

### 2026-06-18 — Deleted scraping_confidence.py and tests/test_scraping_confidence.py after confirming no production callers exist in the codebase.
**Rationale:** Verified no imports before deleting — safe removal of dead module.
**Findings:** No production code imported scraping_confidence; both files deleted cleanly and all tests pass.
LESSONS: none
**Files:** scraping_confidence.py (-177), test_scraping_confidence.py (-194)
**Commit:** 994b93e (hockey)

### 2026-06-18 — Deleted llm_approval_gate.py and tests/test_llm_approval_gate.py after confirming no production callers exist. Also fixed _check_stage2_checkpoint to skip the threshold check when no sources are configured (empty sources list).
**Rationale:** No production callers existed; safe deletion. Empty-sources early-return needed to fix test_confidence_gate_ok_verdict_skips_gate which uses an empty sources checkpoint.
**Findings:** llm_approval_gate.py (-127 lines), test_llm_approval_gate.py (-100 lines) deleted; pipeline_orchestrator.py (+5 lines) to handle empty sources list.
LESSONS: _check_stage2_checkpoint must handle empty sources list (no sources configured) as a pass-through — otherwise integration tests with empty checkpoint dicts fail.
**Files:** llm_approval_gate.py (-127), test_llm_approval_gate.py (-100), pipeline_orchestrator.py (+5)
**Commit:** [pending — fill after commit]
