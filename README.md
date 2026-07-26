# RVV Miniputt

RVV Miniputt is an **AI-operated season-planning system** for RVV hockey clubs.

The intended workflow is goal-oriented: a human supervisor asks an LLM harness to produce the best trustworthy season plan, and the AI operator validates inputs, gathers calendar data, recovers from routine problems, generates and evaluates plans, and exports the result. The human is involved when credentials, authorization, incomplete source data, or genuine hockey-policy decisions require judgment.

Underneath the operator experience is a deterministic, checkpointed four-stage pipeline that:

1. validates season input (`input.xlsx` workbook + roster data)
2. scrapes club calendars and caches results
3. builds a season plan
4. exports Excel, CSV, iCal, HTML, and Spond files

The current AI-operator direction and ordered implementation backlog are documented in:

- [AI operator product direction](docs/ai-operator-product-direction.md)
- [AI operator implementation roadmap](docs/ai-operator-roadmap.md)

## Current operator workflow

The goal-oriented operator entry point is being developed. Today, LLM harnesses operate the existing portable pipeline and its recovery commands.

In Pi, start the workflow with:

```bash
/rvv-miniputt run
```

Outside Pi, including Codex, Claude Code, OpenCode, or a normal shell, use:

```bash
scripts/rvv-miniputt run
# or
python3 -m tournament_scheduler.cli.rvv_cli run
```

The operator should treat these commands as capabilities used to achieve the season-planning objective, rather than requiring the human to manually coordinate each pipeline stage.

Useful inspection and recovery commands include:

- `/rvv-miniputt status` or `scripts/rvv-miniputt status`
- `/rvv-miniputt logs` or `scripts/rvv-miniputt logs list`
- `/rvv-miniputt calendars` or `scripts/rvv-miniputt calendars`
- `/rvv-miniputt calendars --refresh` or `scripts/rvv-miniputt calendars --refresh`

## Product architecture

```text
Human supervisor
      |
      v
AI operator
      |
      +-- workbook and input validation
      +-- calendar collection and recovery
      +-- deterministic scheduling engine
      +-- plan evaluation and comparison
      +-- export and audit artifacts
```

Hard constraints and baseline scoring belong in deterministic, testable code. AI assistance may investigate failures, interpret evidence, compare alternatives, and recommend adjustments, but it should not be required to guarantee schedule validity.

Harness-specific adapters remain thin layers over the portable Python and CLI capabilities:

- Claude: `.claude/commands/rvv-miniputt/`
- OpenCode: `.opencode/commands/rvv-miniputt/`
- Codex: `.codex/commands/rvv-miniputt/` plus `CODEX.md`
- Pi: slash commands and agent-callable `rvv_miniputt_*` tools

## Desktop supervisor prototype

The Electron scaffold in `apps/desktop/` is now considered a possible future **supervisor console**, not a separate scheduling implementation.

It may eventually show operator progress, source health, pending questions, candidate comparisons, approvals, and generated artifacts while using the same underlying capabilities as the CLI and LLM harnesses.

See [`docs/desktop-app.md`](docs/desktop-app.md) for current development and packaging steps.

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

Run `sh scripts/install.sh --help` for installer options. The installer uses `requirements.txt` for runtime dependencies and installs the project in editable mode from `pyproject.toml`.

For Playwright browser binaries used by scraping:

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

## Inputs

Pipeline runs start from the standard Excel workbook `input.xlsx`.

See [the pipeline guide](docs/rvv-miniputt-pipeline.md) for workbook sheets, source formats, recovery flows, and examples.

Per-age-group participation targets can be set in the `Aldersgrupper` sheet with optional `deltakelser_per_lag_før_jul` and `deltakelser_per_lag_etter_jul` values. The English aliases `target_tournament_count_before_christmas` and `target_tournament_count_after_christmas` are also accepted.

## Outputs

A successful run writes exports under `export/` by default:

- `season_plan.xlsx`
- `season_plan.csv`
- `season_plan_overview.csv`
- `season_plan.ics`
- `season_plan.html`
- `season_plan_spond.xlsx`
- `calendars.html`

With `--timestamped-export`, exports are written to a timestamped subfolder for diffable runs.

## Advanced CLI and debugging commands

- `scripts/rvv-miniputt run` — run the complete pipeline
- `scripts/rvv-miniputt status` — inspect stage and checkpoint status
- `scripts/rvv-miniputt logs ...` — inspect structured run logs
- `scripts/rvv-miniputt calendars` — regenerate calendar HTML from cache
- `scripts/rvv-miniputt calendars --refresh` — refresh sources before rebuilding calendar HTML
- `rvv-miniputt recovery-inject` — inject recovered source data
- `rvv-miniputt scrape-merge` — normalize recovered Stage 2 data

The native `/rvv-miniputt guide` setup wizard remains Pi-specific.

## Secret scanning

Run locally with:

```bash
./scripts/secret-scan.sh
```

Or, with `gitleaks` installed:

```bash
gitleaks detect --source . --config .gitleaks.toml --redact
```

## More documentation

- [AI operator product direction](docs/ai-operator-product-direction.md)
- [AI operator implementation roadmap](docs/ai-operator-roadmap.md)
- [Pipeline guide](docs/rvv-miniputt-pipeline.md)
- [Rules report](docs/rvv-miniputt-rules-report.md)
- [Desktop app prototype](docs/desktop-app.md)
- `./scripts/rules-report.sh` or `make rules-report` — regenerate the report and run sync tests
- [Kampveileder 3 mot 3](https://www.hockey.no/contentassets/9f67f790b75f4362a8bb2fb1524923fc/kampveileder-for-3-mot-3-spill---u7ju7---u11ju11.pdf)
