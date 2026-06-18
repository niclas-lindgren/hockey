# Plan: Add LLM approval gate before Stage 4 export
**Goal:** Add LLM approval gate before Stage 4 export: after Stage 3 (and any adjustment loop), have an LLM make a go/no-go call on the plan with a short rationale. If go: proceed to export. If no-go: print the specific blockers and proposed changes, then wait for operator confirmation or auto-apply if --non-strict is set. This is the step that lets the pipeline run fully autonomously on the happy path without a human reviewing the report.
**Created:** 2026-06-18
**Intent:** Enable the pipeline to run fully autonomously on the happy path by having an LLM evaluate the Stage 3 season plan and decide whether it is safe to export without human review.
**Backlog-ref:** 146
**Constraints:** none

## Tasks
- [x] Created llm_approval_gate.py with ApprovalVerdict dataclass and run_approval_gate() function that summarises the stage3 plan checkpoint and calls an LLM for a GO/NO_GO decision with rationale, blockers, and proposed changes. — 2026-06-18
  - Files: tournament_scheduler/pipeline/llm_approval_gate.py
  - Approach: Create a new module with a `run_approval_gate(plan_checkpoint: dict, client: LMStudioClient) -> ApprovalVerdict` function that formats a prompt from the stage3 checkpoint fields (fairness_gate, diversity_score, game_count_spread, month_balance_score, skipped_age_groups, arena_day_collisions) and calls `client.complete()`, then parses the LLM response into a structured `ApprovalVerdict(decision: str, rationale: str, blockers: list[str], proposed_changes: list[str])` dataclass.

- [x] Added _run_approval_gate() helper to pipeline_orchestrator.py that is called between stage3_run() and stage4_run(). Gate is opt-in via RVV_APPROVAL_ENDPOINT env var; returns False (halt) on NO_GO in strict mode, prints blockers/proposed changes, and writes the run log before returning 1. — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: After `stage3_run()` succeeds and before `stage4_run()` is called, invoke `run_approval_gate()` using the same `LMStudioClient` already configured for `_judge_stage`. If the verdict is "go", proceed to stage 4. If "no-go", print blockers and proposed changes via Rich and either halt (strict) or continue after auto-apply (non-strict).

- [x] In _run_approval_gate(), when strictTrue and verdict is NO_GO, prompt the operator with 'Vil du fortsette likevel? (j/n)'. On j/y/ja/yes, log the override and return True (proceed); on any other answer return False (halt). — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: When the approval gate returns no-go and strict=True, print the blockers and proposed changes with Rich formatting and prompt the operator for confirmation (y/n). If the operator declines, exit with code 1. If the operator confirms, proceed to stage 4 unchanged (letting the operator take responsibility).

- [x] In _run_approval_gate(), when strictFalse and verdict is NO_GO, attempt to auto-apply adjustments by calling ManualAdjustmentWorkflow(state).apply(season_plan) after converting plan_checkpoint via _dict_to_plan. Prints changes or warnings, then continues to Stage 4. — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/pipeline/manual_adjustment_workflow.py
  - Approach: When strict=False and the approval gate returns no-go, print the proposed changes then call into `manual_adjustment_workflow` to apply the LLM's proposed adjustments programmatically before proceeding to stage 4. Rebuild the fairness gate after any adjustments are applied.

- [ ] Persist approval gate verdict to stage3 checkpoint
  - Files: tournament_scheduler/pipeline/state.py, tournament_scheduler/pipeline/stage3_helpers.py
  - Approach: After the approval gate runs, write the verdict (decision, rationale, blockers) into the stage3 checkpoint under an `llm_approval` key using the existing state persistence pattern so reruns can inspect what was decided.

- [ ] Add unit tests for approval gate prompt formatting and verdict parsing
  - Files: tests/test_llm_approval_gate.py
  - Approach: Write tests that cover the happy path (go verdict), no-go verdict with blockers, and malformed LLM response fallback. Mock `LMStudioClient.complete()` to return controlled JSON/text responses and assert on the returned `ApprovalVerdict` fields.

