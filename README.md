# RVV Miniputt

**Public season overview:** https://niclas-lindgren.github.io/hockey/latest/

RVV Miniputt is the operational and technical system used to collect team registrations, maintain the activity calendar, generate the miniputt season plan, review the result, and publish approved information for Region Viken Vest.

The project is not only a scheduling program. Its complete operating model spans:

- Microsoft Forms for club submissions
- Power Automate for validation and routing
- SharePoint Lists and files for reviewed operational data
- `input.xlsx` as the controlled planning input
- deterministic Python scheduling and export code
- GitHub Actions and local Make commands
- GitHub Pages for generated public views
- WordPress for the public website and navigation
- Spond for communication and event distribution

This README is the starting point for a new season coordinator or technical maintainer. Detailed implementation documentation remains under [`docs/`](docs/).

## Core principles

1. **SharePoint is the reviewed registration store.** Microsoft Forms is an intake channel, not the planning source of truth.
2. **`input.xlsx` is the controlled input to the season planner.** Form responses must not replace administrative sheets or planning settings directly.
3. **Generated files are not edited manually.** Correct the source data or code, then regenerate.
4. **Generation, review, publication, and rollback are separate actions.** Public publication always requires explicit approval.
5. **Only public-safe fields are published.** Contact details, comments, internal statuses, credentials, paths, and audit data stay private.
6. **The system must be transferable.** Critical Microsoft 365, GitHub, WordPress, and Spond assets should have club-controlled ownership and at least one backup owner.

## End-to-end operating model

```text
Club representative
        |
        v
Microsoft Form
        |
        v
Power Automate
  - validate registration code
  - normalize submitted data
  - reject or route invalid submissions
  - write accepted data to SharePoint
  - notify the responsible team/channel
        |
        v
Reviewed SharePoint List
        |
        +------------------------------+
        |                              |
        v                              v
Public "Påmeldte lag" export     Controlled planning import
                                      |
                                      v
                                  input.xlsx
                                      |
                                      v
                          Four-stage planning pipeline
                          1. validate configuration
                          2. collect calendar data
                          3. generate season plan
                          4. create review/public exports
                                      |
                                      v
                              Human review and approval
                                      |
                       +--------------+---------------+
                       |                              |
                       v                              v
                 GitHub Pages                     Spond import
                       |
                       v
                WordPress links/iframes
```

## Responsibilities by system

| System | Purpose | Source-of-truth status | Important boundary |
|---|---|---|---|
| Microsoft Forms | Collect club and team submissions | No | Treat responses as unreviewed input. |
| Power Automate | Validate and route form responses | No | Invalid registration codes must not create accepted registration records. |
| SharePoint List | Store reviewed registrations and workflow status | Yes, for registrations | Keep contact and internal workflow fields private. |
| `input.xlsx` | Controlled season-planning configuration | Yes, for planner input | Only the `Lag` sheet is rebuilt from approved registrations. |
| Calendar sources | Supply availability and activity data | Yes, per external source | Review stale or suspiciously sparse sources before trusting a plan. |
| Python pipeline | Validate, schedule, evaluate, and export | Derived | Do not put policy or hard constraints only in an LLM prompt. |
| GitHub Pages | Serve generated read-only output | No | Never manually edit generated Pages files. |
| WordPress | Public navigation and explanatory content | Yes, for editorial website text | Link/embed generated output instead of duplicating it manually. |
| Spond | Operational communication and event distribution | Yes, for group communication | Import only after the season plan is approved. |

## Annual season workflow

### 1. Before registration opens

- Confirm Microsoft Form ownership, questions, registration code, confirmation text, and destination flow.
- Confirm the Power Automate flow and all Microsoft 365 connections have club-controlled owners and a backup owner.
- Verify the SharePoint List schema and remove obsolete test rows.
- Update `input.xlsx` administrative sheets: `Innstillinger`, `Aldersgrupper`, `Kilder`, and optional `Datopreferanser`/activity sheets.
- Review GitHub, Pages, WordPress, Spond, and calendar-source access.
- Run `make check` and a dry planning run before clubs start submitting.

