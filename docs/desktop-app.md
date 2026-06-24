# RVV Miniputt desktop app

This repo now includes a first desktop-app scaffold for non-technical users.
The goal is that normal users download an app, open it, choose `input.xlsx`, add credentials/API keys in Settings, and click **Lag sesongplan** — without installing Python or using a terminal.

## Architecture

```text
Electron desktop shell
  -> starts a bundled Python backend executable
  -> backend runs the existing RVV Miniputt pipeline
  -> backend stores settings locally and secrets in the OS keychain when available
```

The Python backend is `tournament_scheduler.desktop_server`. It exposes local-only HTTP endpoints on `127.0.0.1:8765`. The desktop UI does not ask normal users for a work/cache folder; when no work directory is supplied, the backend uses an app-local `pipeline-cache` directory under the OS application data folder.


- `GET /health`
- `GET /settings`
- `POST /settings`
- `POST /run`
- `GET /run/status`

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

## Playwright/browser note

The current scaffold bundles Python code and dependencies, but Playwright browser packaging still needs a final hardening pass before this is ready for non-technical distribution. We should choose one of:

1. Bundle Playwright browsers into the app for the smoothest first run.
2. Add a guided first-launch install step: “Installerer nødvendige nettleserkomponenter …”.

For volunteers, bundled browsers are probably best even if the app download becomes larger.
