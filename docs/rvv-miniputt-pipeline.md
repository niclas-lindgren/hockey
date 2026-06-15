# RVV Miniputt pipeline guide

## Overview

The season-planning workflow is checkpointed in `.pipeline/` and runs in four stages:

1. **Stage 1 — Config**: validate `input.json` or a workbook input and expand the roster
2. **Stage 2 — Scraping**: fetch calendar events from all configured sources
3. **Stage 3 — Planning**: build the season plan
4. **Stage 4 — Export**: write Excel, CSV, iCal, HTML, and Spond outputs

The pipeline is designed so you can fix a blocked source, rerun the command, and keep working from the same work directory.

## Input file

`input.json` is the canonical pipeline input and interchange format. For organizer editing, `--input` can also point to an `.xlsx` workbook that Stage 1 imports into the same JSON-shaped schema before validation.

Required fields:

- `start_date` — `YYYY-MM-DD`
- `end_date` — `YYYY-MM-DD`
- `teams` — either an inline list of teams or a path to a roster file

Optional fields:

- `age_groups`
- `parallel_games`
- `round_length_minutes`
- `sources`

Example:

```json
{
  "start_date": "2025-09-01",
  "end_date": "2025-12-15",
  "age_groups": ["U10", "U12"],
  "parallel_games": {"U10": 3, "U12": 2},
  "round_length_minutes": {"U10": 10, "U12": 12},
  "teams": [
    {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
    {"club": "Skien", "label": "Skien U10A", "age_group": "U10"}
  ],
  "sources": [
    {
      "name": "Kongsberg ishall",
      "type": "outlook",
      "url": "https://kongsberghallen.no/webkalender/ishall/"
    }
  ]
}
```

### Excel workbook input

A workbook input uses these sheets:

- `Innstillinger` — columns `felt` and `verdi` for `start_date`, `end_date`, and `target_tournament_count`.
- `Aldersgrupper` — columns `age_group`, `parallel_games`, and optional `round_length_minutes`.
- `Lag` — columns `club`, `label`, and `age_group`.
- `Kilder` — columns `name`, `type`, and `url`.

Run it the same way as JSON:

```bash
rvv-miniputt run --input input.xlsx --export-dir export
```

See `docs/rvv-miniputt-input-formats.md` for why Excel is supported as an editor-friendly supplement while JSON remains canonical.

### Roster files

If `teams` is a string in JSON, it should point to a JSON/YAML roster file. Each team entry needs:

- `club`
- `label`
- `age_group`

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

### Full run

```bash
rvv-miniputt run --input input.json --export-dir export
```

Useful flags:

- `--non-strict` — continue past some stage failures
- `--allow-missing-sources` — keep partial Stage 2 results and continue
- `--timestamped-export` — write diffable exports into a timestamped folder only
- `target_tournament_count` — soft per-team tournament-participation target in `input.json` or workbook settings (default: 6)

### Rebuild calendar HTML

```bash
rvv-miniputt calendars
rvv-miniputt calendars --refresh
```

### Inspect progress

In Pi, use the slash commands:

- `/rvv-miniputt status`
- `/rvv-miniputt logs`

The pipeline also stores per-run logs in `.pipeline/logs/`.

### Recover from blocked sources

Typical recovery loop:

1. fix `input.json`, workbook input, or source credentials
2. rerun `rvv-miniputt run`
3. if a JS source is still blocked, try `rvv-miniputt scrape-llm --club NAME`
4. rebuild calendars with `rvv-miniputt calendars`

## Notes

- The scheduler is season-based, not a single-tournament planner.
- Stage checkpoints live in `.pipeline/` and make reruns idempotent where possible.
- HTML reports and Spond export are part of the standard Stage 4 output.
