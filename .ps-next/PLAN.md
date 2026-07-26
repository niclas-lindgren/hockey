# Plan: Expose scrape-llm as a capability-gated CLI command
**Goal:** `scripts/rvv-miniputt scrape-llm` exists as a portable CLI entrypoint and returns an explicit, actionable browser-tool requirement instead of an argparse failure.
**Created:** 2026-07-26
**Intent:** Make the LLM-guided recovery path discoverable from a terminal, while clearly telling operators when they need Pi/browser automation instead of a plain shell.

## Tasks
- [x] Add a `scrape-llm` CLI subcommand with explicit browser-tool guidance
  - Files: tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tests/test_rvv_cli_portability.py
  - Approach: add a parser branch and handler that accepts the existing scrape-llm flags, resolves the requested club strategy, and prints a clear actionable message when browser automation is required or the club should use deterministic scraping instead; make the command exit non-zero with no traceback.
- [ ] Update docs and skill text to match the terminal/browser capability boundary
  - Files: .agents/skills/rvv/SKILL.md, .claude/commands/rvv-miniputt/scrape-llm.md, docs/rvv-miniputt-pipeline.md, docs/ai-operator-roadmap.md
  - Approach: explain which environments can actually drive the LLM browser flow, point terminal-only users at the new CLI message, and keep the slash-command examples aligned with the supported recovery path.

## Notes
Issue source: GitHub #26 (open). The repo already has the Pi slash command and strategy metadata, but the portable Python CLI currently lacks a scrape-llm subcommand and fails at argument parsing.

## Acceptance Criteria
- [ ] `scripts/rvv-miniputt scrape-llm --club Holmen` produces an explicit actionable message about browser-tool requirements instead of an invalid-choice error.
- [ ] The portable CLI help/dispatch shows `scrape-llm` as a real subcommand.
- [ ] The RVV skill/docs contain an explicit browser-tool boundary for LLM-guided scraping.
- [ ] Tests pass for the new CLI behavior.

## Log

### 2026-07-26 — Add a `scrape-llm` CLI subcommand with explicit browser-tool guidance
**Done:** Added a real `scrape-llm` parser and handler that accepts the existing flags, normalizes club aliases, and prints an explicit browser-tool boundary instead of an argparse failure.
**Rationale:** This gives terminal users a real subcommand that immediately explains the missing browser capability and points them at the browser-enabled recovery path or deterministic `scrape` when appropriate.
**Findings:** Holmen and other LLM-only sources now emit browser-tool guidance; deterministic sources are redirected to `scrape`; parser coverage and subprocess smoke coverage were added.
**Files:** tournament_scheduler/cli/args.py, tournament_scheduler/cli/rvv_cli.py, tests/test_rvv_cli_portability.py
**Commit:** e74ba86
<!-- pi-next appends entries here after each task -->
