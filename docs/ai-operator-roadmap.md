# AI operator implementation roadmap

This backlog translates the product direction in `ai-operator-product-direction.md` into ordered implementation slices. Each section is intentionally written so it can later become a GitHub issue.

## 1. Define the operator run manifest and structured capability results

**Status: implemented.** See
[`docs/run-manifest-schema.md`](run-manifest-schema.md) for the schema,
`tournament_scheduler/pipeline/capability_result.py` and
`tournament_scheduler/pipeline/run_manifest.py` for the implementation, and
`rvv-miniputt status --json` for inspecting a run.

### Goal

Create the shared data contract that lets an AI operator understand workspace state, capability outcomes, evidence, confidence, artifacts, blockers, and suggested next actions without parsing human-oriented console logs.

### Scope

- Define a versioned run manifest stored under `.pipeline/`.
- Define a structured capability-result schema with at least:
  - `status`
  - `summary`
  - `evidence`
  - `confidence`
  - `artifacts`
  - `problems`
  - `suggested_actions`
  - `requires_human`
- Record the active objective, current capability, input fingerprints, run ID, timestamps, and final outcome.
- Add JSON output to portable CLI commands where practical.
- Preserve current human-readable terminal output.
- Document schema evolution and backward compatibility.

### Acceptance criteria

- An agent can inspect one documented JSON file or CLI response and determine what happened, what remains blocked, and what it should do next.
- Existing checkpoint files remain usable or have a compatibility path.
- Tests cover `ok`, `warning`, `blocked`, and `failed` outcomes.
- The core contract contains no LLM-provider-specific requirements.

## 2. Add one goal-oriented AI operator entry point

