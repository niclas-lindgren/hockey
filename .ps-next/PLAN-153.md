# Plan: Harness-driven scraping confidence gate
**Goal:** Stage 2 checkpoint contains per-source event counts, blocked status, and date range; the harness inspects this after Stage 2 to decide whether to proceed to Stage 3, replacing the removed run_confidence_assessment LMStudio call; scraping_confidence.py and llm_approval_gate.py are removed or simplified.
**Created:** 2026-06-18
**Intent:** Eliminate the LLM-based scraping confidence call so the pipeline is deterministic when running under a harness, relying instead on the structured Stage 2 checkpoint fields the harness can inspect directly.
**Backlog-ref:** 153

## Tasks
- [x] Added start_date and end_date fields to the Stage 2 checkpoint dict, serialized as ISO-format strings from the run() function parameters. — 2026-06-18
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: In the checkpoint dict written by `run` at the end of Stage 2, add top-level `start_date` and `end_date` fields (already available from the scraping config/date range logic in the same module), so downstream consumers and the harness can read the scrape window without digging into per-source metadata.

- [ ] Replace _run_confidence_gate with deterministic harness-readable checkpoint inspection
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Remove the `ScrapingConfidenceVerdict`-based `_run_confidence_gate` function and replace it with a lightweight function that reads `sources[].event_count`, `sources[].blocked`, and `blocked[]` directly from the Stage 2 checkpoint dict; when the harness is active (`get_judge_if_headless()` returns None) auto-proceed based on a simple threshold (e.g. at least one source returned events), otherwise prompt the operator as before.

- [ ] Remove scraping_confidence.py and its tests
  - Files: tournament_scheduler/pipeline/scraping_confidence.py, tests/test_scraping_confidence.py
  - Approach: Delete `scraping_confidence.py` entirely since `run_confidence_assessment` has no production callers; delete `tests/test_scraping_confidence.py` as it tests only the removed module; verify no other file imports from this module before deletion.

- [ ] Remove or stub-out llm_approval_gate.py
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
**Commit:** [pending — fill after commit]
