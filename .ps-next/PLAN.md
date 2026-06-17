# Plan: Portable harness-neutral RVV/Pi-next entrypoints
**Goal:** Codex/Claude/OpenCode can invoke the existing RVV and pi-next workflows through repo-local CLI/script entrypoints without depending on Pi slash-command adapters, and the docs clearly explain what remains Pi-specific.
**Created:** 2026-06-17
**Intent:** Reduce harness lock-in so the same project workflows are accessible from non-Pi coding agents while keeping Pi adapters thin.
**Backlog-ref:** 121

## Tasks
- [ ] Extract RVV slash-command logic behind scriptable CLI entrypoints
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/reporting.py, tournament_scheduler/cli/pipeline_orchestrator.py, .pi/extensions/rvv-miniputt.ts, scripts/rvv-miniputt
  - Approach: Add any missing `rvv-miniputt` subcommands/flags needed to cover the slash-command surface from the repo CLI, create a small repo-local launcher script, and make the Pi extension delegate to those harness-neutral entrypoints where practical instead of embedding command-only logic.
- [ ] Add regression coverage for the new cross-harness entrypoints and portability contract
  - Files: tests/test_rvv_cli_portability.py, tests/test_pi_next_skill_boundary.py, tests/test_rvv_skill_portability.py
  - Approach: Add focused tests for the new CLI/script-accessible behavior and assert the skill/docs language that defines portable vs Pi-only boundaries.
- [ ] Document cross-harness usage and Pi-specific boundaries for RVV and pi-next
  - Files: README.md, docs/rvv-miniputt-pipeline.md, .agents/skills/rvv/SKILL.md, .agents/skills/pi-next/SKILL.md
  - Approach: Update the operator docs and skill instructions so non-Pi agents are pointed at `rvv-miniputt`/repo scripts while Pi users keep slash commands, and explicitly call out features that still require Pi adapters or Pi-managed tools.

## Notes
Search before changing behavior: the RVV Python CLI already exposes most pipeline operations, while the Pi extension currently owns `status`, `logs`, `guide`, and agent-callable tool wiring. Keep the portability work additive and preserve existing Pi slash commands.

## Acceptance Criteria
- [ ] `run:python3 -m pytest -q tests/test_rvv_cli_portability.py tests/test_pi_next_skill_boundary.py tests/test_rvv_skill_portability.py`
- [ ] `run:bash scripts/rvv-miniputt status`
- [ ] `grep:README.md contains Cross-harness usage`
- [ ] `grep:.agents/skills/rvv/SKILL.md contains Non-Pi / cross-harness usage`
- [ ] `grep:.agents/skills/pi-next/SKILL.md contains harness-neutral`

## Log
<!-- pi-next appends entries here after each task -->