### 2. During registration

- Clubs submit one or more teams through Microsoft Forms.
- Power Automate validates the submitted registration code before treating the submission as accepted.
- Accepted submissions are normalized and written to the private SharePoint List.
- Rejected, duplicate, incomplete, or withdrawn registrations retain an explicit non-active status and are excluded from planning.
- The season coordinator reviews club name, team label, age group, duplicates, and status.
- Publish the standalone **Påmeldte lag** view when a refreshed public overview is needed; this does not require regenerating the season plan.

### 3. Freeze and import registrations

Export the reviewed SharePoint List as CSV or XLSX. Validate it before changing the planning workbook:

```bash
scripts/rvv-miniputt registrations validate registrations.csv --input input.xlsx
scripts/rvv-miniputt registrations export registrations.csv --input input.xlsx --output input.updated.xlsx --dry-run
scripts/rvv-miniputt registrations export registrations.csv --input input.xlsx --output input.updated.xlsx
```

The import:

- includes only approved/current/active registrations
- replaces only the `Lag` sheet
- preserves all controlled administrative sheets
- rejects unknown clubs, age groups, duplicate IDs, and duplicate teams
- excludes contact/comment fields
- writes an audit sidecar containing the source fingerprint and included SharePoint item IDs

Review `input.updated.xlsx`, then deliberately promote it to the active `input.xlsx` through the normal repository process.

### 4. Update activities and source calendars

Activity information belongs in a supported workbook sheet such as `Aktiviteter`, `Aktivitetsplan`, or `Årshjul`. The export can generate:

- `activities.json`
- `activities/index.html`

Keep these fields structured where possible: date, age group, category, title, location, description, and URL. Dates for player-development gatherings and regional gatherings may change; WordPress should state this editorially. Tournament and championship dates should be published when confirmed.

Calendar source definitions belong in the `Kilder` sheet. Before planning, inspect source health:

```bash
make sources-status
make calendars
# Force a refresh when required:
make calendars-refresh
```

A source returning very few events may not be technically blocked but can still be untrustworthy. Investigate sparse-event warnings before approval.

### 5. Generate and review the season plan

The normal human entry point is the root Makefile:

```bash
make help
make operator-run
make status
make logs
```

The deterministic pipeline has four checkpointed stages:

1. validate `input.xlsx`
2. collect and cache calendar events
3. generate and evaluate a season plan
4. export Excel, CSV, iCal, HTML, report, activity, input overview, and Spond files

A resumed run starts from the earliest missing or stale stage. Force a complete rebuild only when required:

```bash
make operator-run-force
```

Review at least:

- validation errors and warnings
- source health and missing/sparse calendars
- hosting distribution
- team participation counts before and after Christmas
- date conflicts and known activities
- generated HTML report and workbook
- public privacy report
- pending operator questions

Human hockey-policy decisions must be answered explicitly rather than guessed:

```bash
make questions
make answer ID=<id> ANSWER='<answer>'
make operator-run
```

### 6. Publish approved output

Preview publication first:

```bash
make publish-preview
```

Only publish the exact reviewed bundle:

```bash
make publish CONFIRM_PUBLIC=1
make verify-publish
```

Publication sanitizes a separate public bundle, blocks probable secrets, removes or disables links to excluded private files, and updates `/latest/` without force-pushing history.

Useful public paths include:

- main overview: `https://niclas-lindgren.github.io/hockey/latest/`
- registered teams: `https://niclas-lindgren.github.io/hockey/latest/registered-teams/pameldte-lag.html`
- activity calendar: normally under the generated `activities/` path in the latest bundle

WordPress should link to or iframe these generated views. Do not paste generated tables into WordPress unless there is a deliberate editorial reason, because copied data becomes stale.

### 7. Distribute through Spond

The pipeline creates Spond-oriented exports such as `season_plan_spond.xlsx`. Import or recreate events only after approval. Keep at least one backup Spond administrator, and document how to remove or correct imported events if a rollback is needed.

### 8. Handle mid-season changes

