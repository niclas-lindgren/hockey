# AI operator run manifest schema

This document specifies the versioned run manifest and capability-result
contract introduced to satisfy the first item of the
[AI operator implementation roadmap](ai-operator-roadmap.md): a shared data
contract an agent can inspect to understand workspace state, capability
outcomes, evidence, confidence, artifacts, blockers, and suggested next
actions without parsing human-oriented console logs.

It complements, and does not replace, the existing per-stage checkpoint
files documented in `tournament_scheduler/pipeline/state.py`
(`.pipeline/stage1_config.json` … `stage4_export.json`). Those remain the
source of truth for stage data; the run manifest is a higher-level,
operator-facing summary layered on top.

## Where it lives

```
<work_dir>/run_manifest.json      # default work_dir is .pipeline
```

Written and read via `tournament_scheduler.pipeline.run_manifest.RunManifest`.

## Capability result contract

Every capability (a pipeline stage, a recovery action, a future source-health
check, etc.) can report a structured outcome via
`tournament_scheduler.pipeline.capability_result.CapabilityResult`:

```json
{
  "schema_version": 1,
  "capability": "scraping",
  "status": "warning",
  "summary": "6 source(s) scraped, 1 blocked",
  "evidence": [],
  "confidence": 1.0,
  "artifacts": [],
  "problems": ["rvv-club-x.no"],
  "suggested_actions": [],
  "requires_human": false
}
```

Fields:

