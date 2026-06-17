---
name: pi-next
description: Thin project-local proxy for PS:next workflow on projects that use .ps-next task lists. Reads .ps-next/PROJECT.md, BACKLOG.md, PLAN.md, and HISTORY.md; selects the next backlog item or a requested item; writes an implementation plan; executes tasks one-by-one; verifies acceptance criteria; archives completed plans and marks backlog items done. Use with /skill:pi-next, /skill:pi-next auto, /skill:pi-next <backlog-id>, /skill:pi-next plan <feature>, or /skill:pi-next backlog list/add/done.
---

# pi-next — autonomous .ps-next task runner for Pi

You are running inside Pi, not Claude Code. This skill is a thin project-local proxy over the shared PS:next workflow: it keeps the project-specific `.ps-next` state, backlog, and lock helpers here, while the canonical planning/routing/verification/archive behavior lives in the shared PS:next skill and shell scripts.

## Core rule

Act autonomously unless the task is unsafe, ambiguous enough to risk destructive work, legally requires human review, or credentials/production access are needed. Prefer completing one coherent plan end-to-end: select → plan → implement → verify → archive.

## Claude PS:next compatibility / handoff

This skill is intentionally compatible with the Claude `PS:next` skill at the file-protocol level. Both agents may continue the same work as long as they share the same `.ps-next` directory and obey these rules:

- Never run Claude and Pi on the same plan at the same time.
- Treat `.ps-next/PLAN.md` as the source of truth. Checked boxes are completed work; the first unchecked task is next.
- Preserve the canonical PLAN.md sections and task sub-bullets exactly enough for Claude's `ps-next-state` and `PS-auto-worker`: `## Tasks`, `- [ ] ...`, `Files:`, `Approach:`, `## Acceptance Criteria`, `## Log`.
- Commit after each completed task when possible, including both implementation files and `.ps-next/PLAN.md`. This makes handoff robust.
- If `.ps-next/.continue-here.md` exists, read it before resuming. It is a warning/checkpoint from Claude; do not delete it unless the blocker has actually been resolved.
- If Pi archives a plan, Claude will see no active PLAN.md and can pick the next backlog item. If Claude archives a plan, Pi will do the same.

Recommended handoff: stop one agent after it has checked off a task and committed, then start the other with `/skill:pi-next` or `/PS:next`. Mid-task handoff is possible only if the current diff and PLAN.md log make the state obvious.

Do not rely on Claude-only tools, subagents, or `~/.claude/bin/*`. Use the project Pi extension when available (`.pi/extensions/pi-next.ts`) and the helper scripts in this skill directory when useful:

```bash
.agents/skills/pi-next/scripts/pi-next-state.sh . "optional args"
.agents/skills/pi-next/scripts/pi-next-archive.sh "$PS_DIR" "optional-backlog-id"
```

The helper scripts are the harness-neutral way to access project-local PS:next state from Codex, Claude, OpenCode, or a normal shell; the Pi extension tools below are adapters on top of that same file protocol.

When the extension is loaded, prefer its tools for state/backlog/task/archive operations:

- `pi_next_state` — structured `.ps-next` state
- `pi_next_current_task` — first unchecked PLAN.md task with Files/Approach/Lessons
- `pi_next_mark_task_done` — safely check off a task and append a Log entry
- `pi_next_plan_validate` — validate Claude/Pi-compatible PLAN.md structure
- `pi_next_lock` — acquire/release/status `.ps-next/.lock` to prevent concurrent agents
- `pi_next_handoff_status` — determine whether it is safe to switch between Claude and Pi
- `pi_next_quality_gate` — run project typecheck/lint/test/build gates
- `pi_next_safety_scan` — scan diffs for secrets and sensitive file changes
- `pi_next_diff_review` — deterministic pre-commit review for common autonomous-work issues
- `pi_next_plan_drift` — compare changed files with the current task's Files list
- `pi_next_verify_plan` — run embedded `run:`/`grep:` acceptance checks and write VERIFY.md
- `pi_next_git_checkpoint` — inspect dirty/conflict state or create checkpoint commits
- `pi_next_append_fix_task` — append structured remediation tasks after verification failures
- `pi_next_continue_marker` — read/write/clear `.continue-here.md` recovery checkpoints
- `pi_next_backlog` — list/get/add/done backlog items
- `pi_next_archive` — archive completed PLAN.md

