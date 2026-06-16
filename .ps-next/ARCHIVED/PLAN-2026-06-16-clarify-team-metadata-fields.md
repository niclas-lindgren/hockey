# Plan: Clarify Team metadata fields
**Goal:** Keep `Team.region` and `Team.skill_level` only where they still matter, and document their roles clearly instead of deleting live scheduling inputs.
**Created:** 2026-06-16
**Intent:** Confirm whether the fields are dead code; if not, make their remaining uses explicit so future refactors do not remove needed roster metadata or skill-based selection.
**Backlog-ref:** 108

## Tasks
- [x] Document the surviving semantics of `Team.region` and `Team.skill_level`
  - Files: tournament_scheduler/models.py, tournament_scheduler/roster_loader.py, docs/rvv-miniputt-input-formats.md, docs/rvv-miniputt-pipeline.md
  - Approach: update the `Team` docstring and roster-loader docs to state that `region` is retained roster metadata for neighbor-club/cross-region inputs, while `skill_level` is an active planning hint used by participant selection; add a short docs note that both fields are preserved for round-tripping and backward compatibility.

## Notes
`skill_level` is still consumed by `SeasonPlanner` and `participant_selection.py` to bias tournament composition toward adjacent skill bands. `region` is not used as a scheduling constraint, but it is still parsed, preserved, and tested for neighbor-club rosters.

## Acceptance Criteria
- [ ] Docs and inline comments explain why `region` and `skill_level` still exist and how each field is used.
- [ ] No scheduling code is changed to treat `region` as a live constraint.
- [ ] Existing roster-loading and skill-level planner tests still pass.

## Log

### 2026-06-16 — Document the surviving semantics of `Team.region` and `Team.skill_level`
**Done:** Clarified the surviving meaning of both Team metadata fields in code comments and operator docs.
**Rationale:** Audit showed `skill_level` is active scheduling input for participant selection, while `region` is still preserved metadata for neighbor-club/cross-region rosters and reporting. That means the right fix is documentation/annotation, not removal.
**Findings:** `skill_level` is consumed in `season_planner.py` and `participant_selection.py` to bias tournament composition toward adjacent skill bands. `region` is parsed and retained through roster loading and workbook input, but it is not used as a hard scheduling constraint.
**Files:** docs/rvv-miniputt-input-formats.md; docs/rvv-miniputt-pipeline.md; tournament_scheduler/models.py; tournament_scheduler/roster_loader.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
