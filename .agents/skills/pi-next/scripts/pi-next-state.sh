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
  TASK_LINES=$(awk '/^## Tasks/{in_tasks=1; next} /^## /{if(in_tasks){in_tasks=0}} in_tasks && /^- \[[ x]\] /{print}' "$PS_DIR/PLAN.md" || true)
  if [ -n "$TASK_LINES" ]; then
    UNCHECKED=$(printf '%s\n' "$TASK_LINES" | grep -Ec '^- \[ \] ' || true)
    CHECKED=$(printf '%s\n' "$TASK_LINES" | grep -Ec '^- \[x\] ' || true)
  else
    UNCHECKED=0
    CHECKED=0
  fi
  PLAN_GOAL=$(grep -m1 '^\*\*Goal:\*\*' "$PS_DIR/PLAN.md" | sed 's/^\*\*Goal:\*\* *//' | tr -d '\r' | cut -c1-200 || true)
fi

OPEN_BACKLOG=0
BACKLOG_TOP_ID=""
BACKLOG_TOP_TEXT=""
if [ "$BACKLOG" = "exists" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  open_lines="$($SCRIPT_DIR/pi-next-backlog.sh "$WORK_DIR" list || true)"
  if [ -n "$open_lines" ]; then
    OPEN_BACKLOG=$(printf '%s\n' "$open_lines" | grep -Ec '^- \[[0-9]+\] \[ \] ' || true)
  else
    OPEN_BACKLOG=0
  fi
  top=$(printf '%s\n' "$open_lines" | head -1 || true)
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