If this skill is installed outside the project, resolve helper paths relative to this SKILL.md's directory.

## Boundary / cleanup target

The portable, harness-neutral contract is the `.ps-next` file layout plus the helper scripts in `.agents/skills/pi-next/scripts/`. Pi-only additions should stay in the extension/tooling layer, not in the shared workflow protocol.

- Keep local logic limited to project state access, backlog manipulation, locking, and handoff safety.
- Prefer syncing or delegating to the shared PS:next workflow for plan routing, task execution, verification, and archive semantics.
- Do not duplicate the shared PS:next protocol or reimplement its lifecycle locally unless the shared contract cannot cover the project.

## Arguments

Parse the user's arguments first.

- `auto [feature]` — run full lifecycle. If no feature is supplied, use the top open backlog item.
- bare integer, e.g. `210` — use that backlog item.
- `plan [feature]` — create `.ps-next/PLAN.md` only, then stop.
- `backlog list` — show open backlog items.
- `backlog add <text>` — append a new open backlog item with the next numeric id.
- `backlog done <id>` — mark an item done.
- `/pi-next-fresh [args]` — extension command that starts a clean Pi session and runs this skill there.
- `/pi-next-loop N` — extension command that starts a clean session and asks pi-next to process up to N backlog items, stopping on blockers.
- freeform text — treat as a feature/fix request and run full lifecycle.
- no args — if a plan exists, resume it; otherwise auto-select the top open backlog item.

## State detection

Run:

```bash
.agents/skills/pi-next/scripts/pi-next-state.sh . "$ARGS"
```

Parse `PS_DIR`, `PLAN`, `UNCHECKED`, `OPEN_BACKLOG`, `BACKLOG_TOP_ID`, `BACKLOG_TOP_TEXT`, and `PLAN_GOAL`.

If `$PS_DIR/.continue-here.md` exists, read it and surface the checkpoint before routing. Continue only if the next safe action is clear.

Routing:

1. `PLAN=exists` and `UNCHECKED > 0` → execute remaining tasks.
2. `PLAN=exists` and `UNCHECKED = 0` → verify and archive.
3. no plan + explicit feature/freeform/`auto feature` → create plan, then execute unless mode is `plan`.
4. no plan + integer arg → fetch that backlog item, create plan, then execute.
5. no plan + no args + open backlog → auto-select top open backlog item, create plan, then execute.
6. no plan + no backlog → ask the user for the feature.

## Backlog item handling

Open items use this format:

```markdown
- [210] [ ] Text of task
```

For a numeric item, fetch it with:

```bash
grep -E '^- \[210\] \[ \] ' "$PS_DIR/BACKLOG.md"
```

Before planning a backlog item, skim the last 10 lines of `$PS_DIR/HISTORY.md` and avoid duplicating already completed work. If the item explicitly says `depends on [N]`, `requires [N]`, or `blocked by [N]`, and item N is still open, select item N first.

## PLAN.md format

Write `$PS_DIR/PLAN.md` in this exact structure:

```markdown
# Plan: Short title
**Goal:** One-sentence done condition
**Created:** YYYY-MM-DD
**Intent:** Why this work matters
**Backlog-ref:** N

## Tasks
- [ ] Concrete task name
  - Files: path/to/file.ts, another/path.tsx
  - Approach: Specific implementation approach with commands/patterns to follow.

## Notes
Constraints, codebase findings, prior history, and things to avoid.

## Acceptance Criteria
- [ ] Observable criterion containing a verb such as pass, contain, show, return, update, create, remove, or run.

## Log
<!-- pi-next appends entries here after each task -->
```

Omit `**Backlog-ref:**` when the plan is not from backlog.

Planning requirements:
- Read `.ps-next/PROJECT.md` and relevant project instruction files before planning.
- Use graph tools first if available in the harness/project instructions; otherwise use `bash` search and `read`.
- Search the codebase for existing patterns before inventing new ones.
- Create 2-6 independently committable tasks; small fixes may have 1-2 tasks.
- Each task must list real expected files and a concrete approach.
- Acceptance criteria must be testable by code inspection, tests, or commands.