For a late registration, withdrawal, changed activity, or calendar correction:

1. update and review the authoritative source
2. export/rebuild `input.xlsx` if team registrations changed
3. regenerate the affected outputs
4. review the diff and privacy report
5. publish with explicit confirmation
6. update Spond and WordPress only where necessary
7. communicate the change through the established Spond group

Never patch the generated HTML, CSV, Excel, Pages branch, or Spond import file by hand as the permanent fix.

### 9. End of season

- Keep the immutable published run/history needed for audit and rollback.
- Archive the final approved workbook and reviewed registration export in club-controlled storage.
- Export a backup of the Microsoft Form and Power Automate solution where supported.
- Review owner/admin lists and remove departed volunteers.
- Rotate credentials and update the private ownership record.
- Create the next season from controlled templates rather than copying unknown local files.

## Registration and Power Automate runbook

The repository cannot inspect or version the live Power Automate flow, so the following behavior is an operational contract that must be checked in Microsoft 365 after changes.

### Expected flow

1. Trigger when a new Microsoft Forms response is submitted.
2. Retrieve the full response details.
3. Normalize the submitted registration code and compare it with the configured valid value.
4. When invalid:
   - do not create an accepted SharePoint registration item
   - optionally notify the submitter or internal coordinator without exposing the valid code
   - terminate the accepted-registration branch
5. When valid:
   - parse one or more submitted team lines
   - create one SharePoint item per team, or a consistently structured item that the export tooling supports
   - populate club, label, age group, workflow status, response ID, and audit timestamps
   - keep contact details and comments in private fields only
   - notify the responsible Teams channel or mailbox
6. A coordinator reviews the records and changes status to an accepted or rejected vocabulary supported by the importer.

### SharePoint fields needed by the repository

The reviewed export must resolve these canonical values:

| Canonical field | Typical source names | Requirement |
|---|---|---|
| `sharepoint_id` | `ID`, `SharePoint ID`, `Item ID`, `list_item_id` | Stable and unique |
| `club` | `Klubb`, `Forening`, `club` | Must exist in controlled workbook data |
| `label` | `Lag`, `Lagnavn`, `team_name`, `label` | Unique within its age group |
| `age_group` | `Aldergruppe`, `klasse`, `age group` | Must be declared when `Aldersgrupper` exists |
| `status` | `Status`, `Godkjenningsstatus`, `approval_state` | Determines inclusion |

Accepted active statuses include `approved`, `current`, `active`, `accepted`, `godkjent`, `aktiv`, and `gjeldende`. Rejected statuses include `rejected`, `withdrawn`, `duplicate`, `incomplete`, `avvist`, `trukket`, `duplikat`, and `ufullstendig`.

### Power Automate handover checklist

- [ ] Flow is owned by a club Microsoft 365 group, solution, or service account rather than only a personal account.
- [ ] At least one backup co-owner can edit and repair it.
- [ ] Form, SharePoint, Teams, and notification connections are documented privately.
- [ ] Invalid registration codes cannot reach the accepted SharePoint branch.
- [ ] The valid code is not printed in public help text, error messages, logs, or notifications.
- [ ] Multiple team lines are parsed deterministically and errors are visible.
- [ ] Duplicate retries do not silently create duplicate active teams.
- [ ] SharePoint item IDs and Forms response IDs are retained for audit.
- [ ] Contact details cannot leak into public CSV, JSON, HTML, GitHub artifacts, or Pages.
- [ ] The flow or solution is exported after major changes and before handover.

## Standalone registered-team publication

A reviewed SharePoint export can update the public team list without changing `input.xlsx` or regenerating season/activity output:

```bash
make registered-teams CSV=downloads/Miniputt-26-27.csv
make registered-teams-publish CSV=downloads/Miniputt-26-27.csv CONFIRM_PUBLIC=1
```

This writes review artifacts under `registered-teams/`, stages them on top of the current `/latest/` Pages snapshot, and preserves unrelated published files. Extra contact, ID, status, and comment columns are ignored in the public output.

## Browser-only GitHub workflow

