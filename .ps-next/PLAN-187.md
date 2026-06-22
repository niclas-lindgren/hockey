# Plan: Remove --no-timestamped-export flag from Stage 4 docs
**Goal:** Remove --no-timestamped-export flag from rvv-miniputt:run skill Stage 4 docs — it is not a recognized argument and causes stage4_export to fail
**Created:** 2026-06-22
**Intent:** Prevent stage4_export from failing due to an unrecognized CLI argument that was incorrectly documented in skill and command files.
**Backlog-ref:** 187

## Tasks
- [x] Removed the unrecognized --no-timestamped-export flag from the stage4_export command example in run.md. — 2026-06-22
  - Files: /Users/niclasl/src/hockey/.claude/commands/rvv-miniputt/run.md
  - Approach: Find all occurrences of `[--no-timestamped-export]` in the stage4_export command examples and remove the flag, leaving only `[--work-dir .pipeline] [--export-dir export]` as documented in stage4_export.py.
- [x] Removed the unrecognized --no-timestamped-export flag from the stage4_export command example in SKILL.md. — 2026-06-22
  - Files: /Users/niclasl/src/hockey/.agents/skills/rvv/SKILL.md
  - Approach: Locate the Stage 4 export command invocation line containing `--no-timestamped-export` and remove the flag, keeping the remaining valid arguments intact.
- [x] Removed --no-timestamped-export from stage4_export command in .chatgpt/commands/rvv-miniputt/run.md. — 2026-06-22
  - Files: /Users/niclasl/src/hockey/.chatgpt/commands/rvv-miniputt/run.md
  - Approach: Find the stage4_export command invocation at line ~98 and remove `[--no-timestamped-export]` from the command example.
- [ ] Remove --no-timestamped-export from OpenCode command doc
  - Files: /Users/niclasl/src/hockey/.opencode/commands/rvv-miniputt/run.md
  - Approach: Find all occurrences of `[--no-timestamped-export]` in Stage 4 export command examples (lines ~33 and ~60) and remove the flag from each.

## Notes
The `--no-timestamped-export` flag exists in `tournament_scheduler/cli/args.py` for other subcommands (adjust, run_export) but is NOT registered in `tournament_scheduler/pipeline/stage4_export.py`'s argparse definition. That module only accepts `--work-dir` and `--export-dir`. The fix is documentation-only — no source code changes required.

## Acceptance Criteria
- [ ] The --no-timestamped-export flag is not present in any Stage 4 export command examples in .claude/commands/rvv-miniputt/run.md, .agents/skills/rvv/SKILL.md, .chatgpt/commands/rvv-miniputt/run.md, or .opencode/commands/rvv-miniputt/run.md.
- [ ] Running `grep -r "no-timestamped-export" .claude/commands .agents/skills .chatgpt/commands .opencode/commands` from the repo root produces no output.
- [ ] The stage4_export command examples in all four files contain only the recognized arguments --work-dir and --export-dir.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-22 — Removed the unrecognized --no-timestamped-export flag from the stage4_export command example in run.md.
**Rationale:** Flag does not exist in stage4_export.py argparse; removing prevents confusing docs-vs-reality mismatch.
**Findings:** Flag removed from line 134 of run.md; command now matches actual stage4_export.py interface.
LESSONS: none
**Files:** .claude/commands/rvv-miniputt/run.md (+1/-1)
**Commit:** d684414 (hockey)

### 2026-06-22 — Removed the unrecognized --no-timestamped-export flag from the stage4_export command example in SKILL.md.
**Rationale:** Same fix as run.md — flag absent from argparse; removing prevents skill-caused failures.
**Findings:** Flag removed from line 336 of SKILL.md.
LESSONS: none
**Files:** .agents/skills/rvv/SKILL.md (+1/-1)
**Commit:** f146372 (hockey)

### 2026-06-22 — Removed --no-timestamped-export from stage4_export command in .chatgpt/commands/rvv-miniputt/run.md.
**Rationale:** Same fix as Claude run.md and SKILL.md — ensures all command docs match the actual stage4_export.py interface.
**Findings:** Flag removed from line 98 of .chatgpt/commands/rvv-miniputt/run.md.
LESSONS: none
**Files:** .chatgpt/commands/rvv-miniputt/run.md (+1/-1)
**Commit:** [pending — fill after commit]
