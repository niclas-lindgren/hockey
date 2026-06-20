# Plan: Add run.md to .chatgpt/commands/rvv-miniputt/

**Feature:** Add run.md to .chatgpt/commands/rvv-miniputt/ — ChatGPT harness has guide/logs/calendars but is missing the main pipeline run command
**Goal:** Add run.md to .chatgpt/commands/rvv-miniputt/ — ChatGPT harness has guide/logs/calendars but is missing the main pipeline run command
**Backlog-ref:** 160
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Bring the ChatGPT harness run command to parity with the Claude harness by adding the missing Stage 2 recovery sections so ChatGPT can guide recovery from blocked or empty calendar sources during pipeline runs.

---

## Tasks

- [x] Added recovery check section (blocked and empty sources) to .chatgpt/commands/rvv-miniputt/run.md after the Stage 2 block, mirroring the equivalent section in the .claude run.md. — 2026-06-20
  - Files: `.chatgpt/commands/rvv-miniputt/run.md`
  - Approach: Insert a subsection immediately after the Stage 2 block describing how to identify blocked or empty sources using `python3 -m tournament_scheduler.cli.rvv_cli recovery-targets`, mirroring the equivalent section in `.claude/commands/rvv-miniputt/run.md`.

- [x] The recovery loop section with WebFetch and recovery-inject steps was already included in the previous task's insertion — no additional changes needed. — 2026-06-20
  - Files: `.chatgpt/commands/rvv-miniputt/run.md`
  - Approach: Add the recovery loop section after the recovery check, documenting the WebFetch-then-inject pattern: use WebFetch (or browser tool) to retrieve each problem source URL, extract calendar events, and inject them via `echo '<JSON-array>' | python3 -m tournament_scheduler.cli.rvv_cli recovery-inject --source "SOURCE_NAME"`, matching the Claude version structure.

- [x] The proceed/abort decision section was already included in the first task's insertion — no additional changes needed. — 2026-06-20
  - Files: `.chatgpt/commands/rvv-miniputt/run.md`
  - Approach: Add the proceed/abort decision section immediately after the recovery loop, explaining when to continue to Stage 3 versus abort the run, using the same logic and wording as `.claude/commands/rvv-miniputt/run.md`.

---

## Log
- 2026-06-20 Plan created

## Acceptance Criteria

The .chatgpt/commands/rvv-miniputt/run.md file contains a "Recovery check" section after Stage 2 that lists how to identify blocked and empty sources.
The .chatgpt/commands/rvv-miniputt/run.md file contains a recovery loop section that has the recovery-inject command pattern matching the one in .claude/commands/rvv-miniputt/run.md.
The .chatgpt/commands/rvv-miniputt/run.md file has a proceed/abort decision section that describes when to continue to Stage 3 versus abort.
Searching .chatgpt/commands/rvv-miniputt/run.md for "recovery-targets" and "recovery-inject" returns at least one match for each command.
The .chatgpt/commands/rvv-miniputt/run.md file is not missing any of the three recovery sections that are present in .claude/commands/rvv-miniputt/run.md.

### 2026-06-20 — Added recovery check section (blocked and empty sources) to .chatgpt/commands/rvv-miniputt/run.md after the Stage 2 block, mirroring the equivalent section in the .claude run.md.
**Rationale:** Straight port of existing section — no alternatives needed.
**Findings:** Section inserted successfully; .chatgpt run.md now has full recovery guidance matching the .claude version.
LESSONS: none
**Files:** .chatgpt/commands/rvv-miniputt/run.md (+46/-0)
**Commit:** 5b0624c (hockey)

### 2026-06-20 — The recovery loop section with WebFetch and recovery-inject steps was already included in the previous task's insertion — no additional changes needed.
**Rationale:** Content was inserted together with the recovery check section in the prior task commit.
**Findings:** Verified the .chatgpt run.md already contains the full recovery loop content at lines 51-82.
LESSONS: The recovery loop section was inserted as part of the recovery check insertion; both tasks map to the same block of content from the .claude run.md.
**Files:** .chatgpt/commands/rvv-miniputt/run.md (no new changes — already present)
**Commit:** 44449f7 (hockey)

### 2026-06-20 — The proceed/abort decision section was already included in the first task's insertion — no additional changes needed.
**Rationale:** Content was inserted as part of the recovery check block in the first task commit (5b0624c).
**Findings:** Verified the .chatgpt run.md already contains the full proceed/abort decision content at lines 70-82.
LESSONS: All three recovery subsections from the .claude run.md were inserted together in a single block during the first task; the plan treated them as separate tasks but they map to the same inserted text.
**Files:** .chatgpt/commands/rvv-miniputt/run.md (no new changes — already present)
**Commit:** [pending — fill after commit]