Volunteers who should not run local commands can use manual workflows under **GitHub → Actions**:

| Workflow | Purpose | Public write? |
|---|---|---|
| `Sesong: valider inndata` | Validate workbook and upload evidence | No |
| `Sesong: lag vurderingspakke` | Generate a candidate review bundle and publish preview | No |
| `Sesong: publiser godkjent pakke` | Publish an exact reviewed artifact and fingerprint | Yes, through protected environment |
| `Sesong: rull tilbake publisering` | Restore `/latest/` to a prior published run | Yes, through protected environment |

Generation and publication must remain separate. The review workflow must never contain a hidden public confirmation.

## Common commands

| Task | Command |
|---|---|
| Show available operations | `make help` |
| Install locked dependencies | `make install` |
| Run canonical checks | `make check` |
| Full resumable operator run | `make operator-run` |
| Force complete rerun | `make operator-run-force` |
| Raw four-stage run | `make run ARGS='--input input.xlsx'` |
| Inspect status/logs | `make status`, `make logs` |
| Inspect/refresh calendars | `make calendars`, `make calendars-refresh` |
| Inspect source health | `make sources-status` |
| List/answer questions | `make questions`, `make answer ID=<id> ANSWER='<answer>'` |
| Preview publication | `make publish-preview` |
| Publish reviewed bundle | `make publish CONFIRM_PUBLIC=1` |
| Verify publication | `make verify-publish` |
| Show publication history | `make publish-history` |
| Roll back | `make rollback RUN_ID=<id> CONFIRM_PUBLIC=1` |
| Generate public registered-team page | `make registered-teams CSV=<file>` |
| Publish registered-team page | `make registered-teams-publish CSV=<file> CONFIRM_PUBLIC=1` |

Mutating commands retain explicit gates. `make`, `make help`, `make run`, and `make operator-run` do not publish publicly.

## Inputs and generated outputs

### Controlled input workbook

`input.xlsx` is the only supported primary planning input.

Required sheets:

- `Innstillinger`
- `Lag`

Common optional sheets:

- `Aldersgrupper`
- `Kilder`
- `Datopreferanser`
- an activity sheet such as `Aktiviteter`, `Aktivitetsplan`, or `Årshjul`

See [`docs/rvv-miniputt-input-formats.md`](docs/rvv-miniputt-input-formats.md) for exact columns, aliases, and validation rules.

### Common generated output

A successful run may produce:

- `season_plan.xlsx`
- `season_plan.csv`
- `season_plan_overview.csv`
- `season_plan.ics`
- `season_plan.html`
- `season_plan_report.html`
- `season_plan_spond.xlsx`
- `calendars.html`
- `input.html`
- `activities.json`
- `activities/index.html`
- registered-team HTML/JSON review artifacts
- run manifests, checkpoints, logs, fingerprints, privacy reports, and audit files

With timestamped export enabled, one run is written to one timestamped folder. Do not create or rely on nested `export/<timestamp>/<timestamp>` paths.

## Troubleshooting

### A valid registration is missing

1. Find the Forms response ID and Power Automate run.
2. Confirm the code-validation branch succeeded.
3. Confirm the SharePoint item exists and has an accepted status.
4. Export the List again.
5. Run registration validation and inspect rejected rows.
6. Check club/age-group spelling and duplicate identity rules.

### Invalid submissions are stored as accepted

Treat this as a Power Automate defect. Disable or repair the accepted branch before relying on new registrations. The repository import is a second safety layer, not a substitute for correct intake validation.

### Duplicate teams appear

Check for repeated Power Automate runs, duplicate SharePoint IDs, multiple active records for the same team, inconsistent labels, and retries without idempotency. The import should block duplicate IDs or duplicate team identities rather than guessing.

### Activities are missing from the website

Confirm that the activity sheet name is supported, fields are valid, Stage 4 regenerated `activities.json` and `activities/index.html`, the exact reviewed bundle was published, and WordPress points at the current `/latest/activities/` path.

### Calendar data looks incomplete

