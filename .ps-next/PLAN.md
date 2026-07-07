# Plan: Composite best Stage 3 retry selection
**Goal:** The RVV pipeline keeps and exports the best Stage 3 retry attempt by composite plan quality, not just the last or highest fairness-gate-only attempt.
**Created:** 2026-07-07
**Intent:** Avoid losing a stronger season plan generated earlier in the retry loop when later attempts improve only one score or regress overall quality.
**Backlog-ref:** 9

## Tasks
- [x] Add composite attempt scoring to the Stage 3 retry loop
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Extract a small helper that reads fairness_gate score/status plus pairwise_matchup_score, diversity_score, and month_balance_score from the Stage 3 plan payload; rank attempts lexicographically by gate status/score and metric sum; select the best attempt after retries and log/print which attempt won with score components and comparison reason.
- [ ] Cover composite best-attempt behavior with targeted tests
  - Files: tests/test_pipeline_orchestrator_judgment.py, tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: Add mocked _cmd_run coverage where attempt 1 has a better composite score than later attempts despite lower/competing individual metrics; assert Stage 4 receives the selected plan and run logs mention the selected attempt/reason. Add a helper-level test if needed for score extraction/ranking.

## Notes
- Existing retry code already tracks `best_plan` but only by `fairness_gate.score`, which is insufficient for backlog #9.
- The scheduling rules themselves are unchanged; rules report docs likely do not need updates unless scoring semantics are surfaced there.
- Follow RVV instruction: do not invoke `/rvv-miniputt ...` through Bash.

## Acceptance Criteria
- [ ] `tournament_scheduler/cli/pipeline_orchestrator.py` computes best attempt from fairness gate score/status, pairwise_matchup_score, diversity_score, and month_balance_score.
- [ ] Pipeline run logs include which Stage 3 attempt won and why.
- [ ] Targeted tests pass for selecting an earlier/later best composite attempt.
- [ ] run: pytest tests/test_pipeline_orchestrator_judgment.py tests/test_pipeline_orchestrator.py

## Log

### 2026-07-07 — Add composite attempt scoring to the Stage 3 retry loop
**Done:** Added composite Stage 3 attempt quality extraction/ranking that normalizes fairness gate score, pairwise matchup score, diversity score, and month balance score; the retry loop now logs all compared attempts, selects the best, and persists it back to the planning checkpoint when it is not the last attempt.
**Rationale:** A fairness-gate-only comparison could discard an earlier plan with materially better overall quality; selecting by composite components preserves the strongest generated attempt for approval/export/refinement.
**Findings:** Existing code already tracked best_plan but only with fairness_gate.score and did not keep the Stage 3 checkpoint aligned when an earlier attempt won.
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+composite helpers/retry-loop selection), .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
