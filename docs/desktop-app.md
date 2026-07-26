# RVV Miniputt desktop app

This repo includes a desktop-app scaffold for non-technical users. The goal
is that normal users download an app, open it, choose `input.xlsx`, add
credentials/API keys in Settings, and click **Lag sesongplan** — without
installing Python or using a terminal.

## Role: optional supervisor surface, not a second implementation

Per [`docs/ai-operator-product-direction.md`](ai-operator-product-direction.md),
the desktop app is **not** the primary near-term interface and must not
become a second, independently-maintained implementation of the pipeline.
Concretely:

- The Electron shell has no scheduling logic at all — it starts the Python
  backend and renders whatever it returns.
- The Python backend (`tournament_scheduler.desktop_server`) runs the exact
  same stage modules (`tournament_scheduler.pipeline.stage1_config` … 
  `stage4_export`) as the CLI, via the same checkpoint files under the work
  directory — nothing about *what* runs or *how a plan is built* is
  reimplemented for Electron.
- `GET /manifest` and `GET /questions` / `POST /questions/answer` expose the
  same run manifest and escalation questions described in
  [`docs/run-manifest-schema.md`](run-manifest-schema.md) — the same state
  `rvv-miniputt status --json` and `rvv-miniputt operator questions` show —
  so a future UI can display objective/progress/pending-questions without
  re-deriving them from raw checkpoints.
- The app can be omitted entirely without losing any operator capability:
  every capability it calls into is also reachable from `rvv-miniputt`.

