# RVV Miniputt

RVV Miniputt is the season-planning and calendar-scraping pipeline for RVV hockey clubs.
It runs a four-stage workflow that:

1. validates season input (`input.xlsx` workbook + roster data)
2. scrapes club calendars and caches results
3. builds a season plan
4. exports Excel, CSV, iCal, HTML, and Spond files

## Quick start

Activate the skill with:

```bash
/rvv-miniputt run
```

That starts the full pipeline. Useful follow-up commands:

- `/rvv-miniputt calendars`
- `/rvv-miniputt logs`
- `/rvv-miniputt status`

## Current commands

- `/rvv-miniputt run` — run the full pipeline
- `/rvv-miniputt calendars` — regenerate calendar HTML from cache
- `/rvv-miniputt calendars --refresh` — force a fresh scrape first
- `/rvv-miniputt logs` — show pipeline logs
- `/rvv-miniputt status` — show stage status
- `/rvv-miniputt guide` — interactive wizard for setup and first run

## Inputs

Pipeline runs start from the standard Excel workbook `input.xlsx`.
See `docs/rvv-miniputt-pipeline.md` for the workbook sheets, source formats, and examples.

## Outputs

A successful run writes exports under `export/` by default:

- `season_plan.xlsx`
- `season_plan.csv` + `season_plan_overview.csv`
- `season_plan.ics`
- `season_plan.html`
- `season_plan_spond.xlsx`
- `calendars.html`

With `--timestamped-export`, exports are written to a timestamped subfolder for diffable runs.

Set `deltakelser_per_lag` in the workbook `Innstillinger` sheet to tune the soft per-team tournament-participation target (default: 6).
The legacy key `target_tournament_count` also works for backward compatibility.

## Secret scanning

Run locally with:

```bash
./scripts/secret-scan.sh
```

Or, if you have `gitleaks` installed:

```bash
gitleaks detect --source . --config .gitleaks.toml --redact
```

## More documentation

- [Pipeline guide](docs/rvv-miniputt-pipeline.md)
- [Rules report](docs/rvv-miniputt-rules-report.md)
