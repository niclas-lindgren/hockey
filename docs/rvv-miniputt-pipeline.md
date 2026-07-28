# RVV Miniputt pipeline guide

## Overview

The season-planning workflow is checkpointed in `.pipeline/` and runs in four stages:

1. **Stage 1 — Config**: validate the standard `input.xlsx` workbook and expand the roster
2. **Stage 2 — Scraping**: fetch calendar events from all configured sources
3. **Stage 3 — Planning**: build the season plan
4. **Stage 4 — Export**: write Excel, CSV, iCal, HTML, and Spond outputs

The pipeline is designed so you can fix a blocked source, rerun the command, and keep working from the same work directory.

## Input workbook

`input.xlsx` is the standard pipeline input. `rvv-miniputt run` uses it by default:

```bash
rvv-miniputt run --input input.xlsx --export-dir export
```

Stage 1 imports the workbook sheets into the internal config dict and then runs the normal Norwegian-language validation.

### Required workbook sheets

- `Innstillinger` — scalar settings with columns `felt`, `verdi`
- `Lag` — team roster with columns `club`, `label`, `age_group`

### Optional workbook sheets

- `Aldersgrupper` — columns `age_group`, `parallel_games`, `round_length_minutes`, `deltakelser_per_lag_før_jul`, `deltakelser_per_lag_etter_jul`
- `Kilder` — columns `name`, `type`, `url`

### `Innstillinger` rows

Required rows:

- `start_date` — `YYYY-MM-DD`
- `end_date` — `YYYY-MM-DD`

Optional workbook data lives in the other sheets:

- `Aldersgrupper` kan i tillegg ha `deltakelser_per_lag_før_jul` og `deltakelser_per_lag_etter_jul` for per-age-group halvsesongmål.

### `Aldersgrupper` rows

Each row configures one age group:

- `age_group` — for example `U10` or `JU12`
- `parallel_games` — explicit number of simultaneous games
- `round_length_minutes` — optional override of round length

When present, the sheet's age groups are used for cross-checking against `Lag` and the age-group keyed fields.

### `Lag` rows

Each row configures one team:

- `club`
- `label`
- `age_group`

### `Kilder` rows

Each row configures one calendar source:

- `name`
- `type` — for example `outlook` or `ical`
- `url`

Empty rows are ignored.

## Calendar sources

Stage 2 supports multiple source types:

- `outlook` / `html` — Playwright-based browser scraping
- `ical` / `google` — HTTP/iCal scraping
- JS-heavy sites that fail deterministic scraping — use the Pi ScraperAgent (`.pi/lib/scraper-agent.ts`) or another browser-enabled harness for LLM-guided scraping. Holmen's Sportello calendar is the exception: it now has a deterministic GraphQL scraper and no longer depends on browser-only recovery. In a plain terminal, `scripts/rvv-miniputt scrape-llm` reports the browser-tool boundary for the remaining browser-only sources instead of pretending it can drive the page itself.

### Browser-capability boundary

`scripts/rvv-miniputt scrape-llm --club <name>` is a capability probe, not a guaranteed scraper. It can actually recover a source only in an environment that exposes browser control:

- Pi: the `rvv_miniputt_scrape_llm` extension tool / `/rvv-miniputt scrape-llm`
- Browser-enabled harnesses: Claude Code, OpenCode, Codex, or similar only when they have a Playwright/browser controller wired in
- Plain terminal or CI: no browser control; the command should immediately explain the missing capability and exit

If you only have a terminal, use the recovery bridge instead:

```bash
scripts/rvv-miniputt recovery-targets
# recover or prepare event JSON for the blocked source
python3 -m tournament_scheduler.cli.rvv_cli recovery-inject --source "<navn>" < recovered-events.json
scripts/rvv-miniputt scrape-merge
scripts/rvv-miniputt calendars
```

That flow is scriptable and does not require a live browser controller.

### BookUp credentials

Some BookUp calendars require authentication before scraping works.
For those sources, set the credentials expected by the configured strategy, typically:

- `BOOKUP_EMAIL`
- `BOOKUP_PASSWORD`

With credentials in place, Stage 2 can scrape the source and cache the events.

### Sparse event-count warnings

Stage 2 now adds a non-blocking `event_expectation` object to each source in
`.pipeline/stage2_scraping.json`. The estimate is derived from the scrape date
range and active age groups, and is meant as a coarse lower-bound sanity check.
If a source returns events but far fewer than expected, Stage 2 records it in the
top-level `event_expectation_warnings` list and `rvv-miniputt status` prints a
"Mistenkelig få kalenderhendelser" summary.

This is different from a blocked source: the pipeline may continue, but the
source should be prioritized for recovery or manual review before trusting the
plan. Typical example: a club calendar returning 2-3 events for a full season
when the date range and age-group setup suggest roughly 16+ bookings.

## Outputs

A normal run can produce:

- `season_plan.xlsx`
- `season_plan.csv`
- `season_plan_overview.csv`
- `season_plan.ics`
- `season_plan.html`
- `season_plan_spond.xlsx`
- `calendars.html`

With `--timestamped-export`, the same files are written into a timestamped subdirectory under `export/`.

## Operator flows

### Cross-harness entrypoints

Use whichever entrypoint your harness supports:

```bash
# Portable, repo-local launcher
scripts/rvv-miniputt status
scripts/rvv-miniputt run --resume-from 2 --log-level verbose

# Direct Python CLI
python3 -m tournament_scheduler.cli.rvv_cli logs list --count 5
```