## Execute remaining tasks

Loop over unchecked tasks in `$PS_DIR/PLAN.md` until none remain or blocked. If available, acquire a lock first: `pi_next_lock(action="acquire", owner="pi", task="...")`; release it when done or blocked.

For each task:

1. Extract the first unchecked task and its `Files:`/`Approach:` bullets from PLAN.md. Prefer `pi_next_current_task` when available.
2. Read the listed files that exist. Search for related patterns. Follow all `AGENTS.md`, `CLAUDE.md`, package, and local conventions.
3. Implement only that task.
4. Run the narrowest meaningful checks first, then broader checks when appropriate. Prefer `pi_next_quality_gate(level="quick"|"standard")` when available. For this project, relevant commands include:
   - `npm run typecheck`
   - `npm run lint`
   - `npm run test`
   - `npm run build`
   - targeted `npx vitest ...` or Playwright specs when relevant
5. Before marking done, run `pi_next_safety_scan`, `pi_next_diff_review`, and `pi_next_plan_drift` when available. Treat safety failures as blockers; treat drift/review warnings as issues to fix or explicitly explain in the task log.
6. If checks fail, fix them. Stop only after two serious failed attempts or when blocked by missing credentials/services.
7. Update PLAN.md: prefer `pi_next_mark_task_done`. If unavailable, change that task checkbox to `[x]` and append a log entry under `## Log`:

```markdown
### YYYY-MM-DD — Task name
**Done:** What changed.
**Rationale:** Why this approach.
**Findings:** Important discoveries or `none`.
**Files:** Compact list/stat of changed files.
**Commit:** short hash or `not committed`.
```

7. Commit if the repo is in a committable state and the user has not asked you not to. Use a concise message. Include implementation files and PLAN.md in the commit. If commit hooks fail, fix or stop with a clear blocker.

## Verification

When no unchecked tasks remain:

Before verification, run `pi_next_plan_validate` if available and fix structural errors before proceeding.

1. Read `## Acceptance Criteria` from PLAN.md.
2. Prefer `pi_next_verify_plan` to run embedded `run:`/`grep:` checks and write `$PS_DIR/VERIFY.md`; then run `pi_next_quality_gate(level="full")` before archive when feasible.
3. Run `pi_next_safety_scan` and `pi_next_diff_review` if there are uncommitted changes.
4. For each criterion, mark PASS/FAIL/MANUAL in `$PS_DIR/VERIFY.md` with evidence.
5. If any criterion fails, prefer `pi_next_append_fix_task` to add new unchecked `[Fix] ...` tasks to PLAN.md and execute them. Bound this verify-fix loop to 3 attempts.
6. If all criteria pass or only require manual review, archive.

## Archiving

Find backlog ref from PLAN.md if present:

```bash
BACKLOG_REF=$(grep -m1 '^\*\*Backlog-ref:\*\*' "$PS_DIR/PLAN.md" | sed 's/^\*\*Backlog-ref:\*\* *//' || true)
.agents/skills/pi-next/scripts/pi-next-archive.sh "$PS_DIR" "$BACKLOG_REF"
```

The archive helper moves PLAN.md to `$PS_DIR/ARCHIVED/`, appends a HISTORY.md line, and marks the backlog item done.

## Backlog subcommands

- `backlog list`: print all lines matching `^- \[[0-9]+\] \[ \]` from BACKLOG.md.
- `backlog add <text>`: compute max existing id + 1 and append `- [id] [ ] <text>` under `## Open` (or the first appropriate tier if present).
- `backlog done <id>`: replace `- [id] [ ]` with `- [id] [x]` and append today's date.

## Stop conditions

Stop and report clearly when:
- There is no safe way to infer the intended behavior.
- A required secret, external account, or production system is unavailable.
- Tests fail after bounded repair attempts.
- The task asks for legal/business final approval; implement drafts or scaffolding, but mark final review as MANUAL.

Final response should be short: selected item/plan, what changed, checks run, archive status, and any blockers.
