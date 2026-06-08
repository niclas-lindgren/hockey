#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="${1:-.}"
ARGS="${2:-}"

if [ -d "$WORK_DIR/.ps-next" ]; then
  PS_DIR="$(cd "$WORK_DIR/.ps-next" && pwd)"
else
  slug="$(basename "$(cd "$WORK_DIR" && pwd)")"
  PS_DIR="$HOME/.ps-next/projects/$slug"
fi

PROJECT="missing"; [ -f "$PS_DIR/PROJECT.md" ] && PROJECT="exists"
PLAN="missing"; [ -f "$PS_DIR/PLAN.md" ] && PLAN="exists"
BACKLOG="missing"; [ -f "$PS_DIR/BACKLOG.md" ] && BACKLOG="exists"

UNCHECKED=0
CHECKED=0
PLAN_GOAL=""
if [ "$PLAN" = "exists" ]; then
  UNCHECKED=$(grep -Ec '^- \[ \] ' "$PS_DIR/PLAN.md" || true)
  CHECKED=$(grep -Ec '^- \[x\] ' "$PS_DIR/PLAN.md" || true)
  PLAN_GOAL=$(grep -m1 '^\*\*Goal:\*\*' "$PS_DIR/PLAN.md" | sed 's/^\*\*Goal:\*\* *//' | tr -d '\r' | cut -c1-200 || true)
fi

OPEN_BACKLOG=0
BACKLOG_TOP_ID=""
BACKLOG_TOP_TEXT=""
if [ "$BACKLOG" = "exists" ]; then
  OPEN_BACKLOG=$(grep -Ec '^- \[[0-9]+\] \[ \] ' "$PS_DIR/BACKLOG.md" || true)
  top=$(grep -E '^- \[[0-9]+\] \[ \] ' "$PS_DIR/BACKLOG.md" | head -1 || true)
  if [ -n "$top" ]; then
    BACKLOG_TOP_ID=$(printf '%s' "$top" | sed -E 's/^- \[([0-9]+)\] \[ \] .*/\1/')
    BACKLOG_TOP_TEXT=$(printf '%s' "$top" | sed -E 's/^- \[[0-9]+\] \[ \] //')
  fi
fi

ARGS_PROVIDED=0
[ -n "$ARGS" ] && ARGS_PROVIDED=1

cat <<OUT
PS_DIR=$PS_DIR
PROJECT=$PROJECT
PLAN=$PLAN
BACKLOG=$BACKLOG
UNCHECKED=$UNCHECKED
CHECKED=$CHECKED
OPEN_BACKLOG=$OPEN_BACKLOG
BACKLOG_TOP_ID=$BACKLOG_TOP_ID
BACKLOG_TOP_TEXT=$BACKLOG_TOP_TEXT
ARGS_PROVIDED=$ARGS_PROVIDED
PLAN_GOAL=$PLAN_GOAL
OUT
