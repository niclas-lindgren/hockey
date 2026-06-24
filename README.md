# RVV Miniputt

RVV Miniputt is the season-planning and calendar-scraping pipeline for RVV hockey clubs.
It runs a four-stage workflow that:

1. validates season input (`input.xlsx` workbook + roster data)
2. scrapes club calendars and caches results
3. builds a season plan
4. exports Excel, CSV, iCal, HTML, and Spond files

## Desktop app prototype

For non-technical users, the repo now has an Electron desktop-app scaffold in `apps/desktop/`.
It launches a bundled/local Python backend, stores credentials/API keys through the OS keychain when available, runs the existing RVV Miniputt pipeline, and shows logs/results in a normal app window.

See [`docs/desktop-app.md`](docs/desktop-app.md) for development and packaging steps.

## Installation

Prerequisites:
- Python 3.10+
- `python3 -m venv`
- access to `pip`

Fast path on macOS/Linux:

```sh
git clone <repo-url>
cd hockey
make install
# or
sh scripts/install.sh
```

Run `sh scripts/install.sh --help` for installer options.
The installer uses `requirements.txt` for runtime dependencies and installs the project in editable mode from `pyproject.toml`.
If you need the Playwright browser binaries for scraping, run:

```sh
INSTALL_PLAYWRIGHT=1 make install
# or
INSTALL_PLAYWRIGHT=1 sh scripts/install.sh
```

Manual install:

```sh
python3 -m venv venv
venv/bin/python3 -m pip install --upgrade pip setuptools wheel
venv/bin/python3 -m pip install -r requirements.txt
venv/bin/python3 -m pip install -e .
```

## Quick start

In Pi, start the workflow with:

```bash
/rvv-miniputt run
```

Outside Pi (Codex/Claude/OpenCode/shell), use the repo-local launcher or Python CLI:

```bash
scripts/rvv-miniputt run
# or
python3 -m tournament_scheduler.cli.rvv_cli run
```

Useful follow-up commands in either mode:

- `/rvv-miniputt calendars` in Pi, or `scripts/rvv-miniputt calendars` elsewhere
- `/rvv-miniputt logs` in Pi, or `scripts/rvv-miniputt logs list` elsewhere
- `/rvv-miniputt status` in Pi, or `scripts/rvv-miniputt status` elsewhere

Project-local command adapters are also included for:
- Claude: `.claude/commands/rvv-miniputt/` → `/rvv-miniputt:run`, `/rvv-miniputt:status`, ...
- OpenCode: `.opencode/commands/rvv-miniputt/` → `/rvv-miniputt:run`, `/rvv-miniputt:status`, ...
- Codex: `.codex/commands/rvv-miniputt/` plus `CODEX.md` guidance

## Current commands

- `/rvv-miniputt run` / `scripts/rvv-miniputt run` — run the full pipeline
- `/rvv-miniputt calendars` / `scripts/rvv-miniputt calendars` — regenerate calendar HTML from cache
- `/rvv-miniputt calendars --refresh` / `scripts/rvv-miniputt calendars --refresh` — force a fresh scrape first
- `/rvv-miniputt logs` / `scripts/rvv-miniputt logs ...` — show structured pipeline logs
- `/rvv-miniputt status` / `scripts/rvv-miniputt status` — show stage status
- `/rvv-miniputt guide` — interactive wizard for setup and first run (Pi-only)

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

Set per-age-group participation targets in the workbook `Aldersgrupper` sheet with optional `deltakelser_per_lag_før_jul` / `deltakelser_per_lag_etter_jul` split values.
The English aliases `target_tournament_count_before_christmas` and `target_tournament_count_after_christmas` are also accepted.

## Secret scanning

Run locally with:

```bash
./scripts/secret-scan.sh
```

Or, if you have `gitleaks` installed:

```bash
gitleaks detect --source . --config .gitleaks.toml --redact
```

## Cross-harness usage

- **Portable / harness-neutral:** `scripts/rvv-miniputt ...` and `python3 -m tournament_scheduler.cli.rvv_cli ...` work from Codex, Claude, OpenCode, or a normal shell.
- **Project command adapters:** `.claude/commands/rvv-miniputt/`, `.opencode/commands/rvv-miniputt/`, and `.codex/commands/rvv-miniputt/` provide local command wrappers around the portable repo entrypoints.
- **Pi adapter layer:** `/rvv-miniputt ...` slash commands and agent-callable `rvv_miniputt_*` tools are Pi conveniences layered on top of the repo workflows.
  The Pi run path now performs bounded convergence rounds: it re-runs from the earliest still-problematic stage until the output looks good or the retry cap is reached.
- **Still Pi-specific:** the native `/rvv-miniputt guide` extension UX, live slash-command notifications, and the extension-managed `rvv_miniputt_*` tool registrations.

## More documentation

- [Pipeline guide](docs/rvv-miniputt-pipeline.md)
- [Rules report](docs/rvv-miniputt-rules-report.md)
- `./scripts/rules-report.sh` or `make rules-report` — regenerate the report and run the sync tests
- [Kampveileder 3 mot 3](https://www.hockey.no/contentassets/9f67f790b75f4362a8bb2fb1524923fc/kampveileder-for-3-mot-3-spill---u7ju7---u11ju11.pdf)