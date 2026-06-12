# Plan: Normalize backlog structure
**Goal:** BACKLOG.md keeps all unchecked items under ## Open, all completed items under ## Done, and no duplicate/conflicting IDs remain.
**Created:** 2026-06-12
**Intent:** Make backlog state reliable after the helper fix so Pi/Claude automation only sees real open work.
**Backlog-ref:** 60

## Tasks
- [x] Rewrite the backlog into open-only and done-only sections
  - Files: .ps-next/BACKLOG.md
  - Approach: Rebuild BACKLOG.md so ## Open contains only unchecked items, ## Done contains completed items with preserved continuation lines, and the conflicting duplicate ID 54 is renumbered to the next free unique id while keeping the original completed task text.

## Notes
The helper/state tooling was already fixed in backlog item 59. This cleanup should only normalize the existing backlog content and avoid touching unrelated working-tree changes.

## Acceptance Criteria
- [ ] run: bash .agents/skills/pi-next/scripts/pi-next-state.sh .
- [ ] run: bash .agents/skills/pi-next/scripts/pi-next-backlog.sh . list
- [ ] run: python3 - <<'PY'
from pathlib import Path
import re
text = Path('.ps-next/BACKLOG.md').read_text().splitlines()
section = None
ids = {}
for line_no, line in enumerate(text, 1):
    if line.startswith('## '):
        section = line[3:]
    match = re.match(r'^- \[(\d+)\] \[([ x])\] ', line)
    if not match:
        continue
    item_id = int(match.group(1))
    checked = match.group(2) == 'x'
    ids.setdefault(item_id, []).append(line_no)
    if section == 'Open' and checked:
        raise SystemExit(f'checked item still under Open at line {line_no}')

for item_id, locations in ids.items():
    if len(locations) > 1:
        raise SystemExit(f'duplicate backlog id {item_id} at lines {locations}')
print('ok')
PY

## Log

### 2026-06-12 — Rewrite the backlog into open-only and done-only sections
**Done:** Rebuilt .ps-next/BACKLOG.md so ## Open now contains only unchecked items, ## Done contains completed items with continuation lines preserved, and the conflicting duplicate 54 entry from the open section was renumbered to 72.
**Rationale:** The backlog file itself was the source of the polluted state; normalizing it makes helper output match the actual open work.
**Findings:** pi_next_state now reports UNCHECKED=1 and pi_next_backlog list shows only open items. The duplicate-id conflict was resolved by keeping the historical done #54 entry and renumbering the moved progress-output task to #72.
**Files:** .ps-next/BACKLOG.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
