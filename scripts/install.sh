#!/bin/sh
set -eu

show_help() {
  cat <<'EOF'
Usage: scripts/install.sh [--help|-h]

Creates a virtualenv (default: ./venv), installs runtime dependencies from
requirements.txt, and installs the project in editable mode.

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

printf '%s\n' "Upgrading packaging tools ..."
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

printf '%s\n' "Installing runtime dependencies from requirements.txt ..."
"$VENV_PY" -m pip install -r requirements.txt

printf '%s\n' "Installing rvv-miniputt in editable mode ..."
"$VENV_PY" -m pip install -e .

if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then
  printf '%s\n' "Installing Playwright Chromium browser ..."
  "$VENV_PY" -m playwright install chromium
fi

printf '%s\n' "Done. Activate with: ./$VENV_DIR/bin/activate"
