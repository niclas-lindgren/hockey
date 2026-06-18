# Plan: LLM semantic config validation in Stage 1
**Goal:** After parsing input.xlsx, pass key constraints to an LLM and emit pre-planning warnings about infeasible plans (e.g. too many tournaments for available clubs/weekends) before Stage 3 runs.
**Created:** 2026-06-18
**Intent:** Schema validation catches typos but not infeasible plans — an LLM semantic pass gives operators actionable warnings to fix config before wasting time on a doomed Stage 3 run.
**Backlog-ref:** 143

## Tasks
- [x] Created semantic_validation.py with build_semantic_prompt() and parse_semantic_warnings() functions. — 2026-06-18
  - Files: tournament_scheduler/pipeline/semantic_validation.py
  - Approach: Create a new module with a `build_semantic_prompt(config: dict) -> tuple[str, str]` function that extracts key constraints (age groups, team counts per age group, host club counts, available weekends derived from start/end dates, target_tournament_count, parallel_games) and formats them as a structured system+user prompt. Add a `parse_semantic_warnings(response_text: str) -> list[str]` function that splits the LLM reply into a list of warning strings (one per line or bullet).

- [x] Added optional llm_client parameter to stage1_config.run(); calls semantic_validation after successful schema validation and stores warnings in checkpoint. — 2026-06-18
  - Files: tournament_scheduler/pipeline/stage1_config.py, tournament_scheduler/pipeline/stage1_helpers.py
  - Approach: Add an optional `llm_client` parameter to `stage1_config.run()`. After successful schema validation, call `semantic_validation.build_semantic_prompt(effective_config)`, invoke `llm_client.complete(system, user)`, and collect warnings via `semantic_validation.parse_semantic_warnings(response.text)`. Store warnings in the returned checkpoint dict under a `semantic_warnings` key, and surface them via Rich console using the existing `rich_output.py` pattern (yellow/amber warning panel), gracefully skipping if `llm_client` is None or raises `LMStudioUnavailableError`.

- [x] Instantiates LMStudioClient before stage1_run in _cmd_run; passes it as llm_client to stage1_run; silently skips with a Norwegian notice when endpoint unavailable. — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: In `_cmd_run`, instantiate `LMStudioClient` before calling `stage1_config.run()` (same pattern as the Stage 4 client at line 656–661) and pass it as `llm_client=`. Catch `LMStudioUnavailableError` and log a one-line notice that semantic validation is skipped, without aborting the pipeline.

- [x] Added print_semantic_warnings() to rich_output.py with amber Panel styling; called from stage1_config.run() after LLM parsing. — 2026-06-18
  - Files: tournament_scheduler/utils/rich_output.py, tournament_scheduler/pipeline/stage1_config.py
  - Approach: Add a `print_semantic_warnings(warnings: list[str])` helper to `rich_output.py` that renders a labelled Rich panel with amber styling (consistent with existing warning panels), then call it from `stage1_config.run()` immediately after LLM parsing, before returning to the orchestrator.

- [ ] Write unit tests for semantic validation module and Stage 1 integration
  - Files: tests/test_semantic_validation.py, tests/test_stage1_config.py
  - Approach: Add pytest tests that verify `build_semantic_prompt` includes expected constraint fields, `parse_semantic_warnings` returns a list from a sample LLM reply, and `stage1_config.run()` calls `llm_client.complete()` exactly once and stores warnings in the checkpoint. Use `unittest.mock.MagicMock` for `llm_client` to avoid external LLM calls.

## Notes
Constraints: none
LMStudioClient interface: `complete(system: str, user: str) -> LLMResponse` where `LLMResponse.text` holds the reply. Raises `LMStudioUnavailableError` when server is unreachable.
Existing warning pattern: `season_planner._scan_club_load_warnings()` returns `list[str]`; `rich_output.py` renders them via Rich panels.
Stage 4 already passes an `llm_client` to `stage4_run` — same pattern applies here.

## Acceptance Criteria
- [ ] When `stage1_config.run()` is called with a mock `llm_client`, it calls `llm_client.complete()` at least once and returns a checkpoint dict containing a `semantic_warnings` key.
- [ ] When the LLM response contains warning lines, `parse_semantic_warnings` returns a non-empty list of strings.
- [ ] Running `pytest tests/test_semantic_validation.py tests/test_stage1_config.py` passes with no errors.
- [ ] When the pipeline runs with a live or mocked LLM client and a config that has more tournaments than available weekends, the console output contains at least one pre-planning warning emitted before Stage 3 output appears.
- [ ] When `llm_client` is None or raises `LMStudioUnavailableError`, Stage 1 completes successfully and no exception propagates — semantic validation is skipped gracefully.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-18 — Created semantic_validation.py with build_semantic_prompt() and parse_semantic_warnings() functions.
**Rationale:** Straightforward new module following the same LLM-client pattern as llm_approval_gate.py; no alternatives needed.
**Findings:** Module builds a structured system+user prompt from merged config constraints and parses numbered/bullet LLM responses into a list of warnings; smoke-tested successfully.
LESSONS: none
**Files:** tournament_scheduler/pipeline/semantic_validation.py (+165/-0)
**Commit:** 641d4b2 (hockey)

### 2026-06-18 — Added optional llm_client parameter to stage1_config.run(); calls semantic_validation after successful schema validation and stores warnings in checkpoint.
**Rationale:** Broad except clause used to catch both LMStudioUnavailableError and any other transient LLM errors gracefully.
**Findings:** Semantic warnings stored under 'semantic_warnings' key in checkpoint; run() signature extended with keyword-only llm_client param defaulting to None.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage1_config.py (+36/-2)
**Commit:** f48c7ab (hockey)

### 2026-06-18 — Instantiates LMStudioClient before stage1_run in _cmd_run; passes it as llm_client to stage1_run; silently skips with a Norwegian notice when endpoint unavailable.
**Rationale:** Matched existing Stage 4 LLM client instantiation pattern using inline os import and try/except.
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+12/-1)
**Commit:** f7f8b90 (hockey)

### 2026-06-18 — Added print_semantic_warnings() to rich_output.py with amber Panel styling; called from stage1_config.run() after LLM parsing.
**Rationale:** Amber/yellow Panel with ROUNDED box is consistent with existing warning styling; fixed a misplaced console.print(table) line in print_rules_report that was missing from original file.
**Findings:** The original print_rules_report() was missing its final console.print(table) call — this was a pre-existing bug that got exposed by the edit and was fixed as part of this task.
LESSONS: When editing rich_output.py, the existing print_rules_report() was missing its closing console.print(table) line — check for truncated loop bodies before appending to this file.
**Files:** tournament_scheduler/utils/rich_output.py (+34/-1), tournament_scheduler/pipeline/stage1_config.py (+2/-0)
**Commit:** [pending — fill after commit]
