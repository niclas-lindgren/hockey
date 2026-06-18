# Plan: Harness-driven plan critic after Stage 3

**Backlog-ref:** 141
**Created:** 2026-06-18
**Status:** open

## Intent

Give operators a concise 5-bullet harness summary of the most important season-plan issues immediately after Stage 3 completes, so they never need to open the 147KB HTML report to understand what needs fixing.

## Goal

After Stage 3 completes, the harness (Claude Code, Codex, OpenCode) reads the Stage 3 checkpoint and emits a ranked list of up to 5 issues with specific fix proposals (e.g. "club X hosts 3 out of 4 weekends in October — consider moving tournament Y to November").

## Constraints

none

## Tasks

- [x] Created plan_critic.py with generate_critic_summary(plan) returning up to 5 ranked issue strings from a SeasonPlan object. — 2026-06-18
  - Files: `tournament_scheduler/cli/plan_critic.py`
  - Approach: Implement pure-Python analysis with no LLM call: detect hosting clumps per month (>2 tournaments at same club in same month), game-count outliers, fairness-gate failures, and arena-day collisions; rank by severity and format each as a single actionable Norwegian or English sentence.

- [ ] Replace the `_run_approval_gate` placeholder in `pipeline_orchestrator.py` with a call to `generate_critic_summary`, print the summary to the Rich console, and continue to Stage 4.
  - Files: `tournament_scheduler/cli/pipeline_orchestrator.py`
  - Approach: Import `generate_critic_summary` from `plan_critic`, call it with `plan_checkpoint["plan"]` after Stage 3 completes, and print each bullet using `_console.print` with a `[bold cyan]` prefix; the gate still always returns `True` so Stage 4 is not blocked.

- [ ] Add `rvv-miniputt critic` CLI subcommand that reads an existing Stage 3 checkpoint from disk and prints the harness summary without running the full pipeline.
  - Files: `tournament_scheduler/cli/rvv_cli.py`, `tournament_scheduler/cli/args.py`
  - Approach: Register a `critic` subcommand in `args.py` that accepts `--work-dir` (default `.pipeline`), then in `rvv_cli.py` load `stage3_planning.json` via `state.py`, call `generate_critic_summary`, and print with Rich — mirrors the pattern used by `rvv-miniputt status`.

- [ ] Write unit tests for `generate_critic_summary` covering: hosting clump detection, game-count outlier detection, fairness-gate failure, arena-day collision, and the happy-path (no issues returns empty or minimal list).
  - Files: `tests/test_plan_critic.py`
  - Approach: Construct minimal plan dicts in-memory (no file I/O) for each scenario, assert the returned list contains the expected issue string, and assert the list never exceeds 5 items.

- [ ] Extend `reporting.py` / `checkpoint_printer.py` so that `rvv-miniputt status` includes a one-line critic summary when a valid Stage 3 checkpoint is present.
  - Files: `tournament_scheduler/cli/reporting.py`, `tournament_scheduler/cli/checkpoint_printer.py`
  - Approach: Call `generate_critic_summary` inside `_build_status_text` when `stage3` checkpoint data is available, and append a "Critic: N issues found" line to the status panel — keep it short (single line) so it does not clutter the status view.

## Log

## Acceptance Criteria

When Stage 3 completes, the harness produces and outputs a 5-bullet summary to stdout that contains specific issue rankings with fix proposals.
The harness-driven plan critic reads the Stage 3 checkpoint JSON file and returns a ranked list of up to 5 issues with actionable suggestions.
The operator can observe the harness summary in console output after Stage 3 completes, without needing to open or parse the 147KB HTML report.
The harness summary output contains at least one issue with a specific fix proposal such as a host-clump or game-count outlier notice when such a condition is present in the plan.
Running `rvv-miniputt critic` against a completed Stage 3 checkpoint prints the ranked issue list and exits without running the full pipeline.

### 2026-06-18 — Created plan_critic.py with generate_critic_summary(plan) returning up to 5 ranked issue strings from a SeasonPlan object.
**Rationale:** Pure-Python analysis with no LLM call; severity buckets assembled in ranked order and capped at 5.
**Findings:** Module imports cleanly, all existing tests pass.
LESSONS: none
**Files:** tournament_scheduler/cli/plan_critic.py (+131/-0)
**Commit:** [pending — fill after commit]
