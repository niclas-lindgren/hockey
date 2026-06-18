# RVV Miniputt: Run (ChatGPT)

Run the RVV Miniputt season-scheduling pipeline stage-by-stage, reviewing each checkpoint before proceeding to the next stage.

## Rules

- Do NOT run `scripts/rvv-miniputt run` or `python3 -m tournament_scheduler.cli.rvv_cli run` as a black box — that bypasses inter-stage review.
- Invoke each stage individually using the commands below.
- After each stage, read the checkpoint JSON and verify it looks correct before continuing.
- If a stage exits with a non-zero code, stop and report the error.

## Stage-by-stage orchestration

### Stage 1 — Config

```bash
python3 -m tournament_scheduler.pipeline.stage1_config [--input input.xlsx] [--work-dir .pipeline]
```

Read `.pipeline/stage1_config.json` and verify before continuing:
- `teams` is non-empty and contains all 9 RVV clubs
- `age_groups` is populated
- `parallel_games` config is present
- `target_tournament_count` ≥ 1
- `sources` list is non-empty

### Stage 2 — Scraping

```bash
python3 -m tournament_scheduler.pipeline.stage2_scraping [--work-dir .pipeline] [--force-refresh] [--non-strict] [--allow-missing-sources]
```

Read `.pipeline/stage2_scraping.json` and verify before continuing:
- `sources` contains scraped events for the expected clubs
- `blocked` list is empty or explicitly approved
- Note any `cached` sources not re-fetched

### Stage 3 — Planning

```bash
python3 -m tournament_scheduler.pipeline.stage3_planning [--work-dir .pipeline]
```

Read `.pipeline/stage3_planning.json` and verify before continuing:
- `plan` is non-empty (tournaments with date, host club, age group)
- No two tournaments with overlapping player pools share a weekend
- `rules_report` (if present) shows no critical violations

### Stage 4 — Export

```bash
python3 -m tournament_scheduler.pipeline.stage4_export [--work-dir .pipeline] [--export-dir export] [--no-timestamped-export]
```

Read `.pipeline/stage4_export.json` and report:
- Files written under `export/`
- Any `errors` in the checkpoint

## Checkpoint review helper

Pretty-print any checkpoint in compact human-readable form:

```bash
python3 -m tournament_scheduler.cli.checkpoint_printer stage1
python3 -m tournament_scheduler.cli.checkpoint_printer stage2
python3 -m tournament_scheduler.cli.checkpoint_printer stage3
python3 -m tournament_scheduler.cli.checkpoint_printer stage4
```

## Resuming from a specific stage

To skip earlier stages whose checkpoints already exist:

```bash
python3 -m tournament_scheduler.cli.rvv_cli run --resume-from 3
```

Use only when earlier checkpoint files in `.pipeline/` are already valid.

## Examples

- Run all stages: invoke Stage 1, review, then Stage 2, review, then Stage 3, review, then Stage 4.
- Force-refresh calendars: pass `--force-refresh` to the Stage 2 invocation.
- Continue past blocked sources: pass `--non-strict` to the Stage 2 invocation.
