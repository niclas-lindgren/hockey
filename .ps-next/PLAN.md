# Plan: Feed fairness gate scores from failed planning attempts as penalty hints into retries
**Goal:** The 3-attempt Stage 3 retry loop in `_cmd_run` no longer just blindly increases `--iterations` — it reads fairness gate scores from each failed attempt and passes targeted penalty hints (relaxed thresholds) into the next attempt, so the planner can explore solutions that pass the gate rather than searching independently each time.
**Created:** 2026-06-24
**Intent:** The outer retry loop currently has no memory — each attempt starts fresh with only a larger search budget. Failed fairness metrics (e.g. `hosting_deviation` at score 44) are discarded. This change feeds those scores back as config adjustments so the planner can fix what went wrong.
**Backlog-ref:** 8

## Tasks
- [x] Add penalty-hints plumbing from `_cmd_run` retry loop through `_run_stage3` and `stage3_planning.run()` into `SeasonPlanner`
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/season_planner.py
  - Approach:
    1. In `_cmd_run` retry loop: after each attempt where tone is "rough", extract fairness gate metrics from the plan checkpoint dict. Build `penalty_hints` by collecting any metric with `score < 100` and `status != "pass"`, storing `{metric_key: score}` pairs.
    2. Pass `penalty_hints` into `_run_stage3()` as a new parameter.
    3. In `_run_stage3()`, merge `penalty_hints` into the `cfg` dict under a new `"penalty_hints"` key before calling `stage3_run()`.
    4. In `stage3_planning.run()`, extract `penalty_hints` from config and pass to `_make_planner()`.
    5. In `SeasonPlanner.__init__()`, accept `penalty_hints: Optional[Dict[str, float]] = None` and store as `self.penalty_hints`.
    6. Log applied hints via `_console.print` and `_log` in Norwegian so operators see which metrics triggered adjustments.

- [x] Relax failing fairness thresholds based on penalty hints in the next attempt
  - Files: tournament_scheduler/season_planner.py
  - Approach:
    1. In `SeasonPlanner.__init__()`, after setting `self.fairness_thresholds`, iterate over `penalty_hints`.
    2. For `hosting_deviation_score`: if score < 100, relax `max_hosting_deviation` to `max(2.0, original * 1.5)` so the planner has more room.
    3. For `game_count_spread_score`: if score < 100, relax `max_game_count_spread` to `max(4, original * 1.5)`.
    4. For `month_balance_score` or `diversity_score` or `pairwise_matchup_score`: if score < 75 (below min), relax `min_*_score` by multiplying by 0.7 (lower threshold = easier to pass).
    5. Log each relaxation via `print(f"[penalty_hints] {key}: {old} → {new}")` so the operator/run log can trace it.
    6. The original thresholds in the config are NOT mutated — only the running instance's thresholds change, so re-running without penalty_hints uses original thresholds.

- [x] Track the best plan by composite fairness score across retries in `_cmd_run`
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach:
    1. Before the retry loop, initialize `best_plan: dict[str, Any] | None = None` and `best_score: int = -1`.
    2. After each attempt, extract the fairness gate score from the plan checkpoint (`plan.get("plan", {}).get("fairness_gate", {}).get("score", 0)`).
    3. If `score > best_score`, store `(best_plan, best_score) = (plan, score)` and log which attempt won.
    4. After the loop, use `best_plan` instead of `plan` for the continuation (Stage 4, refinement loop).
    5. Log a message like `"Valgte forsøk N (score=M) over forsøk K (score=L)"` so the operator sees which attempt had the best quality.

## Notes
- This is only about the *outer* retry loop in `_cmd_run` (3 attempts with increasing iterations). The *inner* multi-seed loop in `stage3_planning.run()` already keeps the best plan across seeds — that's untouched.
- Penalty hints should never make the threshold easier than double the original (cap relaxation).
- Hints are ephemeral — written only to the running instance, never persisted to input.xlsx or the Stage 1 checkpoint.
- Test by running the pipeline with intentionally tight thresholds and verifying each retry relaxes appropriately.

## Acceptance Criteria
- [ ] `penalty_hints` dict flows from `_cmd_run` → `_run_stage3` → `stage3_planning.run()` → `SeasonPlanner.__init__()` without breaking existing callers.
- [ ] Failed fairness metrics trigger relaxed thresholds in the next attempt (verified by log output).
- [ ] Best plan across all retries is kept, not just the last attempt.
- [ ] Existing tests pass without changes.
- [ ] Log output in Norwegian shows which metrics triggered hints and what was relaxed.

## Log



### 2026-06-25 — Track the best plan by composite fairness score across retries in `_cmd_run`
**Done:** _cmd_run tracks best_plan/best_score/best_attempt across retries and selects the best one
**Rationale:** best_plan/best_score/best_attempt initialized before retry loop. After each attempt, fairness gate score is extracted and compared. After loop, best plan is used if earlier attempt scored higher. Norwegian logging: 'Velger forsøk N (fairness-score M) — best av N'.
**Findings:** Best-plan tracking works correctly: stores only when score > best_score, logs which attempt won, recomputes tone from the selected best plan. Pre-existing test failures in test_season_planner and test_stage3_planning unrelated.
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py
**Commit:** not committed
### 2026-06-25 — Relax failing fairness thresholds based on penalty hints in the next attempt
**Done:** SeasonPlanner.__init__() relaxes thresholds based on penalty hints
**Rationale:** After storing self.penalty_hints, the code iterates over hint keys and relaxes max_hosting_deviation (1.5x, min 2), max_game_count_spread (1.5x, min 4), min_diversity_score, min_pairwise_matchup_score, and min_month_balance_score (0.7x, min 0.3). Original config thresholds are not mutated, and relaxation is capped at 2x.
**Findings:** All 5 metric types handled with appropriate relaxation logic. Logging via print('[penalty_hints] ...') in Norwegian. Original thresholds preserved in config dict.
**Files:** tournament_scheduler/season_planner.py
**Commit:** not committed
### 2026-06-25 — Add penalty-hints plumbing from `_cmd_run` retry loop through `_run_stage3` and `stage3_planning.run()` into `SeasonPlanner`
**Done:** penalty_hints flows from _cmd_run → _run_stage3 → stage3_planning.run() → _make_planner() → SeasonPlanner.__init__()
**Rationale:** The retry loop in _cmd_run builds penalty_hints from failed fairness gate metrics; _run_stage3 merges them into cfg; stage3_planning.run() extracts and passes to _make_planner(); SeasonPlanner stores as self.penalty_hints and logs via _console.print/print in Norwegian.
**Findings:** All plumbing paths verified: _cmd_run builds hints → _run_stage3 merges into cfg → stage3_planning.run() extracts from config → _make_planner() passes to SeasonPlanner.__init__(). Norwegian logging present at each hop.
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/pipeline/stage3_helpers.py, tournament_scheduler/season_planner.py
**Commit:** not committed
