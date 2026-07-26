# CI: required checks and branch protection

This documents the checks introduced for issue #16 — automatic, visible
evidence of test/reproducibility/packaging health on every PR and push to
`main`, since an autonomous operator needs independently enforced evidence
before changes are trusted or merged, not just a local "hundreds of tests
passed" claim in a commit message.

## Required-fast tier: `.github/workflows/ci.yml`

Triggers on every pull request and every push to `main`. Every job here is
designed to run in low single-digit minutes and makes **no live external
calendar/network call** — all fixtures are synthetic or in-memory, so the
whole tier is safe to require as a merge gate without flaking on a real
club's calendar site being slow or down.

| Job (status check name)                          | What it covers |
|----------------------------------------------------|----------------|
| `Python quick test suite`                           | The default `pytest` run (excludes `slow`/`integration`-marked tests) — the full unit/component suite. |
| `Operator manifest & escalation tests`              | `test_run_manifest.py`, `test_capability_result.py`, `test_escalation.py`, `test_operator_run.py` specifically, as their own visible check. |
| `Deterministic planner reproducibility`             | `test_reproducibility.py` — the same config/seeds must reproduce the same selected-candidate metadata and plan dates across two independent runs. |
| `CLI integration smoke test`                        | `test_cli_smoke.py` (marked `integration`) — a real `rvv-miniputt` subprocess invocation (`operator run`, `status`, `sources status`, `operator questions`, `candidates`) against a synthetic workbook with zero calendar sources. |
| `Desktop backend API smoke test`                    | `test_desktop_server_escalation.py` — a real HTTP round-trip against `desktop_server.Handler` (manifest, questions, answer, and confirms the dead `/run` route stays gone). |
| `Desktop packaging config validation`               | `test_desktop_packaging.py` — static checks on `apps/desktop/package.json` and `release.yml` (no Electron download, no build, no publish). Guards against the wrong-owner and missing-keyring bugs found in issue #7. |
| `Secret scanning (gitleaks)`                        | `gitleaks/gitleaks-action`, configured via the existing `.gitleaks.toml`. |

Dependencies are cached via `actions/setup-python`'s built-in `cache: pip`,
keyed on `requirements.txt` and `pyproject.toml`, across all jobs.

Failure artifacts: the quick-suite job uploads its `htmlcov/` coverage
report; the reproducibility and CLI-smoke jobs upload their `--basetemp`
directory (generated run manifests, checkpoints, logs) on failure so a
human or agent can inspect exactly what state a failing run produced.

## Slower/optional tier

Unchanged by this issue, and intentionally *not* required on every PR:

- **`.github/workflows/desktop-build.yml`** — manual (`workflow_dispatch`) or
  on a push touching desktop-relevant paths; builds a real unsigned macOS
  app via `electron-builder`. Slow (full Electron + PyInstaller build) and
  consumes meaningfully more Actions minutes, hence optional.
- **`.github/workflows/release.yml`** — triggers only on a `v*.*.*` tag;
  builds and publishes the real macOS/Windows/Linux release artifacts.

## Recommended branch protection

On the `main` branch, enable **Require status checks to pass before
merging** and require these exact check names (they're the job `name:`
values above, as GitHub renders them):

- `Python quick test suite`
- `Operator manifest & escalation tests`
- `Deterministic planner reproducibility`
- `CLI integration smoke test`
- `Desktop backend API smoke test`
- `Desktop packaging config validation`
- `Secret scanning (gitleaks)`

Also recommended: **Require branches to be up to date before merging**, so
a stale PR can't merge past a check that has since caught a regression on
`main`. The slower/optional workflows above should **not** be added as
required checks — they're not triggered on every PR and would permanently
block merging.
