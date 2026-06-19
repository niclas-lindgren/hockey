# Plan: Harness-driven automated adjustment loop between Stage 3 and Stage 4
**Goal:** Harness-driven automated adjustment loop between Stage 3 and Stage 4: when the harness plan critic finds fixable issues, the harness should propose specific moves (tournament, from-date, to-date, reason) and apply them via the existing replan CLI entrypoint, then re-run Stage 3 and re-evaluate. Iterate up to N times (configurable). Escalate to the human operator only when issues remain after N iterations or when a move requires knowledge the harness cannot infer (e.g. explicit club preference).
**Created:** 2026-06-19
**Intent:** Reduce manual intervention in the season-planning cycle by having the harness automatically resolve common fixable issues flagged by the plan critic before handing off to Stage 4.
**Backlog-ref:** 142
**Constraints:** none

## Tasks
- [x] Added suggest_moves(plan, issues) to plan_critic.py mapping each critic issue string to a replan proposal dict with tournament_id, new_date, reason, can_auto_fix, and issue keys. — 2026-06-19
  - Files: tournament_scheduler/cli/plan_critic.py
  - Approach: Add a `suggest_moves(plan: SeasonPlan, issues: List[str]) -> List[dict]` function that maps each critic issue string to a concrete replan proposal dict with keys `tournament_id`, `new_date`, `reason`, `can_auto_fix` (bool). Arena-day collisions and hosting clumps are auto-fixable (shift tournament by one week); fairness-gate FAILs requiring club-preference knowledge set `can_auto_fix=False`.

- [x] Added auto-adjust subcommand to args.py and _cmd_auto_adjust handler to rvv_cli.py; the handler loads Stage 3 checkpoint, runs plan critic, translates auto-fixable moves via suggest_moves, applies each via _cmd_replan, and loops until clean or max-iterations reached. — 2026-06-19
  - Files: tournament_scheduler/cli/rvv_cli.py, tournament_scheduler/cli/args.py
  - Approach: Add a new `auto-adjust` CLI subcommand to `args.py` (with `--max-iterations` int defaulting to 3, `--work-dir`, `--export-dir`, `--timestamped-export`) and a `_cmd_auto_adjust(args)` handler in `rvv_cli.py` that loads the Stage 3 checkpoint, calls `generate_critic_summary`, translates issues to moves via `suggest_moves`, and applies each auto-fixable move by invoking `_cmd_replan` internally with the proposed arguments, then re-evaluates.

- [x] Refactored _cmd_auto_adjust to apply one move per iteration then reload the checkpoint and re-run generate_critic_summary before the next iteration; count_critic_issues_from_dict serves as the fast early-exit gate; extracted _load_critic_state helper to avoid code duplication. — 2026-06-19
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Inside `_cmd_auto_adjust`, loop up to `max_iterations` times: after each call to `_cmd_replan`, reload the checkpoint, re-run `generate_critic_summary`, and break early when `count_critic_issues_from_dict` returns 0. Track iteration count and pass it to the escalation step.

- [ ] Implement escalation path and Rich console feedback
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: When the loop ends with remaining issues (either max iterations reached or all remaining moves have `can_auto_fix=False`), print a Rich-formatted escalation table listing each unresolved issue, the reason the harness could not fix it, and the suggested next manual step. Use the existing Rich console pattern from `tournament_scheduler/utils/rich_output.py`.

- [ ] Add unit tests for the adjustment loop
  - Files: tests/test_auto_adjust.py, tests/test_plan_critic.py
  - Approach: Write pytest tests covering: (a) `suggest_moves` returns correct move dicts for each issue category, (b) the loop exits early when all issues are resolved before max iterations, (c) the loop escalates when `can_auto_fix=False` issues remain, and (d) the loop stops at `max_iterations` even when auto-fixable issues persist. Mock `_cmd_replan` and the Stage 3 checkpoint load to isolate harness logic.

## Acceptance Criteria
- [ ] Running `scripts/rvv-miniputt auto-adjust` produces updated plan output and reports the number of adjustment iterations applied.
- [ ] When all critic issues are auto-fixable and resolved within N iterations, the command exits with code 0 and the updated stage 3 checkpoint contains no critical issues as returned by count_critic_issues_from_dict.
- [ ] When issues remain after N iterations or a move has can_auto_fix=False, the CLI prints an escalation report listing each unresolved issue and does not silently pass.
- [ ] suggest_moves returns at least one move dict with can_auto_fix=True for arena-day collision and hosting-clump issue strings.
- [ ] `pytest tests/test_auto_adjust.py tests/test_plan_critic.py -q` passes.

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-19 — Added suggest_moves(plan, issues) to plan_critic.py mapping each critic issue string to a replan proposal dict with tournament_id, new_date, reason, can_auto_fix, and issue keys.
**Rationale:** Used regex matching on issue strings to dispatch to typed handlers; arena-day collisions and hosting clumps produce auto-fixable move proposals (+7d shift); fairness gate and other issues produce non-auto-fixable stubs.
**Findings:** suggest_moves resolved collisions and clumps to tournament IDs via arena/date and host/month lookups respectively; fairness/spread/balance issues flagged as manual-review.
LESSONS: none
**Files:** tournament_scheduler/cli/plan_critic.py (+208/-1)
**Commit:** fb1d5ad (hockey)

### 2026-06-19 — Added auto-adjust subcommand to args.py and _cmd_auto_adjust handler to rvv_cli.py; the handler loads Stage 3 checkpoint, runs plan critic, translates auto-fixable moves via suggest_moves, applies each via _cmd_replan, and loops until clean or max-iterations reached.
**Rationale:** Used a synthetic argparse.Namespace to call _cmd_replan internally without spawning a subprocess; forceTrue skips conflict prompts during automated fixes.
**Findings:** Deduplication of manual-review issues across iterations prevents duplicate output when the same non-fixable metric recurs.
LESSONS: none
**Files:** tournament_scheduler/cli/rvv_cli.py (+120), tournament_scheduler/cli/args.py (+31)
**Commit:** 36cd4fb (hockey)

### 2026-06-19 — Refactored _cmd_auto_adjust to apply one move per iteration then reload the checkpoint and re-run generate_critic_summary before the next iteration; count_critic_issues_from_dict serves as the fast early-exit gate; extracted _load_critic_state helper to avoid code duplication.
**Rationale:** Applies one auto-fixable move at a time (not all moves in a batch) so each iteration starts from a fresh plan state; this prevents stale collision/clump data from generating redundant moves.
**Findings:** The _plan_to_dict converter lives in pipeline.stage3_helpers, not on SeasonPlanner; import it from there for the dict-based issue count gate.
LESSONS: _plan_to_dict is in pipeline/stage3_helpers.py — import from there, not from season_planner
**Files:** tournament_scheduler/cli/rvv_cli.py (+91/-50)
**Commit:** [pending — fill after commit]