Run `make sources-status` and inspect sparse-event warnings. Refresh the source, repair credentials, inject a reviewed recovery file where needed, then resume the pipeline. Do not approve a schedule solely because Stage 2 technically completed.

### A run stopped halfway

Run:

```bash
make status
make logs
make operator-run
```

The pipeline is checkpointed and normally resumes from the earliest incomplete or stale stage.

### The public result is wrong

Stop further publication, identify the last known-good run, and use:

```bash
make publish-history
make rollback RUN_ID=<id> CONFIRM_PUBLIC=1
make verify-publish
```

Then correct the source data/code and generate a new reviewed bundle.

### Power Automate is unavailable

Use the Forms response export as a temporary recovery source, manually review it in private club storage, transform it into the documented SharePoint interchange columns, validate it with the repository tooling, and record the recovery. Do not copy unreviewed contact data into `input.xlsx` or publish it.

### The primary maintainer is unavailable

Follow [`docs/ownership-and-handover.md`](docs/ownership-and-handover.md). Recover through club-owned accounts, rotate credentials, freeze publication until current output is reviewed, and have a second person complete the documented dry run.

## Repository map

| Path | Purpose |
|---|---|
| `input.xlsx` | Controlled season-planning workbook |
| `tournament_scheduler/` | Canonical Python validation, scraping, scheduling, export, and operator logic |
| `scripts/rvv-miniputt` | Portable repository-local CLI launcher |
| `scripts/check` | Canonical local/CI verification entry point |
| `Makefile` | Human-discoverable thin command menu |
| `.github/workflows/` | CI and manual validation/review/publish/rollback workflows |
| `.pipeline/` | Local checkpoints, logs, decisions, and run state; generated, not authoritative source data |
| `export/` | Generated review/export output |
| `registered-teams/` | Standalone registered-team review artifacts |
| `docs/` | Detailed architecture, input, pipeline, security, and handover documentation |
| `apps/desktop/` | Experimental supervisor UI; not a separate planner |
| `.claude/`, `.opencode/`, `.codex/`, `.pi/` | Thin harness-specific adapters over canonical commands |

## Installation and development

Prerequisites:

- Python 3.10+
- `python3 -m venv`
- `pip`

```bash
git clone https://github.com/region-viken-vest-hockey/hockey.git
cd hockey
make install
make check
```

Install Playwright browser binaries where calendar scraping requires them:

```bash
INSTALL_PLAYWRIGHT=1 make install
```

`pyproject.toml` is the canonical direct dependency declaration. Deterministic installs and CI use the committed hash-checked `requirements.lock`. Refresh dependencies intentionally and verify lock freshness rather than installing unpinned packages ad hoc.

## Documentation

- [Pipeline and operator guide](docs/rvv-miniputt-pipeline.md)
- [Input formats and SharePoint registration export](docs/rvv-miniputt-input-formats.md)
- [Ownership and handover](docs/ownership-and-handover.md)
- [Run manifest and durable decisions](docs/run-manifest-schema.md)
- [Security](docs/security.md)
- [AI operator product direction](docs/ai-operator-product-direction.md)
- [AI operator roadmap](docs/ai-operator-roadmap.md)

## Handover acceptance test

A new volunteer should be able to complete the following without the original maintainer's personal account:

- [ ] access the club-owned Form, Power Automate flow, SharePoint List, repository, protected publication environment, WordPress, and Spond
- [ ] explain which system is authoritative for registrations, planning input, public editorial text, and communication
- [ ] validate a reviewed SharePoint export
- [ ] rebuild the `Lag` sheet without changing administrative workbook sheets
- [ ] update or verify activity and calendar sources
- [ ] generate a review bundle without publishing
- [ ] inspect warnings, plan quality, and privacy output
- [ ] publish through explicit approval or rehearse the protected workflow
- [ ] verify the public URL
- [ ] find publication history and perform a controlled rollback
- [ ] recover temporarily when Power Automate or a calendar source is unavailable

When any step still depends on undocumented personal knowledge, update this README or the linked operational documentation before the handover is considered complete.
