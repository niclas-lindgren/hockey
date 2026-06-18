Run the RVV Miniputt season-scheduling pipeline stage-by-stage, reviewing each checkpoint before proceeding to the next stage.

Rules:
- Never run `/rvv-miniputt ...` as a shell command.
- Do NOT run `scripts/rvv-miniputt run` or `python3 -m tournament_scheduler.cli.rvv_cli run` as a black box — that bypasses inter-stage review.
- Invoke each stage individually using the commands below.
- After each stage, read the checkpoint JSON from `.pipeline/` and verify it looks correct before continuing.
- If a stage exits with a non-zero code, stop and report the error.
- All stages share the same `PipelineState` checkpoint files so stages can be re-run independently.

Stage-by-stage orchestration:

**Stage 1 — Config**
```bash
python3 -m tournament_scheduler.pipeline.stage1_config [--input input.xlsx] [--work-dir .pipeline]
```
Read `.pipeline/stage1_config.json` and verify: `teams` non-empty (9 RVV clubs), `age_groups` populated, `parallel_games` present, `target_tournament_count` ≥ 1, `sources` non-empty.

**Stage 2 — Scraping**
```bash
python3 -m tournament_scheduler.pipeline.stage2_scraping [--work-dir .pipeline] [--force-refresh] [--non-strict] [--allow-missing-sources]
```
Read `.pipeline/stage2_scraping.json` and verify: `sources` has events for expected clubs, `blocked` is empty or approved, note `cached` sources.

**Stage 3 — Planning**
```bash
python3 -m tournament_scheduler.pipeline.stage3_planning [--work-dir .pipeline]
```
Read `.pipeline/stage3_planning.json` and verify: `plan` non-empty (tournaments with date, host, age group), no overlapping-player-pool conflicts on same weekend, no critical `rules_report` violations.

**Stage 4 — Export**
```bash
python3 -m tournament_scheduler.pipeline.stage4_export [--work-dir .pipeline] [--export-dir export] [--no-timestamped-export]
```
Read `.pipeline/stage4_export.json` and report files written under `export/` and any `errors`.

Checkpoint review helper:
```bash
python3 -m tournament_scheduler.cli.checkpoint_printer stage1
python3 -m tournament_scheduler.cli.checkpoint_printer stage2
python3 -m tournament_scheduler.cli.checkpoint_printer stage3
python3 -m tournament_scheduler.cli.checkpoint_printer stage4
```

Resuming from a specific stage (when earlier checkpoints are already valid):
```bash
python3 -m tournament_scheduler.cli.rvv_cli run --resume-from 3
```

Flags for stage 2:
```
--force-refresh             Clear calendar cache before scraping
--non-strict                Continue on blocked sources or warnings
--allow-missing-sources     Treat blocked sources as operator-approved and keep partial results
```

Flags for stage 4:
```
--export-dir <path>         Export directory (default: export)
--no-timestamped-export     Write exports flat instead of a timestamped subfolder
```
