# Plan: Harness auto-refinement loop for rough season plans

**Goal:** When /rvv-miniputt:run reads a stage 3 checkpoint with judgment tone "rough" (IKKE KLAR), the harness calls auto-adjust CLI up to 3 times and re-runs stage 4 export after each attempt until the tone is no longer rough or the retry cap is reached.
**Created:** 2026-06-21
**Intent:** Eliminate the silent bypass in run.md that proceeds straight to stage 4 on any valid plan, so rough plans are automatically refined before export rather than silently delivered to organizers.
**Backlog-ref:** 181

## Tasks

- [x] Added verdict command step after stage 3 validation that runs python3 -m tournament_scheduler.cli.rvv_cli verdict --work-dir .pipeline and parses the tone output line. — 2026-06-21
  - Files: .claude/commands/rvv-miniputt/run.md
  - Approach: After validating the stage 3 checkpoint (non-empty plan, no critical violations), add a step that runs `python3 -m tournament_scheduler.cli.rvv_cli verdict --work-dir .pipeline` and captures the tone value from its output to determine whether refinement is needed.

- [x] Replaced unconditional stage 4 proceed with a tone-gated loop: while tonerough and iterations<3, calls auto-adjust CLI then re-runs stage 4 export then rechecks tone via verdict. — 2026-06-21
  - Files: .claude/commands/rvv-miniputt/run.md
  - Approach: Replace the current stub step that unconditionally proceeds to stage 4 with a conditional block: if tone is "rough", enter a retry loop (up to 3 iterations) that calls `python3 -m tournament_scheduler.cli.rvv_cli auto-adjust --work-dir .pipeline --max-iterations 3`, then re-runs stage 4 export (`python3 -m tournament_scheduler.pipeline.stage4_export --work-dir .pipeline`), then rechecks tone via `verdict`; exit the loop when tone is no longer "rough" or the cap is reached.

- [x] Added post-loop reporting section that summarizes initial tone, number of refinement iterations run, final tone, and a warning if the 3-iteration cap was reached with tone still rough. — 2026-06-21
  - Files: .claude/commands/rvv-miniputt/run.md
  - Approach: After the refinement loop terminates, add a step that prints a summary to the user: how many auto-adjust iterations ran, the initial tone, and the final tone — using the same Rich/CLI output convention already used elsewhere in the command file.

## Notes

The Python orchestrator (tournament_scheduler/cli/pipeline_orchestrator.py) already has _run_refinement_loop and _run_refinement_and_reexport fully implemented and tested. The gap is exclusively in the Claude command harness: .claude/commands/rvv-miniputt/run.md says "proceed directly to stage 4" without checking tone. Tasks 1-3 address run.md only; task 4 adds coverage for the already-implemented Python path.

Tone values: "rough" (IKKE KLAR) triggers refinement, "mixed" (BLANDET) and "strong" (SOLID) do not.
The `verdict` subcommand in rvv_cli.py prints the tone; parse it to gate the loop.
The auto-adjust CLI: `python3 -m tournament_scheduler.cli.rvv_cli auto-adjust --work-dir .pipeline --max-iterations 3`.
Stage 4 re-export: `python3 -m tournament_scheduler.pipeline.stage4_export --work-dir .pipeline`.

## Acceptance Criteria

- [ ] When a stage 3 checkpoint has judgment tone "rough", run.md calls auto-adjust at least once before proceeding to final stage 4 export, and the harness reports how many iterations ran.
- [ ] When the judgment tone is not "rough" after stage 3, run.md does not call auto-adjust and proceeds directly to stage 4 export.
- [ ] The refinement loop in run.md exits after at most 3 iterations even when tone remains "rough" throughout all iterations.
- [ ] After the refinement loop exits, run.md re-runs stage 4 export and reports the final tone to the user.
- [x] The test suite contains a test that passes when tone transitions from "rough" to "mixed" on the second auto-adjust iteration and the loop exits after two iterations (already covered in tests/test_pipeline_orchestrator.py line 201).

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-21 — Added verdict command step after stage 3 validation that runs python3 -m tournament_scheduler.cli.rvv_cli verdict --work-dir .pipeline and parses the tone output line.
**Rationale:** none
**Findings:** Verdict command outputs keyvalue pairs including tonerough/mixed/strong; this step captures the initial tone before deciding whether refinement is needed.
LESSONS: none
**Files:** .claude/commands/rvv-miniputt/run.md (+50/-1)
**Commit:** [pending — fill after commit]

### 2026-06-21 — Replaced unconditional stage 4 proceed with a tone-gated loop: while tonerough and iterations<3, calls auto-adjust CLI then re-runs stage 4 export then rechecks tone via verdict.
**Rationale:** none
**Findings:** Loop exits early when tone improves to mixed or strong; proceeds to stage 4 only after loop exits.
LESSONS: none
**Files:** .claude/commands/rvv-miniputt/run.md (+50/-1)
**Commit:** [pending — fill after commit]

### 2026-06-21 — Added post-loop reporting section that summarizes initial tone, number of refinement iterations run, final tone, and a warning if the 3-iteration cap was reached with tone still rough.
**Rationale:** none
**Findings:** Reporting uses the same inline text format as other stage summaries in run.md.
LESSONS: none
**Files:** .claude/commands/rvv-miniputt/run.md (+50/-1)
**Commit:** [pending — fill after commit]
