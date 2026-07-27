# Plan: Make scrape-llm recovery explicit and terminal-scriptable
**Goal:** `rvv-miniputt scrape-llm` clearly distinguishes deterministic sources, browser-enabled recovery, and terminal-only recovery flow using `recovery-targets`/`recovery-inject`.
**Created:** 2026-07-27
**Intent:** Close the gap where a terminal-only user is pointed at an interactive browser skill without a scriptable recovery path.

## Tasks
- [x] Update CLI recovery guidance for `scrape-llm`
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/pipeline/source_health.py
  - Approach: revise the output/suggested_actions so direct scrapers point to `scrape`, browser-only sources mention browser-enabled sessions, and terminal-only sessions are told to use `recovery-targets` + `recovery-inject` with clear next steps.
- [ ] Sync docs and regression coverage
  - Files: .claude/commands/rvv-miniputt/scrape-llm.md, .claude/commands/rvv-miniputt/run.md, .agents/skills/rvv/SKILL.md, tests/test_rvv_cli_portability.py, tests/test_source_health.py
  - Approach: document the terminal-only recovery flow and update tests to lock down the new message content and command references.

## Notes
- `rvv-miniputt scrape-llm` currently prints browser-tool guidance only; `recovery-targets` and `recovery-inject` already provide a shell-friendly recovery bridge.
- Holmen/Sportello already has a deterministic scraper, so direct sources should continue to prefer `scrape`.

## Acceptance Criteria
- [ ] `rvv-miniputt scrape-llm --club Jar` prints an explicit browser-enabled warning and mentions the terminal-only recovery commands.
- [ ] `rvv-miniputt scrape-llm --club Holmen` prints a deterministic `scrape` recommendation instead of browser-tool guidance.
- [ ] The docs and skill notes update to show `recovery-targets` and `recovery-inject` as the fallback for plain terminal sessions.

## Log

### 2026-07-27 — Update CLI recovery guidance for `scrape-llm`
**Done:** Clarified the CLI messages for direct-scraper and browser-only sources so terminal users see a deterministic scrape path or an explicit recovery-targets/recovery-inject fallback.
**Rationale:** This closes the user-facing guidance gap in the command itself and in source-health suggestions without changing scraper behavior.
**Findings:** Blocked sources now get a terminal-only recovery path in addition to the browser-enabled path; direct sources continue to steer to scrape.
**Files:** tournament_scheduler/cli/rvv_cli.py; tournament_scheduler/pipeline/source_health.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