| Field                | Type                | Meaning                                                                 |
|-----------------------|--------------------|---------------------------------------------------------------------------|
| `schema_version`      | int                | Capability-result schema version (see [Versioning](#versioning)).         |
| `capability`           | string             | Name of the capability that produced this result (e.g. `"config"`).       |
| `status`               | string             | One of `ok`, `warning`, `blocked`, `failed`.                              |
| `summary`              | string             | One or two sentence human-readable description of what happened.         |
| `evidence`             | array              | Concrete facts backing the summary.                                       |
| `confidence`           | float (0.0–1.0)    | How much the result should be trusted. Informational only.                |
| `artifacts`            | array of strings   | Paths/identifiers of files or checkpoints produced.                       |
| `problems`             | array of strings   | Concrete issues encountered, even on `ok`.                                |
| `suggested_actions`    | array of strings   | Concrete next steps for a human or agent.                                 |
| `requires_human`       | bool               | True when this result cannot be resolved without human judgment.          |

`status` values map onto the escalation model described in
[`docs/ai-operator-product-direction.md`](ai-operator-product-direction.md):

- `ok` — completed as expected.
- `warning` — completed, but with something worth surfacing (a blocked
  source, a rough plan verdict, etc).
- `blocked` — cannot proceed without a human decision (`requires_human` is
  forced `True` by `CapabilityResult.blocked(...)`).
- `failed` — the capability did not complete.

## Run manifest contract

```json
{
  "schema_version": 1,
  "run_id": "20260726T091500Z-3f2a9c1d",
  "objective": "Produce the best trustworthy season plan from the current workbook.",
  "current_capability": "export",
  "input_fingerprint": {
    "path": "/path/to/input.xlsx",
    "sha256": "…"
  },
  "started_at": "2026-07-26T09:15:00+00:00",
  "updated_at": "2026-07-26T09:18:42+00:00",
  "ended_at": "2026-07-26T09:18:42+00:00",
  "final_outcome": "ok",
  "capabilities": [
    { "...": "one CapabilityResult entry per recorded capability, in order, each with a recorded_at timestamp" }
  ],
  "pending_questions": [
    { "...": "one Question entry per escalation raised in this workspace — see below" }
  ]
}
```

| Field                 | Meaning                                                                                   |
|------------------------|--------------------------------------------------------------------------------------------|
| `schema_version`       | Run-manifest schema version.                                                              |
| `run_id`                | Unique ID for this run (`<UTC timestamp>-<8 hex chars>`).                                  |
| `objective`             | The active objective, in the human's own words if provided, else a sensible default.       |
| `current_capability`    | Name of the capability that most recently ran or is running.                               |
| `input_fingerprint`     | Path + SHA-256 of the input workbook at run start.                                          |
| `started_at` / `updated_at` / `ended_at` | ISO-8601 UTC timestamps. `ended_at` is `null` until `finalize()` is called.  |
| `final_outcome`         | `in_progress` until finalized, then one of `ok`, `warning`, `blocked`, `failed`.            |
| `capabilities`          | Ordered history of every `CapabilityResult` recorded during the run.                        |
| `pending_questions`     | Escalation questions raised in this workspace, answered or not — see below.                 |

`rvv-miniputt run` starts a manifest at the beginning of every run, records a
capability result after each of the four pipeline stages, and finalizes the
manifest with the run's terminal outcome. Manifest writes are best-effort:
a failure to write the manifest never aborts the pipeline itself.

`start_run()` resets `capabilities` and the run's timestamps/outcome for the
new run, but **carries `pending_questions` forward unchanged** from any
existing manifest. Escalation questions and their human answers are durable
workspace state, not per-run state — a human answers a question in a
separate CLI invocation from the one that raised it, so that answer has to
survive the next `start_run()` call or the escalation protocol below
couldn't work at all.

## Human escalation and approval protocol

Defined in `tournament_scheduler/pipeline/escalation.py`. Any capability that
returns a `CapabilityResult` with `requires_human: true` can be turned into a
`Question` and raised into `pending_questions`:

```json
{
  "id": "abbee2e6f80e4678",
  "type": "credentials",
  "capability": "scraping",
  "summary": "Kongsberg ishall blocked",
  "context": "event_count=0; strategy=browser",
  "alternatives": ["Set credentials via KONGSBERG_USER", "Try scrape-llm"],
  "recommendation": "Set credentials via KONGSBERG_USER",
  "impact": "Timeout loading the page",
  "created_at": "2026-07-26T09:16:00+00:00",
  "answered": false,
  "answer": null,
  "decided_by": null,
  "decided_at": null
}
```

`type` is one of six escalation types: `credentials`, `incomplete_data`,
`ambiguous_policy`, `destructive_repair`, `impossible_constraints`,
`external_publication`. A question's `id` is a stable hash of
`(type, capability, summary)`, so raising the *same* question again — from a
retried or resumed run — is a no-op rather than a duplicate, and raising a
question that was already answered leaves the recorded answer untouched
instead of reopening it.

`rvv-miniputt operator run` raises a question for every capability result
that came back `requires_human: true` after the pipeline finishes, and
prints any still-unanswered ones as part of its final summary. Inspect and
resolve them with:

```bash
rvv-miniputt operator questions [--json]
rvv-miniputt operator answer <question-id> "<answer>" [--decided-by NAME]
```

Answering records a durable, auditable decision — it does not itself change
pipeline state. Running `rvv-miniputt operator run` again afterwards picks
up from the earliest stale/pending capability as usual (see item 2); the
human's answer being on record just means the same question won't be raised
a second time.

## Inspecting a run

```bash
rvv-miniputt status --json
# or
python3 -m tournament_scheduler.cli.rvv_cli status --json
```

prints the current run manifest as JSON. The existing human-readable
`rvv-miniputt status` output is unchanged.

## Backward compatibility

Work directories populated before this schema existed have per-stage
checkpoint files but no `run_manifest.json`. `RunManifest.read()` handles
this transparently: when no manifest file exists (or it fails to parse), a
manifest-shaped view is synthesized from the legacy `stage*.json`
checkpoints, with `"synthesized_from_legacy_checkpoints": true` set so
callers can tell the difference. Every field the manifest normally promises
is still populated — derived from data that was already on disk — so
callers do not need a special code path for old work directories.

## Versioning

`CAPABILITY_RESULT_SCHEMA_VERSION` and `RUN_MANIFEST_SCHEMA_VERSION`
(both currently `1`) are bumped only on a breaking change — removing or
renaming a field, or changing a field's meaning. Adding a new optional field
with a safe default is not a breaking change and does not require a bump.

`CapabilityResult.from_dict()` ignores unknown keys, so code built against an
older schema version can still read a manifest written by a newer one as
long as no field it depends on was removed or repurposed. A future breaking
change should be accompanied by an explicit migration path (e.g. a
`schema_version`-keyed reader) rather than assuming all readers upgrade in
lockstep.
