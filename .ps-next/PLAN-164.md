# Plan: Add verdict CLI command

**Feature:** Add verdict CLI command: python3 -m tournament_scheduler.cli.rvv_cli verdict [--work-dir .pipeline] — reads stage3 checkpoint and prints the tone (strong/mixed/rough) and key scores to stdout, so rvv-miniputt:run skill can check the verdict without parsing HTML
**Goal:** Add verdict CLI command: python3 -m tournament_scheduler.cli.rvv_cli verdict [--work-dir .pipeline] — reads stage3 checkpoint and prints the tone (strong/mixed/rough) and key scores to stdout, so rvv-miniputt:run skill can check the verdict without parsing HTML
**Backlog-ref:** 164
**Constraints:** none
**Date:** 2026-06-20
**Intent:** Provide a machine-readable CLI output of the plan verdict so the rvv-miniputt:run skill can check schedule quality without parsing HTML.

---

## Tasks

- [x] Added verdict subparser to args.py using add_parser() with --work-dir defaulting to .pipeline, following the same pattern as critic and status subcommands. — 2026-06-20
  - Files: `tournament_scheduler/cli/args.py`
  - Approach: Register the new `verdict` subcommand in `args.py` using `sub.add_parser()` with `--work-dir` defaulting to `.pipeline`, following the established pattern used by `critic` and `status` subcommands.

- [ ] Implement _cmd_verdict handler in rvv_cli.py
  - Files: `tournament_scheduler/cli/rvv_cli.py`
  - Approach: Add `_cmd_verdict(args: argparse.Namespace) -> int` that reads stage3 via `PipelineState(args.work_dir).read_stage(StageName.PLANNING)`, extracts the plan, calls `compute_team_game_counts`, `compute_team_travel_info`, and `compute_club_stats` from `tournament_scheduler/html/html_exporter.py`, then passes them to `analyze_opinionated_judgment` from `tournament_scheduler/html/renderers/judgment.py`.

- [ ] Format and print verdict output to stdout using Rich console
  - Files: `tournament_scheduler/cli/rvv_cli.py`
  - Approach: Inside `_cmd_verdict`, use `_console.print()` to emit tone, tone_label, pairwise/diversity/month_balance scores, verdict string, and action_text in a structured, machine-parseable format (e.g. `tone: strong`, `pairwise_score: 0.85`) so the rvv-miniputt:run skill can consume it without HTML parsing.

- [ ] Wire verdict command into main() dispatcher
  - Files: `tournament_scheduler/cli/rvv_cli.py`
  - Approach: Add `elif args.command == "verdict": return _cmd_verdict(args)` to the `main()` dispatch block, following the pattern of all other subcommands in the same function.

- [ ] Write tests for verdict command
  - Files: `tests/test_verdict_cli.py`
  - Approach: Using pytest and a fixture that provides a minimal stage3 checkpoint dict, invoke `_cmd_verdict` and assert it returns exit code 0 and that the Rich console output contains the expected tone string (strong/mixed/rough) and at least one score field.

---

## Log

## Acceptance Criteria

When the rvv_cli verdict command is executed with a valid stage3 checkpoint, it outputs to stdout the tone (strong/mixed/rough) and key scores in a parseable format that can be consumed by the rvv-miniputt:run skill.
The rvv_cli verdict command reads the stage3 checkpoint from the specified work directory and produces structured output containing the tone classification and key performance metrics.
Running python3 -m tournament_scheduler.cli.rvv_cli verdict with a valid --work-dir outputs the verdict information to stdout without requiring HTML parsing.
The CLI command exits with code 0 when successfully reading the stage3 checkpoint and producing the verdict output to stdout.
The verdict command exits with code 1 and prints an error message when no stage3 checkpoint is found in the specified work directory.

### 2026-06-20 — Added verdict subparser to args.py using add_parser() with --work-dir defaulting to .pipeline, following the same pattern as critic and status subcommands.
**Rationale:** Straightforward — followed the existing pattern exactly.
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/args.py (+11/-0)
**Commit:** [pending — fill after commit]
