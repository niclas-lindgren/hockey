# RVV Miniputt

📅 **Published season plan:** https://niclas-lindgren.github.io/hockey/latest/

RVV Miniputt is an **AI-operated season-planning system** for RVV hockey clubs.

The intended workflow is goal-oriented: a human supervisor asks an LLM harness to produce the best trustworthy season plan, and the AI operator validates inputs, gathers calendar data, recovers from routine problems, generates and evaluates plans, and exports the result. The human is involved when credentials, authorization, incomplete source data, or genuine hockey-policy decisions require judgment.

Underneath the operator experience is a deterministic, checkpointed four-stage pipeline that:

1. validates season input (`input.xlsx` workbook + roster data)
2. scrapes club calendars and caches results
3. builds a season plan
4. exports Excel, CSV, iCal, HTML, and Spond files

The current AI-operator direction, ordered implementation backlog, and operational ownership guidance are documented in:

- [AI operator product direction](docs/ai-operator-product-direction.md)
- [AI operator implementation roadmap](docs/ai-operator-roadmap.md)
- [AI operator run manifest schema](docs/run-manifest-schema.md)
- [Ownership and handover guide](docs/ownership-and-handover.md)

## Current operator workflow

For humans working outside an LLM harness, the root `Makefile` is the concise operator menu. Run `make help` to discover every deterministic or explicitly human-controlled operation. Each Make target is a thin wrapper over the canonical scripts/CLI commands; it does not reimplement planning, publishing, release, or safety logic.

Common Make targets and their direct equivalents:

| Workflow | Make target | Direct command |
|---|---|---|
| Full operator run | `make operator-run` | `scripts/rvv-miniputt operator run` |
| Forced operator rerun | `make operator-run-force` | `scripts/rvv-miniputt operator run --force` |
| Raw four-stage pipeline | `make run ARGS='--input input.xlsx'` | `scripts/rvv-miniputt run --input input.xlsx` |
| Status/log inspection | `make status`, `make logs` | `scripts/rvv-miniputt status`, `scripts/rvv-miniputt logs list` |
| Calendar report | `make calendars`, `make calendars-refresh` | `scripts/rvv-miniputt calendars`, `scripts/rvv-miniputt calendars --refresh` |
| Source health | `make sources-status` | `scripts/rvv-miniputt sources status` |
| Pending questions | `make questions`, `make questions-all` | `scripts/rvv-miniputt operator questions [--all]` |
| Record a decision | `make answer ID=<id> ANSWER='<answer>'` | `scripts/rvv-miniputt operator answer <id> '<answer>'` |
| Promote a decision | `make promote ID=<id> SCOPE=workspace` | `scripts/rvv-miniputt operator promote <id> workspace` |
| Publication preview | `make publish-preview` | `scripts/rvv-miniputt operator publish --dry-run` |
| Public publish | `make publish CONFIRM_PUBLIC=1` | `scripts/rvv-miniputt operator publish --confirm-public` |
| Publish verification/history | `make verify-publish`, `make publish-history` | `scripts/rvv-miniputt operator verify`, `scripts/rvv-miniputt operator publish-history` |
| Roll back latest | `make rollback RUN_ID=<id> CONFIRM_PUBLIC=1` | `scripts/rvv-miniputt operator rollback <id> --confirm-public` |
| Local verification | `make check` | `scripts/check` |
| Guarded release | `make release-dry-run TAG=vX.Y.Z`, `make release TAG=vX.Y.Z` | `scripts/release --dry-run vX.Y.Z`, `scripts/release vX.Y.Z` |

`ARGS='...'` is appended to the relevant underlying CLI command for normal option forwarding. Mutating targets retain explicit gates: `make publish` and `make rollback` require `CONFIRM_PUBLIC=1`, and release creation goes through `scripts/release` rather than raw `git tag`/`git push`. `make`, `make help`, `make run`, and `make operator-run` never publish publicly.

Browser-only operation is available through manual GitHub Actions workflows when a volunteer should not run local commands:

| Browser workflow | Purpose | Safety boundary |
|---|---|---|
| `Sesong: valider inndata` | Validate a workbook and upload input fingerprint, status, logs, manifest, and validation artifacts. | Read-only; never publishes. |
| `Sesong: lag vurderingspakke` | Generate a candidate plan/review bundle and upload HTML exports, logs, manifest, publish preview, and privacy report. | Read-only; never publishes. |
| `Sesong: publiser godkjent pakke` | Download an approved review artifact, verify the exact `bundle_fingerprint`, and publish through `operator publish --confirm-public`. | Requires the protected `pages-publication` environment plus `PUBLISER`. |
| `Sesong: rull tilbake publisering` | Restore `/latest/` to a prior immutable run. | Requires the protected `pages-publication` environment plus `RULL_TILBAKE`. |

Use these workflows from GitHub's **Actions** tab; they call the same `scripts/rvv-miniputt` operator commands as the Make targets and keep generation, approval, publication, and rollback separated.

LLM-harness-only conveniences such as `/rvv-miniputt guide`, extension-managed browser recovery, and agent-callable Pi tools are intentionally excluded from Make. Use the Pi/Claude/OpenCode/Codex adapters when that harness capability is required.

