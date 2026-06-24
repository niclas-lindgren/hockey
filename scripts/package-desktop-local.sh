#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUILD_DIR="$ROOT_DIR/.desktop-build"
PY_ROOT="$BUILD_DIR/python-standalone"
PY_BIN="$PY_ROOT/python/bin/python3"
NODE_DIR="$ROOT_DIR/apps/desktop"

mkdir -p "$BUILD_DIR"

platform=$(uname -s)
arch=$(uname -m)
case "$platform:$arch" in
  Darwin:arm64) PBS_TARGET="aarch64-apple-darwin"; ELECTRON_ARGS=(--mac dmg zip) ;;
  Darwin:x86_64) PBS_TARGET="x86_64-apple-darwin"; ELECTRON_ARGS=(--mac dmg zip) ;;
  Linux:x86_64) PBS_TARGET="x86_64-unknown-linux-gnu"; ELECTRON_ARGS=(--linux AppImage) ;;
  Linux:aarch64|Linux:arm64) PBS_TARGET="aarch64-unknown-linux-gnu"; ELECTRON_ARGS=(--linux AppImage) ;;
  *)
    echo "Unsupported local build platform: $platform $arch" >&2
    exit 1
    ;;
esac

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm is required for the Electron shell." >&2
  echo "Install Node 22 LTS, then rerun this script." >&2
  exit 1
fi

if [[ ! -x "$PY_BIN" ]]; then
  echo "Downloading standalone Python 3.12 for $PBS_TARGET..."
  api_json="$BUILD_DIR/python-build-standalone-release.json"
  curl -fsSL "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest" -o "$api_json" || \
    curl -fsSL "https://api.github.com/repos/indygreg/python-build-standalone/releases/latest" -o "$api_json"

  asset_url=$(grep -Eo 'https://[^" ]+cpython-3\.12\.[^" ]+-'"$PBS_TARGET"'-install_only_stripped\.tar\.gz' "$api_json" | head -n 1 || true)
  if [[ -z "$asset_url" ]]; then
    echo "Could not find a standalone Python asset for $PBS_TARGET in the latest release." >&2
    echo "Open $api_json to inspect available assets." >&2
    exit 1
  fi

  archive="$BUILD_DIR/python-standalone.tar.gz"
  curl -fL "$asset_url" -o "$archive"
  rm -rf "$PY_ROOT"
  mkdir -p "$PY_ROOT"
  tar -xzf "$archive" -C "$PY_ROOT"
fi

"$PY_BIN" --version

export PYTHON_BIN="$PY_BIN"
export PLAYWRIGHT_BROWSERS_PATH=0

"$PY_BIN" -m pip install --upgrade pip setuptools wheel
"$PY_BIN" -m pip install -e "${ROOT_DIR}[desktop]"
"$PY_BIN" -m playwright install chromium

"$ROOT_DIR/scripts/package-desktop-backend.sh"

cd "$NODE_DIR"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

CSC_IDENTITY_AUTO_DISCOVERY=false npm run dist -- "${ELECTRON_ARGS[@]}"

cat <<MSG

Desktop build complete.
Artifacts are in:
  $NODE_DIR/dist

This used a private standalone Python under:
  $PY_ROOT

Nothing was installed into the system Python.
MSG
