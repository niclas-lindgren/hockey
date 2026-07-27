# Plan: Make browser-only recovery scriptable in docs
**Goal:** Terminal-only users can recover blocked JS calendar sources by following an explicit, documented recovery bridge without needing a browser controller.
**Created:** 2026-07-27
**Intent:** Close GitHub issue #26 by making the supported recovery path easy to discover, copy, and script from a plain shell.

## Tasks
- [x] Make the terminal-only recovery bridge explicit across the pipeline, skill, and launcher docs
  - Files: docs/rvv-miniputt-pipeline.md, tests/test_rvv_skill_boundary.py, .agents/skills/rvv/SKILL.md, .claude/commands/rvv-miniputt/scrape-llm.md
  - Approach: expand the browser-capability boundary and recovery sections with a copy/paste shell recipe that uses `scripts/rvv-miniputt recovery-targets`, `python3 -m tournament_scheduler.cli.rvv_cli recovery-inject --source ...`, and `scrape-merge`, then lock the guidance with regression coverage that mentions the same bridge.

## Notes
- Existing CLI guidance already distinguishes browser-enabled sessions from plain terminal/CI sessions; this plan makes the docs surface match that behavior more concretely.
- Holmen/Sportello is the main motivating example, but the wording should stay generic for any future JS-only recovery source.

## Acceptance Criteria
- [ ] `docs/rvv-miniputt-pipeline.md` explicitly shows the terminal-only recovery flow with `recovery-targets`, `recovery-inject`, and `scrape-merge`.
- [ ] The RVV skill and launcher docs show `recovery-targets`, `recovery-inject`, and the browser-capability boundary for `scrape-llm`.
- [ ] The regression test contains the terminal-only recovery bridge and browser-capability boundary in its assertions.

## Log

### 2026-07-27 — Make the terminal-only recovery bridge explicit across the pipeline, skill, and launcher docs
**Done:** Expanded the browser-capability and recovery guidance so terminal-only users get a copy/paste bridge from `recovery-targets` to `recovery-inject`/`scrape-merge`, and locked it down with regression coverage.
**Rationale:** Issue #26 asked for a scriptable, non-ambiguous recovery path for browser-only sources; the docs now show the full shell flow and the skill/launcher docs repeat the same boundary instead of pointing only at interactive browser tooling.
**Findings:** Holmen remains on the deterministic Sportello path; the browser-only recovery bridge is meant for future JS-only sources. The existing CLI guidance was already close, but the docs needed to make the plain-terminal flow explicit and test-covered.
**Files:** docs/rvv-miniputt-pipeline.md; .agents/skills/rvv/SKILL.md; .claude/commands/rvv-miniputt/scrape-llm.md; tests/test_rvv_skill_boundary.py; .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
