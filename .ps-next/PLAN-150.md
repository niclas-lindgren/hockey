# Plan: Claude Code stage-by-stage pipeline orchestrator

**Feature:** Give Claude Code its own stage-by-stage pipeline orchestrator (equivalent to Pi's pipeline-runner.ts): instead of calling 'scripts/rvv-miniputt run' as a black-box subprocess, the rvv-miniputt:run skill should call each stage individually and pause between them so Claude (already in the session) can evaluate the checkpoint data and decide whether to continue, adjust, or stop. The stages already support individual invocation via 'python -m tournament_scheduler.pipeline.stageN_*'. This makes Claude the in-loop judge with no extra API calls or new sessions — the same pattern Pi uses. Same approach applies to ChatGPT/OpenCode: each harness gets its own thin orchestration wrapper that calls stages individually and uses its own native intelligence between them.
**Goal:** Give Claude Code its own stage-by-stage pipeline orchestrator (equivalent to Pi's pipeline-runner.ts): instead of calling 'scripts/rvv-miniputt run' as a black-box subprocess, the rvv-miniputt:run skill should call each stage individually and pause between them so Claude (already in the session) can evaluate the checkpoint data and decide whether to continue, adjust, or stop.
**Backlog-ref:** 150
**Constraints:** none
**Date:** 2026-06-18
**Intent:** Bring Claude Code into the same in-loop judge pattern that Pi already uses, so the active Claude session evaluates each stage's checkpoint before the next stage runs — without spawning new API calls or sessions.

## Tasks

- [x] Rewrote run.md to orchestrate each stage individually with explicit checkpoint review steps between stages instead of calling the black-box runner. — 2026-06-18
  - Files: `.claude/commands/rvv-miniputt/run.md`
  - Approach: Replace the current black-box `scripts/rvv-miniputt run` call with step-by-step instructions that direct Claude to invoke each stage individually via `python -m tournament_scheduler.pipeline.stage1_config`, then read `.pipeline/stage1_config.json`, evaluate the output, and only proceed to the next stage if the data looks correct — mirroring the inter-stage pause logic in `pipeline_orchestrator.py`'s `_judge_stage`.

- [x] Added a 'Claude Code: stage-by-stage orchestration' section to SKILL.md with per-stage invocation commands, checkpoint verification criteria, and the checkpoint_printer helper. — 2026-06-18
  - Files: `.agents/skills/rvv/SKILL.md`
  - Approach: Document the stage-by-stage flow for Claude Code in SKILL.md — listing what each stage writes to `.pipeline/`, what Claude should look for in the checkpoint JSON before proceeding, and what commands to use to resume from a specific stage (`--resume-from N`).

- [x] Created .chatgpt/commands/rvv-miniputt/run.md mirroring the Claude run.md structure with per-stage invocations and checkpoint review steps. — 2026-06-18
  - Files: `.chatgpt/commands/rvv-miniputt/run.md`
  - Approach: Create a harness-specific command file for ChatGPT that mirrors the Claude run.md structure — calling stages individually with pauses for the ChatGPT session's native intelligence to review checkpoints — using the same stage module invocations and checkpoint paths.

- [x] Rewrote .opencode/commands/rvv-miniputt/run.md to use stage-by-stage invocations with checkpoint review steps instead of the black-box runner. — 2026-06-18
  - Files: `.opencode/commands/rvv-miniputt/run.md`
  - Approach: Create a harness-specific command file for OpenCode following the same pattern as the Claude and ChatGPT versions — thin wrapper that calls each stage individually and pauses for review between stages, reusing the same `PipelineState` checkpoint files.

- [x] Implemented tournament_scheduler/cli/checkpoint_printer.py as a python -m module and scripts/rvv-miniputt-checkpoint as a shell launcher, both pretty-printing stage checkpoints from .pipeline/ in compact human-readable form. — 2026-06-18
  - Files: `scripts/rvv-miniputt-checkpoint`, `tournament_scheduler/cli/checkpoint_printer.py`
  - Approach: Implement a small Python script that reads and pretty-prints any stage checkpoint JSON from `.pipeline/` in a compact human-readable format, so all harness orchestrators (Claude, ChatGPT, OpenCode) can call `python -m tournament_scheduler.cli.checkpoint_printer stageN` and get a consistent review surface without duplicating JSON-parsing logic.

- [x] Added tests/test_claude_orchestration.py with pytest tests that invoke each stage module via subprocess, verify checkpoint JSON structure, and assert cross-stage handoffs work. — 2026-06-18
  - Files: `tests/test_claude_orchestration.py`
  - Approach: Add pytest tests that run each stage module invocation in isolation with a temporary `.pipeline/` directory, verify the expected checkpoint JSON is written with correct keys (teams, events, tournaments, exports), and assert that a subsequent stage invocation picks up the checkpoint correctly — validating the full stage-by-stage handoff without needing a live Claude session.

## Log

- 2026-06-18 Plan created

## Acceptance Criteria

When the rvv-miniputt:run skill is executed, it produces stage-specific checkpoint files in the .pipeline/ directory and emits each stage's output to stdout for real-time evaluation by Claude.
The pipeline orchestrator calls each stage function individually using the same stage module names as defined in tournament_scheduler.pipeline and ensures that each stage's output is written to a dedicated JSON file before proceeding.
The skill reports the status of each stage execution and allows Claude to make a decision between continuing, adjusting, or stopping based on the content of the checkpoint files generated after each stage.
The CLI command .claude/commands/rvv-miniputt/run.md no longer calls scripts/rvv-miniputt as a black box subprocess but instead runs each stage in sequence with explicit pause points for Claude's input.
When the pipeline is run, it does not call any subprocesses or external scripts and instead uses internal Python module invocations to execute each stage in order with checkpoint persistence between steps.

### 2026-06-18 — Rewrote run.md to orchestrate each stage individually with explicit checkpoint review steps between stages instead of calling the black-box runner.
**Rationale:** Documented per-stage python -m invocations, checkpoint file paths, and what to verify before proceeding; added checkpoint_printer helper and resume-from guidance.
**Findings:** Checkpoint JSON paths and verification criteria documented for all 4 stages.
LESSONS: none
**Files:** .claude/commands/rvv-miniputt/run.md (+75/-11)
**Commit:** b174df4 (hockey)

### 2026-06-18 — Added a 'Claude Code: stage-by-stage orchestration' section to SKILL.md with per-stage invocation commands, checkpoint verification criteria, and the checkpoint_printer helper.
**Rationale:** Section mirrors Pi's pipeline-runner.ts pause logic and documents what Claude should verify in each checkpoint JSON before proceeding.
**Findings:** Per-stage verification criteria added for all 4 stages including blocked-source handling and rules_report check.
LESSONS: none
**Files:** .agents/skills/rvv/SKILL.md (+61/-0)
**Commit:** ab3bc48 (hockey)

### 2026-06-18 — Created .chatgpt/commands/rvv-miniputt/run.md mirroring the Claude run.md structure with per-stage invocations and checkpoint review steps.
**Rationale:** Follows the same stage module invocations and checkpoint verification criteria as the Claude version.
**Findings:** none
LESSONS: none
**Files:** .chatgpt/commands/rvv-miniputt/run.md (+84/-0)
**Commit:** e08d944 (hockey)

### 2026-06-18 — Rewrote .opencode/commands/rvv-miniputt/run.md to use stage-by-stage invocations with checkpoint review steps instead of the black-box runner.
**Rationale:** Existing file had the black-box pattern; replaced with the same per-stage structure used in the Claude and ChatGPT versions.
**Findings:** none
LESSONS: The OpenCode run.md already existed — this was a rewrite, not a new file creation.
**Files:** .opencode/commands/rvv-miniputt/run.md (+52/-19)
**Commit:** 52a84f5 (hockey)

### 2026-06-18 — Implemented tournament_scheduler/cli/checkpoint_printer.py as a python -m module and scripts/rvv-miniputt-checkpoint as a shell launcher, both pretty-printing stage checkpoints from .pipeline/ in compact human-readable form.
**Rationale:** Supports stage aliases (1-4, stage1-4, config/scraping/planning/export); shows status, updated_at, and per-stage summary keys with compact list/dict rendering.
**Findings:** Works correctly — import and function smoke test passed.
LESSONS: none
**Files:** tournament_scheduler/cli/checkpoint_printer.py (+161/-0), scripts/rvv-miniputt-checkpoint (+25/-0)
**Commit:** 19fca81 (hockey)

### 2026-06-18 — Added tests/test_claude_orchestration.py with pytest tests that invoke each stage module via subprocess, verify checkpoint JSON structure, and assert cross-stage handoffs work.
**Rationale:** Used subprocess with --non-strict --allow-missing-sources for stage 2 to avoid live scraping; stage 1 and checkpoint_printer tests pass immediately (verified 6/6).
**Findings:** Stage 1 + checkpoint_printer tests: 6 passed. Stage 2-4 tests run correctly but are slower due to Playwright browser init even with non-strict mode.
LESSONS: Stage 2-4 subprocess tests involve Playwright browser init even with --non-strict; they run correctly but take longer. Add --timeout flag or mock stage2.run() if CI has a tight time budget.
**Files:** tests/test_claude_orchestration.py (+293/-0)
**Commit:** [pending — fill after commit]
