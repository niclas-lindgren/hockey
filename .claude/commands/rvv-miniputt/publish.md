---
name: "RVV Miniputt: Run + Publish"
description: "Run the full RVV Miniputt pipeline and publish the result to GitHub Pages, auto-confirmed, in one step"
category: RVV
---

Run the full RVV Miniputt pipeline end to end and publish the resulting season plan to GitHub Pages, without pausing for a manual approval step.

## What this does differently from `/rvv-miniputt:run`

`/rvv-miniputt:run` reviews each stage's checkpoint before proceeding and never publishes. This command runs the pipeline non-interactively via the `operator` entry point and then publishes with `--confirm-public` set automatically — no pause for human confirmation between "plan looks good" and "it's live on GitHub Pages."

**This intentionally skips the approval gate that `operator run --publish` alone leaves in place** (that flag only previews and raises an approval question by design — see `_cmd_operator_publish` in `tournament_scheduler/cli/pipeline_orchestrator.py`). Use this command only when you want that gate skipped for this run. If you want the safer default (run, then a human explicitly approves before publish), use `/rvv-miniputt:run` followed by a separate, explicit `operator publish --confirm-public` once you've reviewed the export.

**What still stops this command even in auto-confirm mode:** hard validation failures are not bypassed by `--confirm-public` — it only skips the *approval* step, not correctness checks. Stage 4 export refuses to produce output when hard scheduling conflicts remain (arena double-bookings, per issue #27's "Block export and publish on arena conflicts"), and `operator publish` will fail if there is no valid export to publish. If the run fails, or the export step reports errors, stop and report them — do not retry with weaker flags without telling the user why the run failed first.

## Steps

1. Run the full pipeline through the operator entry point:

   ```bash
   python3 -m tournament_scheduler.cli.rvv_cli operator run [--force-refresh] [--non-strict] [--allow-missing-sources]
   ```

   Pass `--force-refresh` only if the user asked for a fresh scrape; pass `--non-strict` / `--allow-missing-sources` only if the user has already accepted degraded source coverage for this run.

2. Check the exit code. If non-zero, or if `.pipeline/stage4_export.json` has a non-empty `errors` list, stop here and report the failure — do not proceed to publish. Print the errors and any pending escalation questions (`operator questions`).

3. If the run succeeded, publish immediately with the approval gate auto-confirmed:

   ```bash
   python3 -m tournament_scheduler.cli.rvv_cli operator publish --confirm-public
   ```

   This also runs post-publish reachability verification by default (issue #20) — do not pass `--no-verify` unless the user asks.

4. Report to the user:
   - Final plan tone (from the `operator run` summary)
   - Whether publish succeeded, and the published URL
   - Any warnings surfaced (e.g. fairness-gate warn-level metrics) even if they didn't block publish

## If something goes wrong after publishing

To roll `/latest/` back to the previous published run:

```bash
python3 -m tournament_scheduler.cli.rvv_cli operator publish-history
python3 -m tournament_scheduler.cli.rvv_cli operator rollback <run_id> --confirm-public
```

Confirm the target `run_id` with the user before rolling back — this is also a public-facing change.

## Examples

- `/rvv-miniputt:publish` — run the full pipeline and publish on success, no pause
- `/rvv-miniputt:publish --non-strict` — same, but tolerate blocked scrape sources