In Pi, the slash commands remain available and map onto the same repo workflow surface where possible:

```bash
/rvv-miniputt status
/rvv-miniputt logs show latest
/rvv-miniputt run --resume-from 2 --log-level verbose
```

Pi-only features remain the interactive guide and extension-managed tool wrappers (`rvv_miniputt_run`, `rvv_miniputt_status`, etc.).

### Full run

```bash
rvv-miniputt run --input input.xlsx --export-dir export
```

Useful flags:

- `--non-strict` — continue past some stage failures
- `--allow-missing-sources` — keep partial Stage 2 results and continue
- `--iterations N` — run the Stage 3 planner with multiple random seeds and keep the best plan for that Stage 3 attempt
- `--mid-planning-critic-iterations N` — opt into a pre-export critic loop after Stage 3 and before Stage 4; the loop inspects `.pipeline/stage3_planning.json`, stores structured `planning_critic_hints`, reruns Stage 3 with numeric penalty hints from those findings, and repeats up to `N` times before export
- `--timestamped-export` — write diffable exports into a timestamped folder only

### Pre-export planning critic vs post-export refinement

`--mid-planning-critic-iterations N` runs before any Stage 4 artifacts exist. It is checkpoint-driven: the pipeline reads the Stage 3 plan, asks the deterministic plan critic/fairness metrics for issues, persists the structured hint payload in the next Stage 3 checkpoint as `planning_critic_hints`, and reruns Stage 3 with the extracted numeric `penalty_hints` baked into the config. Default is `0`, so existing runs are unchanged.

This is separate from the post-Stage-4 refinement loop. Post-export refinement starts only after export, applies targeted manual-adjustment moves to an already materialized plan, and may re-export improved artifacts. The mid-planning loop instead tries to improve the planner search before export and does not create or patch export files by itself.

### Rebuild calendar HTML

```bash
rvv-miniputt calendars
rvv-miniputt calendars --refresh
```

### Inspect progress

In Pi, use the slash commands:

- `/rvv-miniputt status`
- `/rvv-miniputt logs`

Outside Pi, use the portable equivalents:

- `scripts/rvv-miniputt status`
- `scripts/rvv-miniputt logs list`

Run logs (`run-*.jsonl`) live in the export tree alongside the exported artifacts; `.pipeline/logs/` is only a legacy fallback when no export folder exists yet.

When stages are invoked individually rather than through `rvv-miniputt run`/`operator run` — e.g. an agent following the stage-by-stage flow in `run.md` — no `pipeline_run_*.log` gets written, since that file is only produced by the single-process `operator run` orchestration. Each of the four stage scripts instead appends one line per invocation to `stage_run.log`, using the same location resolution as the JSONL run logs above (export tree once Stage 4 has run, `.pipeline/logs/` before that). It is the only debugging trail for a stage-by-stage session, so check it there before assuming a run left no record.

### Recover from blocked sources

Typical recovery loop for a blocked JS-only source:

1. fix `input.xlsx` or source credentials
2. rerun `rvv-miniputt run`
3. if a JS source is still blocked, use Pi, Claude Code, Codex, or OpenCode for LLM-driven scraping; in a plain terminal, first run `scripts/rvv-miniputt recovery-targets` to confirm the blocked source, then gather event JSON with WebFetch or your own script
4. inject the recovered events into the cache with `python3 -m tournament_scheduler.cli.rvv_cli recovery-inject --source "<navn>" < recovered-events.json`
5. normalize the Stage 2 checkpoint with `scripts/rvv-miniputt scrape-merge`
6. rebuild calendars with `scripts/rvv-miniputt calendars`

Holmen's Sportello calendar now uses the deterministic GraphQL scraper, so it should not need this browser-only recovery path.

## Headless / CI usage

For cron jobs or CI pipelines, configure a headless judge backend so inter-stage judgment still runs.

Set `RVV_JUDGE_BACKEND` before running the pipeline:

```bash
# Use the Anthropic Claude API as the judge
export RVV_JUDGE_BACKEND=claude
export ANTHROPIC_API_KEY=sk-ant-...
scripts/rvv-miniputt run --input input.xlsx --export-dir export

# Use the OpenAI API as the judge
export RVV_JUDGE_BACKEND=openai
export OPENAI_API_KEY=sk-...
scripts/rvv-miniputt run --input input.xlsx --export-dir export

# Use a locally-running LLM via LM Studio / llm-bridge (no API key required)
export RVV_JUDGE_BACKEND=llm_bridge
scripts/rvv-miniputt run --input input.xlsx --export-dir export
```

If `RVV_JUDGE_BACKEND` is not set, the pipeline logs a warning and continues.

### Required environment variables per backend

| `RVV_JUDGE_BACKEND` | Required env var | Notes |
|---------------------|-----------------|-------|
| `claude`            | `ANTHROPIC_API_KEY` | Uses Anthropic Messages API |
| `openai`            | `OPENAI_API_KEY`    | Uses OpenAI Chat Completions API |
| `llm_bridge`        | — | Requires LM Studio running at `host.lima.internal:1234` |

## Notes

- The scheduler is season-based, not a single-tournament planner.
- Stage checkpoints live in `.pipeline/` and make reruns idempotent where possible.
- HTML reports and Spond export are part of the standard Stage 4 output.
