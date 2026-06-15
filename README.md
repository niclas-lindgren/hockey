# RVV Miniputt

RVV Miniputt is the season-planning and calendar-scraping pipeline for RVV hockey clubs.
It replaces the older single-tournament workflow with a four-stage pipeline that:

1. validates season input (`input.json` or workbook input + roster data)
2. scrapes club calendars and caches results
3. builds a season plan
4. exports Excel, CSV, iCal, HTML, and Spond files

## Quick start

```bash
rvv-miniputt run --input input.json --export-dir export
# or: rvv-miniputt run --input input.xlsx --export-dir export
```

If you use the Pi extension, the matching slash commands are:

- `/rvv-miniputt run`
- `/rvv-miniputt calendars`
- `/rvv-miniputt logs`
- `/rvv-miniputt status`

## Current commands

- `rvv-miniputt run` — full pipeline run
- `rvv-miniputt calendars` — regenerate calendar HTML from cache
- `rvv-miniputt calendars --refresh` — force a fresh scrape first
- `rvv-miniputt scrape --club NAME` — scrape one calendar source for troubleshooting
- `rvv-miniputt scrape-llm --club NAME` — use the LLM-guided browser scraper for blocked JS-heavy sources
- `rvv-miniputt logs` — show pipeline logs
- `rvv-miniputt cancel` / `replan` — cancel or move an existing tournament
- `rvv-miniputt tournament ...` — list/add/remove/cancel tournaments in the plan

## Inputs

Pipeline runs start from `input.json` (canonical JSON) or an Excel workbook that maps into the same schema.
See `docs/rvv-miniputt-pipeline.md` for the full schema, source formats, and examples. See `docs/rvv-miniputt-input-formats.md` for the JSON vs CSV vs Excel recommendation.

## Outputs

A successful run writes exports under `export/` by default:

- `season_plan.xlsx`
- `season_plan.csv` + `season_plan_overview.csv`
- `season_plan.ics`
- `season_plan.html`
- `season_plan_spond.xlsx`
- `calendars.html`

With `--timestamped-export`, exports are written to a timestamped subfolder for diffable runs.

Set `target_tournament_count` in `input.json` (or the workbook `Innstillinger` sheet) to tune the soft per-team tournament-participation target (default: 6).

## More documentation

- [Pipeline guide](docs/rvv-miniputt-pipeline.md)
