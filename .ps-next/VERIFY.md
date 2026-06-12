# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: bash .agents/skills/pi-next/scripts/pi-next-state.sh . | PASS | exit 0; output: PS_DIR=/Users/niclasl/src/hockey/.ps-next
PROJECT=exists
PLAN=exists
BACKLOG=exists
UNCHECKED=0
CHECKED=1
OPEN_BACKLOG=12
BACKLOG_TOP_ID=60
BACKLOG_TOP_TEXT=Cle |
| run: bash .agents/skills/pi-next/scripts/pi-next-backlog.sh . list | PASS | exit 0; output: - [60] [ ] Clean the existing .ps-next/BACKLOG.md structure after fixing the helper: move all checked items currently under ## Open into ## Done, resolve duplic |
| run: python3 - <<'PY' | PASS | exit 0 |
