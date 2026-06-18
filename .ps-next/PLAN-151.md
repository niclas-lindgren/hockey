# Plan: Headless LLM fallback for pipeline judgment
**Goal:** Add headless LLM fallback for pipeline judgment when no active harness session is present (e.g. cron jobs, CI): when the pipeline runs standalone via 'scripts/rvv-miniputt run' with no orchestrating harness, judgment calls between stages should fall back to a direct API call (Anthropic API, OpenAI API, or llm-bridge for local). Backend selected by env var (RVV_JUDGE_BACKEND=claude|openai|llm-bridge). This is only the fallback path — when running from Claude Code, Pi, ChatGPT or OpenCode, the harness itself is the judge and this code is not reached.
**Created:** 2026-06-18
**Intent:** Enable the pipeline to run autonomously in cron/CI contexts without requiring an active harness session for inter-stage judgment, while preserving existing harness-driven judgment as the primary path.
**Backlog-ref:** 151
**Constraints:** none

## Tasks
- [x] Created llm_judge package with LLMJudge ABC, three backends (Claude, OpenAI, LLMBridgeJudgeBackend), and a create_judge() factory that reads RVV_JUDGE_BACKEND. — 2026-06-18
  - Files: tournament_scheduler/llm_judge/__init__.py, tournament_scheduler/llm_judge/interface.py, tournament_scheduler/llm_judge/backends.py
  - Approach: Define a `LLMJudge` abstract base class with a single `judge(prompt: str) -> str` method, then implement `ClaudeJudgeBackend` (Anthropic SDK or httpx), `OpenAIJudgeBackend` (openai SDK or httpx), and `LLMBridgeJudgeBackend` (httpx to localhost:1234). A `create_judge(backend: str) -> LLMJudge` factory reads `RVV_JUDGE_BACKEND` and raises `ValueError` on unknown/missing values.

- [x] Created harness.py with is_harness_active() and get_judge_if_headless(); exported both from __init__.py. — 2026-06-18
  - Files: tournament_scheduler/llm_judge/harness.py, tournament_scheduler/llm_judge/__init__.py
  - Approach: Implement `is_harness_active() -> bool` that checks for well-known harness indicators (e.g. `PI_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `OPENCODE_SESSION_ID` env vars, or a `RVV_HARNESS` override). Export `get_judge_if_headless() -> LLMJudge | None` which returns `None` when a harness is active, so callers can skip judgment without duplicating the detection logic.

- [x] Added _judge_stage() helper inside _cmd_run() and wired it after Stage 1, 2, and 3 success paths; returns 1 on ABORT verdict, continues otherwise. — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: In `_cmd_run()`, after each stage checkpoint is written as `done`, call `get_judge_if_headless()` and if a judge is returned, send a structured prompt summarising the stage output and requesting a proceed/abort decision. On an `abort` verdict, log the judge's reasoning and exit with a non-zero code; on `proceed` or when no judge is present, continue to the next stage.

- [x] Created prompts.py with build_stage_prompt() covering config/stage1, scraping/stage2, and planning/stage3; exported from __init__.py; orchestrator now uses dict summaries and build_stage_prompt. — 2026-06-18
  - Files: tournament_scheduler/llm_judge/prompts.py
  - Approach: Create `build_stage_prompt(stage_name: str, checkpoint_summary: dict) -> str` that produces a concise Norwegian or English prompt describing what the stage produced and asking whether the pipeline should continue. Each stage (config, scraping, planning) gets a tailored template that includes key metrics from the checkpoint JSON.

- [ ] Persist judgment results into the pipeline log and checkpoint state
  - Files: tournament_scheduler/pipeline/state.py, tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Extend `PipelineState` with an optional `judgment` field on each stage checkpoint (verdict, reasoning, backend used, timestamp). The orchestrator writes this via a new `write_judgment(stage, judgment_result)` helper on `PipelineState` so results are visible in `.pipeline/stage*.json` files and in per-run logs already written by `_write_run_log`.

- [ ] Add unit tests for the judge backends, harness detection, and orchestrator integration
  - Files: tests/test_llm_judge.py, tests/test_pipeline_orchestrator_judgment.py
  - Approach: Test `is_harness_active()` by setting/unsetting the relevant env vars; mock httpx/SDK calls to verify each backend sends the right payload and surfaces errors; test that `_cmd_run()` calls the judge between stages when headless and skips it when a harness env var is set.

- [ ] Document the headless judge configuration in docs and CLI help
  - Files: README.md, docs/rvv-miniputt-pipeline.md
  - Approach: Add a short "Headless / CI usage" section explaining `RVV_JUDGE_BACKEND` values and any required API key env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`); update CLI `--help` output or inline comments in `rvv_cli.py` to mention `RVV_JUDGE_BACKEND`.

