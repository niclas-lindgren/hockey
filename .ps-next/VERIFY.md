# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: pytest tests/test_pi_next_backlog_scripts.py | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /usr/bin/python3; stderr: /home/niclasl.guest/.local/lib/python3.12/site-packages/coverage/control.py:958: CoverageWarning: No data was collected. (no-data-collected); see https://covera |
| run: bash .agents/skills/pi-next/scripts/pi-next-state.sh . | PASS | exit 0; output: PS_DIR=/Users/niclasl/src/hockey/.ps-next
PROJECT=exists
PLAN=exists
BACKLOG=exists
UNCHECKED=0
CHECKED=3
OPEN_BACKLOG=13
BACKLOG_TOP_ID=59
BACKLOG_TOP_TEXT=Fix |
| grep: .pi/extensions/pi-next.ts contains pi-next-backlog.sh | PASS | found pi-next-backlog.sh in .pi/extensions/pi-next.ts |
| grep: .agents/skills/pi-next/scripts/pi-next-archive.sh contains pi-next-backlog.sh | PASS | found pi-next-backlog.sh in .agents/skills/pi-next/scripts/pi-next-archive.sh |
| Backlog helper preserves continuation lines when marking an item done, moves it from ## Open to ## Done, and rejects duplicate IDs. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