The goal-oriented entry point is `operator run`. It inspects workspace state, resumes from the earliest stage that is missing, incomplete, or stale, and reports a structured summary — no manual stage coordination required:

```bash
make operator-run
# direct equivalent:
scripts/rvv-miniputt operator run
# or
python3 -m tournament_scheduler.cli.rvv_cli operator run --objective "Produce the best trustworthy season plan"
```

Run it again after an interruption and it resumes automatically; run it again with nothing pending and it reports that the plan is already complete instead of redoing work. Pass `--force` to rerun everything from stage 1 regardless of state.

When something needs a human decision (missing credentials, incomplete source data, an ambiguous policy call), the operator raises a question instead of guessing:

```bash
rvv-miniputt operator questions                        # list what's blocking, with context and a recommendation
rvv-miniputt operator answer <id> "<answer>"            # record a durable decision
rvv-miniputt operator run                               # resume — the same question, in the same context, is never asked twice
rvv-miniputt operator promote <id> workspace             # turn a one-off answer into a standing policy decision
```

Decisions are scoped (run / input_version / season / workspace, see [`docs/run-manifest-schema.md`](docs/run-manifest-schema.md#decision-scoping-issue-12)) so an answer tied to one workbook doesn't get silently reused after a new one is uploaded — it's marked stale instead, and `operator questions --all` shows the full history.

Once an export looks good, publish it to a shareable GitHub Pages URL without running anything in GitHub Actions:

```bash
rvv-miniputt operator publish                           # preview: sanitizes, shows what would change, asks for approval
rvv-miniputt operator publish --confirm-public           # actually publish this exact bundle right now
rvv-miniputt operator run --publish                      # fold publishing into the run — still only previews, never auto-confirms
```

Before anything is written to `gh-pages`, the raw export is sanitized into a separate public bundle (see [issue #18](docs/ai-operator-roadmap.md#18-create-a-sanitized-public-pages-bundle-and-privacy-report)): the public HTML/ICS views plus the downloadable workbook/CSV exports are copied by default (while Spond exports and per-club review packets stay out), probable secrets block publication outright, local paths/contact info are redacted, and links inside included HTML that point at excluded files are disabled or removed. Inspect what would go public in `<work-dir>/pages_privacy_report.json`.

Publishing itself never happens just because `--publish` was passed somewhere upstream (see [issue #19](docs/ai-operator-roadmap.md#19-require-explicit-approval-before-public-pages-publication)): without `--confirm-public` on the exact invocation, `operator publish` only previews what would change under `/latest/` and raises a durable `external_publication` question tied to that exact bundle's content and target. Answer it once and reruns for the *same* bundle/target reuse that approval automatically; any change to the exported content (or the target repo/branch/run) needs a fresh approval:

```bash
rvv-miniputt operator questions                         # shows the pending publication approval, with the file diff
rvv-miniputt operator answer <id> "godkjenn"             # durable approval — the next 'operator publish' actually pushes
```

Publishing is idempotent per run and never force-pushes history. A successful push isn't the last word either (see [issue #20](docs/ai-operator-roadmap.md#20-verify-github-pages-publication-and-support-rollback)): `operator publish` polls the published URL afterward and reports `warning` instead of `ok` if the expected content isn't confirmed reachable within a bounded window. If a publish turns out to be bad, roll `/latest/` back to any previously published run without losing history:

```bash
rvv-miniputt operator verify                            # re-check the last publish is actually reachable
rvv-miniputt operator publish-history                   # list every publish/rollback on the Pages branch
rvv-miniputt operator rollback <run-id> --confirm-public # restore /latest/ to that run (immutable /runs/ untouched)
```

In Pi, start the workflow with:

```bash
/rvv-miniputt run
```

The portable pipeline stages and recovery commands remain available directly for debugging or advanced workflows:

```bash
scripts/rvv-miniputt run
# or
python3 -m tournament_scheduler.cli.rvv_cli run
```

Useful inspection and recovery commands include:

- `/rvv-miniputt status` or `scripts/rvv-miniputt status`
- `/rvv-miniputt logs` or `scripts/rvv-miniputt logs list`
- `/rvv-miniputt calendars` or `scripts/rvv-miniputt calendars`
- `/rvv-miniputt calendars --refresh` or `scripts/rvv-miniputt calendars --refresh`
- `scripts/rvv-miniputt sources status` — per-source health (reachability, event counts, cache age, suggested recovery actions)

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
- [AI operator run manifest schema](docs/run-manifest-schema.md)
- [Ownership and handover guide](docs/ownership-and-handover.md)
- [Pipeline guide](docs/rvv-miniputt-pipeline.md)
- [Rules report](docs/rvv-miniputt-rules-report.md)
- [Desktop app prototype](docs/desktop-app.md)
- [CI: required checks and branch protection](docs/ci.md)
- `./scripts/rules-report.sh` or `make rules-report` — regenerate the report and run sync tests
- [Kampveileder 3 mot 3](https://www.hockey.no/contentassets/9f67f790b75f4362a8bb2fb1524923fc/kampveileder-for-3-mot-3-spill---u7ju7---u11ju11.pdf)
