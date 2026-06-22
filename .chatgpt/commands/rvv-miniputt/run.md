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

**Recovery loop — attempt to fetch events for each problem source:**
For each source returned by `rvv-miniputt recovery-targets`:

```bash
python3 -m tournament_scheduler.cli.rvv_cli recovery-targets [--work-dir .pipeline]
```

Attempt recovery in this order:
1. Use WebFetch (or the browser tool) to retrieve the source's `url`.
2. Extract a list of calendar event objects from the HTML. Each object should have at minimum `title`, `start` (ISO 8601 date or datetime), and optionally `end`, `location`, `description`.
3. If events were extracted, inject them into the cache:
   ```bash
   echo '<JSON-array>' | python3 -m tournament_scheduler.cli.rvv_cli recovery-inject --source "SOURCE_NAME" [--work-dir .pipeline]
   ```
   On success (exit 0), the command prints `{"injected": N, "source": "...", "work_dir": "..."}` — mark this source as recovered.
4. If WebFetch returns no usable content or event extraction fails, log a warning for this source and continue with the next one. Do **not** abort the entire recovery loop on a single-source failure.

If any sources are blocked and `--non-strict` was not passed, stop and report which sources failed before continuing.

**Proceed/abort decision after the recovery loop:**
After attempting recovery for all problem sources:

1. Re-check recovery targets:
   ```bash
   python3 -m tournament_scheduler.cli.rvv_cli recovery-targets [--work-dir .pipeline]
   ```
2. Count remaining blocked/zero-event sources in the output:
   - **All recovered (empty array):** Proceed to Stage 3.
   - **Some still blocked/empty, but `--allow-missing-sources` is acceptable:** Proceed to Stage 3 with a warning listing the unrecovered sources and their URLs.
   - **Some still blocked/empty, and strict mode is required:** Abort. Report each unrecovered source by name and URL, state the reason (`blocked` or `zero_events`), and tell the user to check the URL manually or wait for the source to become available before re-running Stage 2.

If any sources are blocked and `--non-strict` was not passed, stop and report which sources failed before continuing.

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
python3 -m tournament_scheduler.pipeline.stage4_export [--work-dir .pipeline] [--export-dir export]
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
