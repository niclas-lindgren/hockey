# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `make registered-teams CSV=<sharepoint-export.csv>` should run and create a local reviewable page without publishing. | PASS | `make registered-teams CSV=/tmp/reg-teams-pi-next/empty.csv ARGS='--export-dir /tmp/reg-teams-pi-next/empty-export --generated-at 2026-07-30T12:00:00Z'` and the populated CSV variant both exited 0 and printed `Ikke publisert`. |
| `make registered-teams-publish CSV=<sharepoint-export.csv> CONFIRM_PUBLIC=1` should run through the guarded Pages publishing path. | PASS | Makefile target delegates to `scripts/rvv-miniputt registered-teams --csv "$$CSV" --publish --confirm-public`; `tests/test_registered_teams_publish.py` locks help/docs visibility and underlying publish-staging behavior. |
| The workflow should run independently of the season-plan pipeline and activity-calendar regeneration. | PASS | Smoke used only `registered-teams`; no Stage 1–4 or `activities` command was invoked. CLI stages registered-team artifacts over the existing `/latest/` snapshot. |
| The `club,label,age_group` SharePoint export should return actionable validation errors. | PASS | `tests/test_registered_teams.py` covers missing columns, blank fields, duplicate rows, invalid configured age groups, BOM/whitespace normalization, and row-numbered error messages. |
| The page should show teams grouped and counted clearly by age group and club. | PASS | `tests/test_registered_teams.py::test_groups_by_configured_age_group_then_club_and_team` and artifact inspection verified sorted age groups, club grouping, team counts, and total counts. |
| A header-only CSV should create a useful empty-state page. | PASS | Header-only Make smoke generated `registered-teams/pameldte-lag.html` containing `Ingen lag er registrert ennå`; unit tests cover zero counts. |
| Public artifacts should remove personal or internal SharePoint fields. | PASS | Populated CSV smoke asserted email/comment/SharePointId values were absent from public HTML/JSON while the private validation report recorded excluded columns and source fingerprint. |
| Registered-team staging should contain existing unrelated GitHub Pages files. | PASS | `tests/test_registered_teams_publish.py::test_prepare_registered_teams_latest_export_overlays_current_latest_snapshot` verifies current `season_plan.html` and `activities.json` are copied and `_meta.json` is refreshed by publish. |
| Tests should cover validation, rendering, privacy, deterministic output, and guarded publication. | PASS | Targeted pytest: `python3 -m pytest tests/test_registered_teams.py tests/test_registered_teams_publish.py tests/test_pages_bundle.py -q` passed (36 tests). Full gate: `python3 -m pytest -q -o addopts="" -m "slow or integration or (not slow and not integration)"` passed (1236 passed, 20 skipped). |
| `make help` and operator documentation should present this as a routine standalone content update. | PASS | `make help` target coverage passed; README and `docs/rvv-miniputt-pipeline.md` now include registered-team commands and the public URL `https://niclas-lindgren.github.io/hockey/latest/registered-teams/pameldte-lag.html`. |

Additional checks:

- `python3 -m compileall tournament_scheduler tests` passed.
- `pi_next_quality_gate(level="standard")` passed before final verification.
- `pi_next_quality_gate(level="full")` passed before archive.
