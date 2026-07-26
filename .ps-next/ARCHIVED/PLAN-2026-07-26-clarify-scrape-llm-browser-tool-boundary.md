# Plan: Clarify scrape-llm browser-tool boundary
**Goal:** Users can immediately tell whether `scrape-llm` is runnable in their environment and what to do when it is not.
**Created:** 2026-07-26
**Intent:** Close GitHub issue #26 by documenting the actual browser-capability boundary and making the terminal CLI guidance more explicit.

## Tasks
- [x] Document the browser-tool capability matrix for `scrape-llm`
  - Files: docs/rvv-miniputt-pipeline.md, .agents/skills/rvv/SKILL.md, .claude/commands/rvv-miniputt/scrape-llm.md
  - Approach: add a short table or bullet list that says Pi can use the extension/tool path, browser-enabled harnesses can run the recovery flow, and a plain terminal cannot; include the exact fallback advice for terminal-only sessions.
- [x] Tighten terminal CLI guidance for `rvv-miniputt scrape-llm`
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/args.py
  - Approach: update the command help/error text so it names the supported environments, explains the browser-tool requirement, and points users to the deterministic `scrape` command or recovery docs when the capability is missing.

## Notes
Issue #26 is documentation-first, but the CLI should still emit a crisp actionable boundary message so the docs and runtime behavior match.

## Acceptance Criteria
- [ ] `scrape-llm` docs clearly state which environments have browser tooling and which do not.
- [ ] Running `rvv-miniputt scrape-llm --club Holmen` in a terminal-only environment prints an explicit browser-capability message and exits without pretending to recover the source.

## Log


### 2026-07-26 — Tighten terminal CLI guidance for `rvv-miniputt scrape-llm`
**Done:** Updated the `scrape-llm` CLI help and runtime output so terminal users see the supported environments, the browser-tool requirement, and the deterministic fallback path.
**Rationale:** The runtime message now matches the new docs: Pi/browser-enabled harnesses can run the recovery flow, while plain terminal or CI sessions get a clear actionable boundary instead of a vague failure.
**Findings:** `pi_next_plan_drift` warned about the doc files from the previous task still being present in the worktree; that is expected and intentional because the docs task was completed first. The command itself now exits with an explicit browser-capability message in terminal-only mode.
**Files:** tournament_scheduler/cli/rvv_cli.py; tournament_scheduler/cli/args.py
**Commit:** not committed
### 2026-07-26 — Document the browser-tool capability matrix for `scrape-llm`
**Done:** Added an explicit browser-capability matrix for `scrape-llm` so the docs now say which environments can actually use the recovery path and which ones cannot.
**Rationale:** Issue #26 asked for clear documentation of the browser-tool boundary. The skill, pipeline guide, and Claude command docs now distinguish Pi/browser-enabled harnesses from plain terminal or CI sessions.
**Findings:** The repo already had partial boundary language; the missing piece was an explicit environment matrix and terminal-only guidance. No code change was needed for this doc task.
**Files:** .agents/skills/rvv/SKILL.md; .claude/commands/rvv-miniputt/scrape-llm.md; docs/rvv-miniputt-pipeline.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
