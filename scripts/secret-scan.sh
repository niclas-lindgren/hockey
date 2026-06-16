#!/usr/bin/env sh
set -eu

if command -v gitleaks >/dev/null 2>&1; then
  exec gitleaks detect --source . --config .gitleaks.toml --redact
fi

if command -v docker >/dev/null 2>&1; then
  exec docker run --rm -v "$(pwd):/repo" ghcr.io/gitleaks/gitleaks:latest detect \
    --source=/repo \
    --config=/repo/.gitleaks.toml \
    --redact \
    --no-banner
fi

echo "Install gitleaks or Docker to run the secret scan." >&2
exit 1
