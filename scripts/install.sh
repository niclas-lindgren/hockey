#!/bin/sh
set -eu

show_help() {
  cat <<'EOF'
Usage: scripts/install.sh [--help|-h]

Creates a virtualenv (default: ./venv), installs the locked Python dependency
set from requirements.lock, and installs the project in editable mode without
resolving additional dependencies.

Environment variables:
  VENV_DIR=venv              Virtualenv directory
  PYTHON_BIN=python3         Python interpreter to use
  INSTALL_PLAYWRIGHT=0       Set to 1 to install Playwright Chromium
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  show_help
  exit 0
fi

ROOT_DIR=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
VENV_DIR=${VENV_DIR:-venv}
PYTHON_BIN=${PYTHON_BIN:-python3}
INSTALL_PLAYWRIGHT=${INSTALL_PLAYWRIGHT:-0}

cd "$ROOT_DIR"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf '%s\n' "Error: $PYTHON_BIN not found on PATH." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  printf '%s\n' "Creating virtual environment in ./$VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PY="$ROOT_DIR/$VENV_DIR/bin/python3"
if [ ! -x "$VENV_PY" ]; then
  printf '%s\n' "Error: expected virtualenv interpreter at $VENV_PY" >&2
  exit 1
fi

if [ ! -f requirements.lock ]; then
  printf '%s\n' "Error: requirements.lock is missing. Run scripts/refresh-python-lock.sh intentionally before installing." >&2
  exit 1
fi

printf '%s\n' "Upgrading pip ..."
"$VENV_PY" -m pip install --upgrade pip

printf '%s\n' "Installing locked Python dependencies from requirements.lock ..."
"$VENV_PY" -m pip install --require-hashes -r requirements.lock

printf '%s\n' "Installing rvv-miniputt in editable mode without dependency resolution ..."
"$VENV_PY" -m pip install --no-deps -e .

if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then
  printf '%s\n' "Installing Playwright Chromium browser ..."
  "$VENV_PY" -m playwright install chromium
fi

printf '%s\n' "Done. Activate with: ./$VENV_DIR/bin/activate"