**Known remaining overlap, tracked as follow-up work, not resolved by this
pass:** `_run_smart` in `desktop_server.py` still runs its own bounded
adjust/retry loop with bespoke per-stage LLM calls
(`_llm_decide_config`/`_llm_decide_scraping`/`_llm_decide_plan`) to produce
live, Norwegian-language narration for a non-technical user, rather than
shelling out to `rvv-miniputt operator run` (issue #2) and consuming its
manifest output directly. The stage *execution* is not duplicated (see
above), only the retry/narration *policy*. Replacing it is a real UI-risk
change — it removes live LLM narration end users may already rely on — so
it was deliberately left in place rather than rewritten blind in a session
with no way to run the actual Electron app end-to-end. A future pass should
migrate `_run_smart` to invoke `operator run` and translate its manifest
into the same narration, rather than keeping two orchestration policies.

## Architecture

```text
Electron desktop shell
  -> starts a bundled Python backend executable
  -> backend runs the existing RVV Miniputt pipeline (same stage modules as the CLI)
  -> backend stores settings locally and secrets in the OS keychain when available
```

The Python backend is `tournament_scheduler.desktop_server`. It exposes local-only HTTP endpoints on `127.0.0.1:8765`. The desktop UI does not ask normal users for a work/cache folder; when no work directory is supplied, the backend uses an app-local `pipeline-cache` directory under the OS application data folder.

Selected endpoints (see `desktop_server.py`'s `Handler` class for the full list):

- `GET /health`, `GET /settings`, `POST /settings`
- `POST /run/smart`, `GET /run/status` — the guided "smart run" and its live log/state
- `GET /manifest` — the same AI-operator run manifest the CLI writes
- `GET /questions`, `POST /questions/answer` — escalation questions raised by a run, and recording a durable answer
- `GET /stage/status`, `GET /checkpoint/<stage>` — raw per-stage checkpoint inspection
- `GET /exports`, `GET /exports/<subfolder>` — generated export files
- `POST /run/command` — a whitelisted subset of portable CLI commands (see `ALLOWED_COMMANDS`)
- `GET /llm/status`, `POST /llm/test`, `POST /llm/validate-teams` — the desktop's own LLM-assist settings
- `GET /playwright/status`, `POST /playwright/install` — browser dependency for calendar scraping

## User-facing features in the prototype

- Choose `input.xlsx`
- Choose export folder
- Use an automatic app-local cache/work folder
- Configure BookUp credentials and API keys
- Run the pipeline
- Watch live logs
- Open `season_plan.html`
- Open the export folder

## Secret storage

The backend uses Python `keyring` when available:

- macOS Keychain
- Windows Credential Manager
- Linux Secret Service/keyring

If keyring is unavailable, it falls back to a local file under the app config directory. The UI tells the user which backend is active.

## Development run

From the desktop app folder:

```bash
cd apps/desktop
npm install
npm start
```

`npm start` automatically creates/repairs the local Python venv if required. You can still run the setup manually with:

```bash
npm run setup:python
```

If `npm start` fails with `spawn ENOEXEC`, Electron was almost certainly installed for the wrong operating system/CPU architecture. This can happen when `node_modules` was created in a Linux/Pi environment and then reused on macOS. Fix it on the machine where you want to run the app:

```bash
cd apps/desktop
npm run cleanup
npm start
```

`npm run cleanup` removes `node_modules` and `package-lock.json`, then reinstalls dependencies for the current platform. If you prefer doing it manually:

```bash
rm -rf node_modules package-lock.json
npm install
```

The app also has a doctor check:

```bash
npm run doctor
```

Node 20 or 22 LTS is recommended. Very new Node versions may work, but are not the tested path.

### Linux/Lima sandbox note

When running inside Linux dev environments on mounted macOS folders, Electron may fail with:

```text
The SUID sandbox helper binary was found, but is not configured correctly
chrome-sandbox is owned by root and has mode 4755
```

The development `npm start` wrapper automatically passes `--no-sandbox` on Linux to avoid this. This is for local development only; packaged releases should use the platform's normal sandbox/signing setup.

In development, Electron starts the repo venv backend:

```bash
../../venv/bin/python3 -m tournament_scheduler.desktop_server --port 8765
```

The `prestart` hook creates/repairs that venv and installs the project dependencies when needed. This is still only for developers; packaged end-user builds will include the Python runtime/backend so users do not install Python themselves.

## Local packaged build without installing Python

If you do not want to install Python locally, use the local packaging script from the repo root:

```bash
scripts/package-desktop-local.sh
```

It downloads a private standalone Python 3.12 into `.desktop-build/python-standalone/`, installs Python dependencies there, builds the PyInstaller backend, then runs Electron packaging. It does not install anything into system Python.

Artifacts are written under:

```text
apps/desktop/dist/
```

Node.js/npm is still required for the Electron shell. Node 22 LTS is recommended.

## Build the bundled Python backend only

From the repo root:

```bash
scripts/package-desktop-backend.sh
```

This creates a PyInstaller build under:

```text
dist/desktop-backend/rvv-miniputt-backend/
```

## Build the desktop app manually

After building the backend:

```bash
cd apps/desktop
npm install
npm run dist
```

`electron-builder` includes the backend as an extra resource.

## GitHub Actions build

There is also a manual workflow at `.github/workflows/desktop-build.yml`. Run **Build desktop app** from the GitHub Actions tab to produce an unsigned macOS artifact when CI minutes are available.

Tagged releases (`v*.*.*`) build all three platforms via `.github/workflows/release.yml` and attach the artifacts to a GitHub Release. `desktop_server.py` imports `keyring` at runtime (`_try_keyring()`) and the Linux leg of that workflow bundles `keyring.backends.SecretService` as a PyInstaller hidden import — both require `keyring` to actually be installed in the build environment. It was previously only `pip install`ed for the macOS and Windows legs; the Linux release build would still succeed, but would silently fall back to storing BookUp/LLM credentials in a local JSON file instead of the OS Secret Service. Fixed to install `keyring` unconditionally on every platform.

## Playwright/browser note

The current scaffold bundles Python code and dependencies, but Playwright browser packaging still needs a final hardening pass before this is ready for non-technical distribution. We should choose one of:

1. Bundle Playwright browsers into the app for the smoothest first run.
2. Add a guided first-launch install step: “Installerer nødvendige nettleserkomponenter …”.

For volunteers, bundled browsers are probably best even if the app download becomes larger.
