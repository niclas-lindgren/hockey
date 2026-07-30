#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif [[ -x "$ROOT_DIR/venv/bin/python3" ]]; then
  PYTHON_BIN="$ROOT_DIR/venv/bin/python3"
else
  PYTHON_BIN="python3"
fi

if [[ ! -f requirements.lock ]]; then
  echo "ERROR: requirements.lock is missing. Run scripts/refresh-python-lock.sh intentionally before packaging." >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install --require-hashes -r requirements.lock
"$PYTHON_BIN" -m pip install --no-deps -e .
"$PYTHON_BIN" -m PyInstaller \
  --name rvv-miniputt-backend \
  --clean \
  --noconfirm \
  --collect-all tournament_scheduler \
  --hidden-import keyring.backends.macOS \
  --hidden-import keyring.backends.Windows \
  --hidden-import keyring.backends.SecretService \
  --distpath dist/desktop-backend \
  --workpath build/desktop-backend \
  tournament_scheduler/desktop_server.py

cat <<'MSG'

Desktop backend built in dist/desktop-backend/rvv-miniputt-backend/.
For Electron packaging, copy or point electron-builder extraResources at that folder.

Next:
  cd apps/desktop
  npm install
  npm run dist
MSG
