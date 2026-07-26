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

**Status: partially implemented — see `docs/desktop-app.md` for the full
breakdown.** Confirmed and documented that the app can be omitted without
losing operator capability (the CLI already reaches every capability the
backend calls). Fixed a dead/broken endpoint (`POST /run` called an
undefined function, unreachable from the actual UI, now removed) and a real
release-pipeline bug (`keyring` wasn't installed for the Linux leg of
`release.yml`, silently degrading credential storage on Linux release
builds). Added `GET /manifest` and `GET /questions` /
`POST /questions/answer` so the backend can serve the same run manifest and
escalation questions the CLI uses. The stage *execution* was already shared
with the CLI (same stage modules, same checkpoints) — not duplicated.
**Not resolved:** `_run_smart`'s bounded retry loop still makes its own
per-stage LLM calls for narration instead of delegating to `operator run`
(issue #2) and translating its manifest into UI narration — left in place
deliberately, since replacing it risks removing real end-user-facing
behavior (live LLM narration) in a session with no way to run the actual
Electron app to verify the change. See `docs/desktop-app.md` for the
specific follow-up.

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

## Second wave: the observe-decide-act loop (issues #10-#16)

Once items 1-7 above landed, a second wave of issues turns the entry point
from a smart-resume command into an actual bounded operator loop. Delivery
order: #16 first (CI validates everything that follows), then #10 → #11
(typed actions before the loop that dispatches them), #12/#14/#15
independently, then #13 integrated into the loop last.

### 16. Add required CI checks for operator trustworthiness

**Status: implemented.** See [`docs/ci.md`](ci.md).

### 10. Add typed operator actions to capability results

**Status: implemented.** `tournament_scheduler/pipeline/operator_action.py`
defines a versioned `OperatorAction` (`action_id`, `description`,
`arguments`, `risk_level`, `requires_approval`, `retryable`, `capability`)
and an `ActionRegistry` mapping stable action IDs to real executors:
`retry_source`, `use_trusted_cache`, `refresh_source`,
`request_credentials` (raises a #5 escalation question), `rerun_planning`,
`compare_candidates`, `export_selected_plan`. `CapabilityResult` gained an
additive `actions: list[OperatorAction]` field alongside the existing
string-based `suggested_actions` — fully backward compatible, nothing that
reads `suggested_actions` needs to change. `destructive`/`external` risk
levels are enforced to require approval at construction time (a
`ValueError`, not just a convention), and `ActionRegistry.execute()` refuses
to run an approval-required action without `approved=True`, raising
structured `UnknownActionError`/`ApprovalRequiredError` (both carry a stable
`code` and `to_dict()`) rather than a bare exception. See
`tests/test_operator_action.py`.

### 11. Implement an observe-decide-act AI operator loop

**Status: implemented.** `tournament_scheduler/pipeline/operator_loop.py`
adds `run_source_recovery_loop()`, a bounded observe (source_health, #3)
-> decide (pure policy function) -> act (dispatch through the #10
`ActionRegistry`) -> evaluate -> continue/retry/escalate/finish loop for
calendar source recovery. `rvv-miniputt operator run` runs it unconditionally
before deciding where to resume from, and forces at least a Stage 2 rerun
when it repairs anything. Bounded by `max_retries_per_source` (default 2)
and `max_actions` (default 10), plus no-progress detection that escalates
instead of retrying an action that produced an identical result twice in a
row. Every step is recorded in the run manifest's new `action_log` field via
`RunManifest.record_action_transition()` — see
[`docs/run-manifest-schema.md`](run-manifest-schema.md). The policy function
never calls an LLM; an optional `action_proposer` may steer *which*
registered action runs but can't invent a new one. Tests in
`tests/test_operator_loop.py` (19 tests) and the wiring into
`_cmd_operator_run` in `tests/test_operator_run.py`.

### 12. Scope durable operator decisions and escalation questions

**Status: implemented.** `tournament_scheduler/pipeline/escalation.py` adds
`DecisionScope` (`run` / `input_version` / `season` / `workspace`, narrowest
to broadest) and `scope`/`scope_key` fields on `Question`. Anything narrower
than `workspace` bakes `(scope, scope_key)` into the question's stable id,
so a context change (new run, new workbook, new season) naturally produces
a fresh escalation instead of silently reusing an old answer; the
superseded entry is marked `stale: true` with a `stale_reason` rather than
deleted, preserving its audit history
(`RunManifest.add_pending_question()`). `workspace` scope is unchanged from
pre-#12 behavior and remains the default, so every existing call site and
question is unaffected unless it opts into a narrower scope.
`RunManifest.promote_question()` / `escalation.promote_question()` copy an
answered decision into a new entry under a strictly broader scope without
touching the original. `_raise_escalation_questions` in
`pipeline_orchestrator.py` now scopes capability escalations to
`input_version` (falling back to `workspace` without a fingerprint) as a
concrete example of a run-specific-turned-durable question. CLI:
`rvv-miniputt operator questions --all` (include answered/stale) and
`rvv-miniputt operator promote <id> <scope> [--scope-key KEY]`; desktop API:
`GET /questions?all=1`, `POST /questions/promote`. See
[`docs/run-manifest-schema.md`](run-manifest-schema.md#decision-scoping-issue-12)
for the full scope table and examples. Tests in `tests/test_escalation.py`
(all four scopes, staleness, promotion, and backward compatibility with
pre-#12 questions) and `tests/test_desktop_server_escalation.py`.

### 13. Make source readiness depend on coverage and downstream impact

Not yet implemented. Depends on #10/#11.

### 14. Make operator manifest persistence observable and reliable

**Status: implemented.** `RunManifest._write()` now writes atomically (temp
file + `os.replace()`), raising `ManifestPersistenceError` on failure and
leaving the previous valid manifest untouched. `RunManifest.read()`
distinguishes "no manifest yet" from "manifest exists but is corrupted": a
corrupted file is backed up alongside itself and the returned (still
usable, synthesized) manifest carries a `manifest_recovery` diagnostic that
`rvv-miniputt status --json` surfaces automatically. `RunManifest.check_health()`
/ `run_manifest.is_durable()` add the operator-state health check, exposed
via `rvv-miniputt operator health [--json]`. The manifest wrapper functions
in `cli/pipeline_orchestrator.py` no longer swallow exceptions silently —
`_warn_manifest_failure()` prints a visible warning, logs it to
`<work_dir>/logs/manifest_warnings.log`, and caps the run's final outcome at
`warning` instead of `ok` when persistence degraded anywhere during the
run. `ActionRegistry.execute()` (issue #10) now refuses to run an approved,
approval-required action when its manifest isn't durably writable, raising
`PersistenceUnavailableError`. See
[`docs/run-manifest-schema.md`](run-manifest-schema.md#manifest-persistence-reliability-issue-14)
for the full behavior and JSON shapes. Tests in
`tests/test_manifest_persistence.py` (34 tests: atomic writes, corruption
recovery, health check, visible warnings, outcome downgrade, the
approval/durability gate, and backward compatibility).

### 15. Clarify active, completed, and recommended capability state

Not yet implemented.

## Third wave: public publishing (issues #17-#20)

A third wave lets the operator publish an approved run to GitHub Pages
without a custom GitHub Actions workflow. Delivery order: #17 first (the
publish mechanism itself), then #18 (a sanitized public bundle and privacy
report — #17 publishes the raw Stage 4 export as-is and does not sanitize
it), #19 (an explicit approval gate for unattended/harness publish
invocations), #20 (verification and rollback).

### 17. Add operator-driven GitHub Pages publishing

**Status: implemented.** `tournament_scheduler/pipeline/pages_publish.py`
adds `publish()`, which copies a Stage 4 export bundle onto a dedicated
`gh-pages` branch under both `/latest/` (overwritten every publish) and the
immutable `/runs/<run-id>/`, plus a root `index.html` (redirects to
`/latest/`) and `.nojekyll`. It never touches the caller's checkout — a
short-lived `git worktree` does the branch checkout/commit — and never force
pushes: a diverged local `gh-pages` is reported as a failure rather than
overwritten, and a push failure leaves the commit intact locally for a
retry. Republishing an unchanged bundle for the same run id is a no-op (no
empty commit). The public URL is derived from the `origin` remote
(`https://<owner>.github.io/<repo>/...`). Registered as the `publish_pages`
operator action (`external` risk, `requires_approval=True`, same invariant
as `export_selected_plan` from #10). CLI: `rvv-miniputt operator publish`
and `rvv-miniputt operator run --publish`; running either is itself the
human approval for this pass — #19 will add an explicit escalation gate for
invocations that shouldn't auto-approve (e.g. an unattended harness run).
See `tests/test_pages_publish.py` (initial branch creation, `/latest/`
updates, `/runs/<run-id>/` retention, no-op republish, and push failure) and
`tests/test_operator_action.py::TestPublishPagesExecutor`.