**Status: implemented.** `rvv-miniputt operator run` (or
`scripts/rvv-miniputt operator run`) is a thin wrapper around `rvv-miniputt
run`: it resolves the objective (`--objective`, defaulting to "Produce the
best trustworthy season plan from the current workbook."), auto-detects the
earliest stage that is missing, not done, or stale via
`PipelineState`/`_resolve_operator_resume_stage`, skips the pipeline entirely
when nothing is pending, and prints a final structured summary from the run
manifest once the run completes. `--resume-from` and `--force` remain
available to override auto-detection. See
`tournament_scheduler/cli/pipeline_orchestrator.py` (`_cmd_operator_run`) and
`tests/test_operator_run.py`.

### Goal

Allow the human to request an outcome such as “produce the best trustworthy season plan” without manually coordinating pipeline stages and recovery commands.

### Scope

- Add an operator entry point, for example `rvv-miniputt operator run`.
- Accept an explicit objective and sensible default objective.
- Inspect workspace state and resume from the earliest stale or problematic capability.
- Execute routine recovery and bounded retries.
- Stop and escalate only when human judgment, credentials, authorization, or unrecoverable source data are required.
- Produce a final structured summary and human-readable report.
- Keep harness adapters thin wrappers around the portable entry point.

### Acceptance criteria

- A normal season run can be completed through one goal-oriented command.
- The operator resumes safely after interruption.
- Retry limits and stopping conditions are deterministic and documented.
- The final result distinguishes completed work, warnings, blockers, and requested human decisions.

## 3. Make calendar source health and recovery agent-friendly

**Status: implemented.** `tournament_scheduler/pipeline/source_health.py`
computes one `CapabilityResult` per configured source from the Stage 2
checkpoint and the unified scrape cache: reachability/block state, event
count vs. the existing expectation heuristic, cache age, scraper
strategy/engine, and a comparison against the previous scrape (the cache now
retains exactly one generation of history via `previous_sources`) to flag
sources that went sparse or duplicate-heavy. Inspect it with
`rvv-miniputt sources status` (`--json` for the raw capability results).
`rvv-miniputt run` also folds non-`ok` findings into the "scraping"
capability's `problems`/`suggested_actions` in the run manifest. Recovery
remains the existing composable `recovery-targets` / `recovery-inject` /
`scrape` / `scrape-llm` commands — this capability tells an operator which
source needs one of those and why, rather than requiring manual checkpoint
inspection. See `tests/test_source_health.py` and
`tests/test_cache_manager_history.py`.

### Goal

Turn calendar ingestion from a collection of scraping commands into a capability the operator can inspect, reason about, and repair.

### Scope

- Provide structured source-health results for every configured calendar.
- Record reachability, authentication state, event count, expected range, date coverage, cache age, parser/strategy, and last successful fetch.
- Attach provenance to imported events.
- Compare fresh results against cache and previous known-good snapshots.
- Detect suspiciously sparse, structurally changed, or duplicate-heavy sources.
- Expose recovery actions as composable operations rather than requiring manual checkpoint editing.
- Preserve a clear boundary around credentials and external access.

### Acceptance criteria

- The operator can identify which source is unreliable and why.
- Every planned event can be traced to a source snapshot or manual recovery input.
- Routine retries and cache fallback can happen without human coordination.
- The operator escalates with a focused question when credentials or policy decisions are required.

## 4. Make plan generation reproducible and candidate comparison explainable

**Status: implemented.** `stage3_planning.run()` now records reproducibility
metadata and a compact summary for every `--iterations` candidate under a
`candidates` list on the Stage 3 checkpoint (planner version, config and
source fingerprints, seed, penalty hints, per-metric score breakdown), plus
`selected_candidate_attempt`. Candidate selection now ranks by
`(hard_constraint_status, aggregate_score, tournament_count)` instead of raw
score alone — a "fail" status (a hard-constraint violation, e.g. an
arena/day collision) can no longer be outscored by a good aggregate score
from a candidate that actually violates a hard constraint. Tie-breaking is
fully deterministic (documented in `_candidate_rank`). Locked
assignments/human decisions continue to work unchanged via the existing
manual-adjustments merge. Inspect candidates with `rvv-miniputt candidates`
(`--json` for raw data), which also shows the most consequential fairness
metric differences between the selected candidate and its runner-up. See
`tests/test_stage3_planning.py::TestCandidateTracking` and
`tests/test_candidates_cli.py`.

### Goal

Let the operator generate and compare alternative plans while preserving deterministic validity and a complete audit trail.

### Scope

- Record planner version, configuration, penalty weights, random seed, and input/source fingerprints for every candidate.
- Separate hard-constraint validity from soft-objective scores.
- Produce a documented score breakdown.
- Retain multiple candidate summaries rather than only the selected result.
- Add comparison output showing the most consequential trade-offs.
- Support locked assignments and approved human decisions.
- Define deterministic tie-breaking and candidate-selection behavior.

### Acceptance criteria

- A candidate can be reproduced from its recorded metadata.
- An agent and human can explain why one candidate was preferred.
- Hard-constraint failures cannot be hidden by a good aggregate score.
- Manual locks survive refinement and reruns.

## 5. Add a human escalation and approval protocol

**Status: implemented.** `tournament_scheduler/pipeline/escalation.py`
defines six escalation types (credentials, incomplete data, ambiguous
policy, destructive repair, impossible constraints, external publication)
and a `Question` record (context, alternatives, recommendation, impact)
stored in the run manifest's `pending_questions`. Questions are
content-addressed (stable id from type+capability+summary), so the same
question is never raised twice and an already-answered question is never
reopened. `RunManifest.start_run()` now carries `pending_questions` forward
across runs — escalation state is durable workspace state, not per-run
state, since a human answers between separate CLI invocations. `operator
run` raises a question for every `requires_human` capability result and
surfaces unanswered ones in its summary; `rvv-miniputt operator questions`
/ `operator answer <id> "<answer>"` inspect and resolve them. Resuming after
an answer reuses the existing auto-resume logic from item 2 — recording an
answer doesn't itself mutate pipeline state, it makes the decision durable
and stops the same question from being asked again. See
`docs/run-manifest-schema.md` and `tests/test_escalation.py`.

### Goal

Give the operator a consistent way to pause for genuine human decisions and continue afterward without losing state.

### Scope

- Define escalation types such as credentials, incomplete data, ambiguous policy, destructive repair, impossible constraints, and external publication.
- Store pending questions in the run manifest.
- Include context, alternatives, recommendation, and impact for every question.
- Allow a human answer to be recorded as a durable decision.
- Resume from the correct capability after an answer.
- Prevent repeated questions that have already been answered for the active run.

### Acceptance criteria

- Every blocked run explains exactly what decision is needed.
- Human decisions are auditable and survive restart.
- The operator can resume without rerunning unaffected work.
- External writes remain explicitly authorized.

## 6. Reframe the README around the AI operator workflow

### Goal

Make the preferred product model clear while retaining CLI, harness, and developer documentation.

### Scope

- Lead with the AI-operator product promise.
- Show one primary goal-oriented quick start.
- Move detailed harness adapter material into a development/integration section.
- Explain the deterministic core and optional role of AI judgment.
- Link to the product-direction and roadmap documents.
- Keep manual stage and recovery commands as debugging/advanced workflows.

### Acceptance criteria

- A new reader understands within the first screen that RVV Miniputt is an AI-operated season-planning system.
- The README clearly distinguishes preferred usage, portable CLI usage, and development internals.
- Existing commands remain discoverable without dominating the product explanation.

## 7. Reposition the desktop app as an optional supervisor console

### Goal

Avoid building a second independent product while preserving a path to a non-technical supervisory interface.

### Scope

- Document the desktop app as an optional surface over the same operator capabilities.
- Show objective, progress, source health, pending questions, candidate comparison, approvals, and artifacts.
- Remove or avoid business logic duplicated in Electron.
- Consume structured capability results and the run manifest.
- Verify packaging and GitHub release configuration.

### Acceptance criteria

- The desktop app can be omitted without reducing core operator capability.
- It does not implement separate scheduling or recovery behavior.
- A future non-technical user can supervise the same run state used by CLI and harness agents.

## Suggested delivery order

1. Run manifest and capability-result contract.
2. Goal-oriented operator entry point.
3. Calendar source health and recovery.
4. Reproducible candidate comparison.
5. Human escalation and approval.
6. README restructuring.
7. Desktop supervisor console.

The first two items establish the operator architecture. Items three through five make it trustworthy. Items six and seven clarify and broaden the user experience after the core workflow is stable.