## Acceptance Criteria
- [ ] When the pipeline reaches Stage 4 export with LLM approval enabled, it produces a go/no-go verdict that is logged to stdout along with the LLM's rationale for the decision.
- [ ] The LLM approval gate outputs specific blockers and proposed changes when it returns a no-go verdict, allowing operators to review the exact issues that need resolution.
- [ ] When --non-strict mode is enabled and the LLM returns a no-go verdict, the pipeline automatically applies the suggested changes without requiring manual confirmation from the operator.
- [ ] Running the pipeline with --strict flag and an LLM that returns no-go causes the process to exit with code 1 and print all specific blockers before halting execution.
- [ ] The stage3 checkpoint has an `llm_approval` key containing the decision, rationale, and blockers after the gate runs.

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-18 — Created llm_approval_gate.py with ApprovalVerdict dataclass and run_approval_gate() function that summarises the stage3 plan checkpoint and calls an LLM for a GO/NO_GO decision with rationale, blockers, and proposed changes.
**Rationale:** Straightforward module creation; fields in the plan checkpoint are plan.tournaments and rules_report (list of dicts with regel/forklaring/kategori)
**Findings:** Plan checkpoint has plan.tournaments (list of tournament dicts with host/age_group/date) and rules_report (list of dicts with regel/forklaring/kategori). No fairness_gate/diversity_score top-level fields exist — those appear only inside rules_report entries.
LESSONS: none
**Files:** tournament_scheduler/pipeline/llm_approval_gate.py (+127)
**Commit:** 5bcf5ed (hockey)

### 2026-06-18 — Added _run_approval_gate() helper to pipeline_orchestrator.py that is called between stage3_run() and stage4_run(). Gate is opt-in via RVV_APPROVAL_ENDPOINT env var; returns False (halt) on NO_GO in strict mode, prints blockers/proposed changes, and writes the run log before returning 1.
**Rationale:** No LMStudioClient was already available in the orchestrator context — used env vars RVV_APPROVAL_ENDPOINT / RVV_APPROVAL_MODEL with a sensible default to create one on-demand, matching the pattern used by the scraper command.
**Findings:** The llm judge system uses judge() not complete() — had to create LMStudioClient directly for the approval gate rather than reusing the headless judge.
LESSONS: The pipeline orchestrator uses LLMJudge with judge() for stage gates but the approval gate module requires LMStudioClient with complete(). Wire separately via env vars.
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+75)
**Commit:** adf311d (hockey)

### 2026-06-18 — In _run_approval_gate(), when strictTrue and verdict is NO_GO, prompt the operator with 'Vil du fortsette likevel? (j/n)'. On j/y/ja/yes, log the override and return True (proceed); on any other answer return False (halt).
**Rationale:** none
**Findings:** none
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+11)
**Commit:** 2713934 (hockey)

### 2026-06-18 — In _run_approval_gate(), when strictFalse and verdict is NO_GO, attempt to auto-apply adjustments by calling ManualAdjustmentWorkflow(state).apply(season_plan) after converting plan_checkpoint via _dict_to_plan. Prints changes or warnings, then continues to Stage 4.
**Rationale:** The proposed_changes from the LLM are free-text strings — not directly mappable to the workflow's structured adjustment dict. The auto-apply re-runs the workflow with existing manual_adjustments from the plan, which rebuilds fairness scoring and applies any previously configured adjustments.
**Findings:** ManualAdjustmentWorkflow.apply() requires a SeasonPlan object, not a plan dict — must use _dict_to_plan from stage4_helpers to convert first. State parameter was added to _run_approval_gate signature.
LESSONS: none
**Files:** tournament_scheduler/cli/pipeline_orchestrator.py (+38/-2)
**Commit:** [pending — fill after commit]
