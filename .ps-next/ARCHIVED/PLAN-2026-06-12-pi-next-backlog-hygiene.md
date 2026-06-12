# Plan: Pi-next backlog hygiene
**Goal:** Backlog done operations keep ## Open open-only, preserve multiline items, reject duplicate IDs, and are covered by deterministic checks.
**Created:** 2026-06-12
**Intent:** Keep Pi/Claude backlog state reliable so automation selects only actionable open items and does not corrupt structured backlog entries.
**Backlog-ref:** 59

## Tasks
- [x] Add shared deterministic backlog manipulation script
  - Files: .agents/skills/pi-next/scripts/pi-next-backlog.sh, .agents/skills/pi-next/scripts/pi-next-state.sh
  - Approach: Implement list/get/add/done operations in one bash helper that parses ## Open/## Done sections, preserves continuation lines while moving done items, rejects duplicate IDs, and update state detection to count/list open items from ## Open only via the helper.
- [x] Wire Pi extension and archive helper to the backlog script
  - Files: .pi/extensions/pi-next.ts, .agents/skills/pi-next/scripts/pi-next-archive.sh, .agents/skills/pi-next/scripts/pi-next-backlog.sh
  - Approach: Replace inline TypeScript/sed backlog mutations with calls to pi-next-backlog.sh so tool done/archive behavior shares the tested section-aware implementation.
- [x] Add deterministic regression checks for multiline and duplicate backlog cases
  - Files: tests/test_pi_next_backlog_scripts.py
  - Approach: Add pytest tests that copy the pi-next scripts into a temp project, exercise multiline done movement, open-only listing/counting, add ID allocation, and duplicate/conflicting ID rejection.

## Notes
The working tree already had unrelated uncommitted changes before this plan: .ps-next/BACKLOG.md additions/deletions, export/ deletions, export/.DS_Store, and tournament_scheduler/pipeline/stage2_scraping.py. Avoid modifying those except PLAN/log/archive effects required by pi-next.
openspec/AGENTS.md was referenced by AGENTS.md but is absent in this checkout.
Existing pi_next_backlog and pi-next-archive currently mark checked items in place under ## Open; pi-next-state greps the whole file, so checked continuation-line items can leave ## Open polluted.

## Acceptance Criteria
- [ ] run: pytest tests/test_pi_next_backlog_scripts.py
- [ ] run: bash .agents/skills/pi-next/scripts/pi-next-state.sh .
- [ ] grep: .pi/extensions/pi-next.ts contains pi-next-backlog.sh
- [ ] grep: .agents/skills/pi-next/scripts/pi-next-archive.sh contains pi-next-backlog.sh
- [ ] Backlog helper preserves continuation lines when marking an item done, moves it from ## Open to ## Done, and rejects duplicate IDs.

## Log



### 2026-06-12 — Add deterministic regression checks for multiline and duplicate backlog cases
**Done:** Added pytest coverage for multiline done movement, open-only list/state counts, and duplicate-ID rejection for add/done paths.
**Rationale:** Script-level regression tests exercise the exact helpers used by state, archive, and the Pi extension without needing a loaded Pi runtime.
**Findings:** pytest tests/test_pi_next_backlog_scripts.py passed. Drift warnings are due to accumulated task changes, pre-existing unrelated changes, and untracked new test/helper files not being visible to pi_next_plan_drift.
**Files:** tests/test_pi_next_backlog_scripts.py
**Commit:** not committed
### 2026-06-12 — Wire Pi extension and archive helper to the backlog script
**Done:** Routed pi_next_backlog actions and pi-next-archive backlog completion through pi-next-backlog.sh; adjusted helper to accept either a worktree or .ps-next directory.
**Rationale:** Using the same script for extension tools and archive prevents behavioral drift and makes completion section-aware everywhere.
**Findings:** bash -n and grep checks passed. Drift warnings include prior task files and pre-existing unrelated working-tree changes; untracked helper still is not visible to pi_next_plan_drift.
**Files:** .pi/extensions/pi-next.ts, .agents/skills/pi-next/scripts/pi-next-archive.sh, .agents/skills/pi-next/scripts/pi-next-backlog.sh
**Commit:** not committed
### 2026-06-12 — Add shared deterministic backlog manipulation script
**Done:** Added pi-next-backlog.sh with section-aware list/get/add/done/validate operations, and updated pi-next-state.sh to count task checkboxes and open backlog items from the appropriate sections.
**Rationale:** A single deterministic helper avoids regex-only mutations that leave checked items under ## Open or lose continuation lines.
**Findings:** Existing working tree had unrelated uncommitted .ps-next/BACKLOG.md, export/, and stage2 changes, so plan drift warnings include pre-existing changes. pi_next_plan_drift also ignores untracked files, so the new helper was listed as not changed despite existing in the worktree.
**Files:** .agents/skills/pi-next/scripts/pi-next-backlog.sh (new), .agents/skills/pi-next/scripts/pi-next-state.sh
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
