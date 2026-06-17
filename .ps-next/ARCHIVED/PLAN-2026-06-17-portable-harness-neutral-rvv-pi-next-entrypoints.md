# Plan: Portable harness-neutral RVV/Pi-next entrypoints
**Goal:** Codex/Claude/OpenCode can invoke the existing RVV and pi-next workflows through repo-local CLI/script entrypoints without depending on Pi slash-command adapters, and the docs clearly explain what remains Pi-specific.
**Created:** 2026-06-17
**Intent:** Reduce harness lock-in so the same project workflows are accessible from non-Pi coding agents while keeping Pi adapters thin.
**Backlog-ref:** 121

## Tasks
- [x] Extract RVV slash-command logic behind scriptable CLI entrypoints
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/reporting.py, tournament_scheduler/cli/pipeline_orchestrator.py, .pi/extensions/rvv-miniputt.ts, scripts/rvv-miniputt
  - Approach: Add any missing `rvv-miniputt` subcommands/flags needed to cover the slash-command surface from the repo CLI, create a small repo-local launcher script, and make the Pi extension delegate to those harness-neutral entrypoints where practical instead of embedding command-only logic.
- [x] Add regression coverage for the new cross-harness entrypoints and portability contract
  - Files: tests/test_rvv_cli_portability.py, tests/test_pi_next_skill_boundary.py, tests/test_rvv_skill_portability.py
  - Approach: Add focused tests for the new CLI/script-accessible behavior and assert the skill/docs language that defines portable vs Pi-only boundaries.
- [x] Document cross-harness usage and Pi-specific boundaries for RVV and pi-next
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



### 2026-06-17 — Document cross-harness usage and Pi-specific boundaries for RVV and pi-next
**Done:** Updated the README, RVV pipeline guide, and both skill docs to point non-Pi agents at repo-local CLI/scripts while explicitly listing what stays in the Pi adapter layer.
**Rationale:** The portable entrypoints are only useful if operators and future agents can discover them quickly and understand which behaviors still depend on Pi-managed slash commands/tools.
**Findings:** By the time this task was marked done the doc changes were already committed alongside the portability tests, so `pi_next_plan_drift` showed no remaining file diff for the planned docs even though the task had been completed in commit 7b09741.
**Files:** M README.md, docs/rvv-miniputt-pipeline.md, .agents/skills/rvv/SKILL.md, .agents/skills/pi-next/SKILL.md, .ps-next/PLAN.md
**Commit:** 7b09741
### 2026-06-17 — Add regression coverage for the new cross-harness entrypoints and portability contract
**Done:** Added portability regression tests for the repo-local RVV launcher/CLI flags plus skill-boundary assertions for RVV and pi-next cross-harness guidance.
**Rationale:** The new launcher and docs need lightweight tests that fail if future changes remove the portable entrypoints or blur the Pi-only boundary.
**Findings:** `pi_next_plan_drift` ignored the new test files until they were staged because untracked files are absent from `git diff --name-only`; the portability tests intentionally rely on the updated docs/skills, so they were committed together with that documentation surface.
**Files:** A tests/test_rvv_cli_portability.py, tests/test_rvv_skill_portability.py; M tests/test_pi_next_skill_boundary.py; M README.md, docs/rvv-miniputt-pipeline.md, .agents/skills/{rvv,pi-next}/SKILL.md, .ps-next/PLAN.md
**Commit:** 7b09741
### 2026-06-17 — Extract RVV slash-command logic behind scriptable CLI entrypoints
**Done:** Added a repo-local `scripts/rvv-miniputt` launcher, expanded the Python CLI with portable `status`/structured `logs` support and run parity flags, and pointed the Pi RVV extension at those harness-neutral CLI entrypoints for status/logs/calendars.
**Rationale:** Using the existing Python CLI as the portable surface keeps non-Pi agents on repo-native commands while leaving Pi-specific streaming run behavior and guide UX in the extension layer.
**Findings:** Untracked files do not appear in `pi_next_plan_drift` until staged; the new launcher script showed as missing there until commit staging. Existing historical JSONL logs can lack finalized run metadata, so `logs list` may show `─` for older start times.
**Files:** A scripts/rvv-miniputt; M tournament_scheduler/cli/{args.py,pipeline_orchestrator.py,reporting.py,rvv_cli.py}; M .pi/extensions/rvv-miniputt.ts; M .ps-next/PLAN.md
**Commit:** 146d20d
<!-- pi-next appends entries here after each task -->
