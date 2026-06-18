# Plan: Scraping Confidence WARN Gating

**Feature:** Act on scraping confidence WARN verdict: in strict mode (default), block Stage 3 and require operator confirmation when the confidence assessment returns WARN; in non-strict mode (--non-strict flag), log the warning and proceed automatically. Reuse the same --non-strict flag and confirmation prompt pattern already used by the LLM approval gate before Stage 4.
**Goal:** Act on scraping confidence WARN verdict: in strict mode (default), block Stage 3 and require operator confirmation when the confidence assessment returns WARN; in non-strict mode (--non-strict flag), log the warning and proceed automatically. Reuse the same --non-strict flag and confirmation prompt pattern already used by the LLM approval gate before Stage 4.
**Backlog-ref:** 147
**Constraints:** none
**Date:** 2026-06-18
**Intent:** Prevent low-confidence scraped data from silently flowing into season planning by gating Stage 3 on the existing confidence verdict and surfacing operator control via the established --non-strict/confirmation-prompt pattern.

## Tasks

- [x] Added _run_confidence_gate helper in pipeline_orchestrator.py that mirrors _run_approval_gate: in strict mode prompts operator with Norwegian confirmation prompt, in non-strict mode logs and continues; updated WARN branch in _cmd_run to call the gate with halt-on-decline; added 10 unit tests in tests/test_confidence_gate.py covering all code paths. — 2026-06-18
  - Mirror the `_run_approval_gate` signature pattern (strict: bool, console, log_fn); accept `_conf_verdict` (ScrapingConfidenceVerdict); in strict mode, show Rich warning with suspicious_sources/gaps/overall_assessment and prompt "Vil du fortsette til planlegging likevel? (j/n):" accepting j/y/ja/yes; in non-strict mode, log the WARN and return True automatically.
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`

- [ ] Call `_run_confidence_gate` from `_cmd_run` between confidence assessment and Stage 3
  - After the confidence assessment block (~line 552) and before the `if resume_from <= 3:` Stage 3 check (~line 553), call `_run_confidence_gate(_conf_verdict, strict, console, log_fn)`; if it returns False, abort the pipeline (return early or raise) mirroring how `_run_approval_gate` False result is handled before Stage 4.
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`

- [ ] Add unit tests for `_run_confidence_gate` covering strict-block and non-strict-proceed paths
  - In `tests/test_pipeline_orchestrator_judgment.py`, add test cases: WARN+strict=True with operator answering "n" (expects abort), WARN+strict=True with operator answering "j" (expects proceed), WARN+strict=False (expects proceed without prompt), OK+strict=True (expects proceed without prompt); mock `input()` and Rich console.
  - Files: `tests/test_pipeline_orchestrator_judgment.py`

- [ ] Verify scraping_confidence.py requires no changes; update `tests/test_scraping_confidence.py` only if helpers move
  - Confirm all gate logic lives in pipeline_orchestrator.py; if any helper is moved from scraping_confidence.py, update its tests accordingly; otherwise add a passing no-op note confirming no API change.
  - Files: `tournament_scheduler/pipeline/scraping_confidence.py`, `tests/test_scraping_confidence.py`

## Acceptance Criteria

When scraping confidence assessment returns WARN verdict in strict mode, the pipeline does not proceed to Stage 3 unless the operator confirms, and the confirmation prompt matches the j/y/ja/yes pattern used before Stage 4.
When the --non-strict flag is provided and the scraping confidence assessment returns WARN, the pipeline logs the warning and continues to Stage 3 without prompting.
When the scraping confidence assessment returns OK, the pipeline proceeds to Stage 3 without any confirmation prompt in both strict and non-strict modes.
The confirmation prompt shown for a WARN verdict in strict mode contains the suspicious sources, gaps, and overall assessment from the verdict, matching the warning detail pattern used by the LLM approval gate.
The unit tests in tests/test_pipeline_orchestrator_judgment.py pass for all four gate scenarios: WARN+strict+no (abort), WARN+strict+yes (proceed), WARN+non-strict (proceed), OK+strict (proceed).

## Log
- [2026-06-18] Plan created for backlog item 147

### 2026-06-18 — Added _run_confidence_gate helper in pipeline_orchestrator.py that mirrors _run_approval_gate: in strict mode prompts operator with Norwegian confirmation prompt, in non-strict mode logs and continues; updated WARN branch in _cmd_run to call the gate with halt-on-decline; added 10 unit tests in tests/test_confidence_gate.py covering all code paths.
**Rationale:** Straightforward extraction of display+prompt logic from the inline WARN block; the gate is self-contained and needs no new imports since the orchestrator already has Console and log_fn in scope.
**Findings:** 10 unit tests pass; pipeline_orchestrator.py now blocks Stage 3 when operator declines in strict mode.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+75/-15), tests/test_confidence_gate.py (+125)
**Commit:** [pending — fill after commit]