## Notes
The harness-driven judgment path (Claude Code, Pi, ChatGPT, OpenCode) must remain completely unaffected. All new code is conditional on `get_judge_if_headless()` returning non-None. The llm-bridge backend connects to localhost:1234 matching the same host used by existing LLM Bridge MCP tooling in this repo.

## Acceptance Criteria
- [ ] `run:python3 -m pytest -q tests/test_llm_judge.py tests/test_pipeline_orchestrator_judgment.py`
- [ ] `grep:tournament_scheduler/llm_judge/interface.py contains class LLMJudge`
- [ ] `grep:tournament_scheduler/llm_judge/harness.py contains is_harness_active`
- [ ] `grep:tournament_scheduler/cli/pipeline_orchestrator.py contains get_judge_if_headless`
- [ ] `grep:docs/rvv-miniputt-pipeline.md contains RVV_JUDGE_BACKEND`

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-18 — Created llm_judge package with LLMJudge ABC, three backends (Claude, OpenAI, LLMBridgeJudgeBackend), and a create_judge() factory that reads RVV_JUDGE_BACKEND.
**Rationale:** Implemented with stdlib urllib only to avoid new dependencies; factory raises ValueError for missing/unknown backend as required.
**Findings:** Package imports cleanly; ValueError raised correctly for empty and unknown backend values; LLMBridgeJudgeBackend instantiates without credentials.
LESSONS: none
**Files:** tournament_scheduler/llm_judge/__init__.py (+62), backends.py (+154), interface.py (+26)
**Commit:** 4b18bc8 (hockey)

### 2026-06-18 — Created harness.py with is_harness_active() and get_judge_if_headless(); exported both from __init__.py.
**Rationale:** Checked PI_SESSION_ID, CLAUDE_CODE_SESSION_ID, OPENCODE_SESSION_ID, and RVV_HARNESS override; circular import avoided via local import inside get_judge_if_headless.
**Findings:** All assertions pass: harness detection works correctly for each env var; returns None when harness active and LLMBridgeJudgeBackend in headless mode.
LESSONS: none
**Files:** tournament_scheduler/llm_judge/harness.py (+67), __init__.py (+11/-1)
**Commit:** 39008f2 (hockey)

### 2026-06-18 — Added _judge_stage() helper inside _cmd_run() and wired it after Stage 1, 2, and 3 success paths; returns 1 on ABORT verdict, continues otherwise.
**Rationale:** Gracefully handles missing RVV_JUDGE_BACKEND (returns True/proceed) and judge call failures (logs warning, continues) so existing workflows are not broken.
**Findings:** Syntax valid; judge hook fires only in headless runs due to get_judge_if_headless(); abort path returns non-zero exit code as required.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+59)
**Commit:** d041b59 (hockey)

### 2026-06-18 — Created prompts.py with build_stage_prompt() covering config/stage1, scraping/stage2, and planning/stage3; exported from __init__.py; orchestrator now uses dict summaries and build_stage_prompt.
**Rationale:** Each builder uses best-effort key access so missing keys degrade gracefully; both canonical ('stage1') and descriptive ('config') names accepted.
**Findings:** Syntax valid; prompts produce structured PROCEED/ABORT instructions tailored to each stage's key metrics.
LESSONS: none
**Files:** tournament_scheduler/llm_judge/prompts.py (+160), __init__.py (+2), pipeline_orchestrator.py (+52/-22)
**Commit:** [pending — fill after commit]
