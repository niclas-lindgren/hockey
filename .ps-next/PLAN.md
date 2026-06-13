# Plan: Document the pi-next proxy boundary
**Goal:** pi-next explicitly states it is a thin project-local proxy over shared PS:next behavior, with the cleanup boundary documented.
**Created:** 2026-06-13
**Intent:** Prevent the local skill from drifting into a second PS:next implementation and make the intended ownership boundary obvious for future cleanup.
**Backlog-ref:** 77

## Tasks
- [x] Document the thin-proxy boundary in the pi-next skill and lock it with a regression test
  - Files: .agents/skills/pi-next/SKILL.md, tests/test_pi_next_skill_boundary.py
  - Approach: Rewrite the skill intro/compatibility notes to say the local skill delegates to shared PS:next behavior and only keeps project-specific glue (state, backlog, lock, handoff). Add a small pytest that asserts the boundary language is present so future edits do not quietly reintroduce a duplicated workflow description.

## Notes
The current local skill already depends on shared PS:next scripts and protocol docs. This task should clarify that relationship rather than add new workflow behavior.

## Acceptance Criteria
- [ ] The pi-next skill file contains an explicit thin-proxy/boundary note that distinguishes shared PS:next behavior from local project-specific glue.
- [ ] `pytest tests/test_pi_next_skill_boundary.py` passes.

## Log

### 2026-06-13 — Document the thin-proxy boundary in the pi-next skill and lock it with a regression test
**Done:** Reworded the pi-next skill to describe it as a thin project-local proxy over shared PS:next behavior and added an explicit boundary/cleanup-target section.
**Rationale:** This keeps the local skill aligned with the shared PS:next contract while making the project-specific glue vs. shared workflow split obvious for future cleanup.
**Findings:** The current implementation already relies on shared PS:next scripts; the new documentation makes that dependency explicit instead of implying a separate local workflow clone.
**Files:** .agents/skills/pi-next/SKILL.md, tests/test_pi_next_skill_boundary.py
**Commit:** not committed
<!-- pi-next appends entries here after each task is executed -->
