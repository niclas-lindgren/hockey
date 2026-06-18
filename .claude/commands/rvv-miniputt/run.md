---
name: "RVV Miniputt: Run"
description: "Run the RVV Miniputt pipeline stage-by-stage with checkpoint review between stages"
category: RVV
---

Run the RVV Miniputt season-scheduling pipeline by invoking each stage individually and reviewing the checkpoint before proceeding to the next stage.

## Rules

- Never run `/rvv-miniputt ...` as a shell command.
- Do NOT call `scripts/rvv-miniputt run` or `python3 -m tournament_scheduler.cli.rvv_cli run` as a black box — that bypasses the inter-stage review.
- Run each stage individually, read the checkpoint JSON after each stage, and only proceed if the output looks correct.
- If a stage fails (non-zero exit code), stop and report the error to the user.

## Stage-by-stage orchestration

### Stage 1 — Config

```bash
python3 -m tournament_scheduler.pipeline.stage1_config [--input input.xlsx] [--work-dir .pipeline]
```

After success, read `.pipeline/stage1_config.json` and verify:
- `teams` list is non-empty and contains all 9 RVV clubs
- `age_groups` is populated
- `parallel_games` config is present
- `target_tournament_count` is a reasonable number (≥ 1)
- `sources` list is non-empty

Stop and ask the user if any of these look wrong before continuing.

### Stage 2 — Scraping

```bash
python3 -m tournament_scheduler.pipeline.stage2_scraping [--work-dir .pipeline] [--force-refresh] [--non-strict] [--allow-missing-sources]
```

After success, read `.pipeline/stage2_scraping.json` and verify:
- `sources` list contains scraped events for the expected clubs
- `blocked` list (sources that failed) is empty or explicitly approved by the user
- `cached` sources are noted for transparency

**Recovery check — blocked and empty sources:**
Inspect `data.blocked` and `data.sources` from the checkpoint:
1. **Blocked sources:** Any entry in `data.blocked`, or any source in `data.sources` where `blocked == true`. These failed entirely — no events were retrieved.
2. **Zero-event sources:** Any source in `data.sources` where `event_count == 0` and `blocked == false`. These scraped successfully but returned no calendar events (may indicate a layout change, empty season, or wrong URL).

For each blocked or zero-event source, report:
- Source name and URL
- `block_reason` (if blocked)
- Whether `llm_fallback` was attempted
- Suggested recovery: try `--force-refresh` for a transient failure; if the issue persists, check the source URL manually or add an LLM-assisted scraper for that source

Do **not** proceed to Stage 3 if any sources are blocked and `--non-strict` was not passed. For zero-event sources, ask the user whether to continue or investigate further.

If any sources are blocked and `--non-strict` was not passed, stop and report which sources failed before continuing.

### Stage 3 — Planning

```bash
python3 -m tournament_scheduler.pipeline.stage3_planning [--work-dir .pipeline]
```

After success, read `.pipeline/stage3_planning.json` and verify:
- `plan` is present and contains a non-empty list of tournaments
- Each tournament has a date, host club, and age group
- No two tournaments with overlapping player pools are scheduled on the same weekend
- `rules_report` section (if present) shows no critical violations

Stop and ask the user to review the plan before exporting if anything looks unexpected.

### Stage 4 — Export

```bash
python3 -m tournament_scheduler.pipeline.stage4_export [--work-dir .pipeline] [--export-dir export] [--no-timestamped-export]
```

After success, read `.pipeline/stage4_export.json` and report:
- List of files written under `export/` (or the timestamped subfolder)
- Any `errors` present in the checkpoint

## Checkpoint review helper

To pretty-print any checkpoint in a compact human-readable form:

```bash
python3 -m tournament_scheduler.cli.checkpoint_printer stage1
python3 -m tournament_scheduler.cli.checkpoint_printer stage2
python3 -m tournament_scheduler.cli.checkpoint_printer stage3
python3 -m tournament_scheduler.cli.checkpoint_printer stage4
```

## Resuming from a specific stage

To skip earlier stages whose checkpoints already exist, pass `--resume-from N` to the full pipeline runner (stages 1 through N-1 will be skipped):

```bash
python3 -m tournament_scheduler.cli.rvv_cli run --resume-from 3
```

Use this only when the earlier checkpoint files in `.pipeline/` are already valid and you want to re-run from a specific stage.

## Examples

- `/rvv-miniputt:run` — run all four stages with checkpoint review between each
- `/rvv-miniputt:run --force-refresh` — pass `--force-refresh` to Stage 2 to bypass cached calendar data
- `/rvv-miniputt:run --non-strict` — pass `--non-strict` to Stage 2 to continue if some sources are blocked
