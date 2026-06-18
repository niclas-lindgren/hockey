# Plan: Replace static report conclusion with LLM-generated narrative

**Goal:** Replace static report conclusion with LLM-generated narrative: instead of picking from 3 hardcoded strings based on fairness_gate.status, pass the plan metrics, score breakdown, blocked sources, and adjustment history to an LLM and ask it to write a short (3–5 sentence) run-specific assessment in Norwegian. This is the conclusion section in _report_overview_html. See also #136 for the data injection groundwork.

**Created:** 2026-06-18

**Intent:** The report conclusion currently picks from three hardcoded Norwegian strings based only on the gate status, losing all run-specific detail; an LLM-generated narrative will surface meaningful per-run context (scores, blocked sources, adjustment history) to help organizers understand why the plan is ready — or not.

**Backlog-ref:** 144

**Constraints:** none

## Tasks

- [x] Created conclusion.py renderer module with generate_report_conclusion() that calls LMStudio for a 3-5 sentence Norwegian narrative; returns None on unavailability. Updated renderers/__init__.py docstring. — 2026-06-18
  - Files: tournament_scheduler/html/renderers/conclusion.py, tournament_scheduler/html/renderers/__init__.py
  - Approach: Create a new renderer module that accepts `plan`, `blocked`, and an optional `LMStudioClient` instance; it builds a system prompt instructing the LLM to write 3–5 Norwegian sentences, constructs a user prompt with gate status/score, per-metric breakdown, blocked source count, and manual_adjustments summary, calls `client.complete()`, and returns the text string. When no client is provided or `LMStudioUnavailableError` is raised, return `None` so the caller can fall back.

- [x] Added llm_client parameter to _report_overview_html and wired in generate_report_conclusion; falls back to static answer if LLM returns None. — 2026-06-18
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Add an optional `llm_client` keyword argument to `_report_overview_html`; after computing `overall_status`, call `generate_report_conclusion(plan, blocked, llm_client)` and, if it returns a non-empty string, use it as `answer` instead of `answer_by_status[overall_status]`. The `note` string (navigation guidance) stays deterministic and is not replaced by LLM output, keeping the UI stable.

- [x] Added llm_client parameter to HtmlExporter.export() and forwarded it to _report_overview_html(). — 2026-06-18
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Add an optional `llm_client` parameter to `HtmlExporter.export()` and forward it to the `_report_overview_html(...)` call at line ~200. No other call sites are affected since they do not pass the parameter.

- [ ] Instantiate and inject the LLM client in `pipeline_orchestrator.py` report export call
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: At the point where `HtmlExporter(...).export(...)` is called (Stage 4 report generation), read `RVV_APPROVAL_ENDPOINT` and `RVV_APPROVAL_MODEL` env vars (same pattern as line 180); if the endpoint is set, instantiate `LMStudioClient` and pass it as `llm_client=` to `export()`. Wrap the instantiation in a try/except to handle unavailability gracefully.

- [ ] Add unit tests for the new conclusion renderer
  - Files: tests/test_report_conclusion.py
  - Approach: Write tests covering: (a) LLM client returns a string — function returns that string; (b) client is None — function returns None; (c) `LMStudioUnavailableError` is raised — function returns None without propagating the error. Use a mock or stub for `LMStudioClient.complete()`.

## Log

- 2026-06-18 Plan created by PS-plan-worker

## Acceptance Criteria

- [ ] When the pipeline orchestrator runs with `RVV_APPROVAL_ENDPOINT` set, it produces a `season_plan_report.html` that contains a Norwegian-language assessment in the overview section rather than one of the three static hardcoded strings.
- [ ] When `RVV_APPROVAL_ENDPOINT` is not set or LM Studio is unreachable, the report generation does not fail and the overview section still shows a meaningful fallback conclusion string.
- [ ] The `generate_report_conclusion` function returns `None` when called with `llm_client=None`, verified by the unit tests passing under `pytest`.
- [ ] The generated narrative output contains at least 3 sentences and is written in Norwegian, not in English or mixed language.
- [ ] All existing `pytest` tests pass after the changes without modification to test fixtures or mocks.

### 2026-06-18 — Created conclusion.py renderer module with generate_report_conclusion() that calls LMStudio for a 3-5 sentence Norwegian narrative; returns None on unavailability. Updated renderers/__init__.py docstring.
**Rationale:** Straightforward new module following existing LMStudio client patterns in the codebase.
**Findings:** New module conclusion.py created with full prompt construction and graceful LMStudio fallback.
LESSONS: none
**Files:** conclusion.py (+125/-0), __init__.py (+2/-0)
**Commit:** 72380e1 (hockey)

### 2026-06-18 — Added llm_client parameter to _report_overview_html and wired in generate_report_conclusion; falls back to static answer if LLM returns None.
**Rationale:** none
**Findings:** LLM conclusion replaces static answer only when non-empty; note stays deterministic.
LESSONS: none
**Files:** html_exporter.py (+7/-1)
**Commit:** a756dc6 (hockey)

### 2026-06-18 — Added llm_client parameter to HtmlExporter.export() and forwarded it to _report_overview_html().
**Rationale:** none
**Findings:** Straightforward parameter threading; no callers affected as default is None.
LESSONS: none
**Files:** html_exporter.py (+2/-0)
**Commit:** [pending — fill after commit]
