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

Optional rows:

- `deltakelser_per_lag` — mykt mål for antall turneringsdeltakelser per lag (standard 6).
  Internt lagret som `target_tournament_count`. Det gamle feltnavnet `target_tournament_count`
  fungerer fortsatt i `Innstillinger`-arket for bakoverkompatibilitet.
- `Aldersgrupper` kan i tillegg ha `deltakelser_per_lag_før_jul` og `deltakelser_per_lag_etter_jul` for per-age-group halvsesongmål.

### `Aldersgrupper` rows

Each row configures one age group:

- `age_group` — for example `U10` or `JU12`
- `parallel_games` — federation-limited number of simultaneous games
- `round_length_minutes` — optional override of default round length

### `Lag` rows

Each row configures one team:

- `club`
- `label`
- `age_group`
- `region` (optional) — preserved roster metadata for cross-region teams and reporting
- `skill_level` (optional) — 1-10 planning hint used when selecting participants

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
- JS-heavy sites that fail deterministic scraping — can be retried with `rvv-miniputt scrape-llm`

### BookUp credentials

Some BookUp calendars require authentication before scraping works.
For those sources, set the credentials expected by the configured strategy, typically:

- `BOOKUP_EMAIL`
- `BOOKUP_PASSWORD`

If credentials are missing, Stage 2 reports a blocked source instead of silently returning zero events.

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
- `--timestamped-export` — write diffable exports into a timestamped folder only

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

The pipeline also stores per-run logs in `.pipeline/logs/`.

### Recover from blocked sources

Typical recovery loop:

1. fix `input.xlsx` or source credentials
2. rerun `rvv-miniputt run`
3. if a JS source is still blocked, try `rvv-miniputt scrape-llm --club NAME`
4. rebuild calendars with `rvv-miniputt calendars`

## Headless / CI usage

When the pipeline runs without an active harness session (for example in a cron job or CI
pipeline), the in-session LLM judge is not available. A headless judge backend can be
configured instead so that inter-stage judgment still happens.

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

If `RVV_JUDGE_BACKEND` is not set and no harness session is detected, the pipeline
skips inter-stage judgment and logs a warning instead of failing.

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
