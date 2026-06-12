#!/usr/bin/env bash
set -euo pipefail

PS_DIR="${1:?usage: pi-next-archive.sh PS_DIR [backlog_id]}"
BACKLOG_ID="${2:-}"
PLAN="$PS_DIR/PLAN.md"
[ -f "$PLAN" ] || { echo "No PLAN.md at $PLAN" >&2; exit 1; }

mkdir -p "$PS_DIR/ARCHIVED"
DATE="$(date +%F)"
TITLE="$(grep -m1 '^# Plan:' "$PLAN" | sed 's/^# Plan: *//' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-60)"
[ -n "$TITLE" ] || TITLE="plan"
DEST="$PS_DIR/ARCHIVED/PLAN-$DATE-$TITLE.md"
i=2
while [ -e "$DEST" ]; do
  DEST="$PS_DIR/ARCHIVED/PLAN-$DATE-$TITLE-$i.md"
  i=$((i+1))
done

GOAL="$(grep -m1 '^\*\*Goal:\*\*' "$PLAN" | sed 's/^\*\*Goal:\*\* *//' || true)"
FILES="$(grep '^\*\*Files:\*\*' "$PLAN" 2>/dev/null | tail -1 | sed 's/^\*\*Files:\*\* *//' || true)"
[ -n "$FILES" ] || FILES="see archived plan"

mv "$PLAN" "$DEST"

mkdir -p "$PS_DIR"
touch "$PS_DIR/HISTORY.md"
if ! grep -q '^# Build History' "$PS_DIR/HISTORY.md"; then
  tmp="$(mktemp)"
  { echo '# Build History'; cat "$PS_DIR/HISTORY.md"; } > "$tmp"
  mv "$tmp" "$PS_DIR/HISTORY.md"
fi
printf -- '- %s: %s; plan: %s; built %s\n' "$DATE" "${GOAL:-Completed plan}" "${DEST#$PS_DIR/}" "$FILES" >> "$PS_DIR/HISTORY.md"

if [ -n "$BACKLOG_ID" ] && [ -f "$PS_DIR/BACKLOG.md" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  "$SCRIPT_DIR/pi-next-backlog.sh" "$PS_DIR" done "$BACKLOG_ID" >/dev/null
fi

echo "$DEST"
