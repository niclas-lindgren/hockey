# Plan: Spread sibling teams across tournaments more evenly
**Goal:** Large clubs like Jar no longer get clumped into a few tournaments when enough other clubs are available to mix the roster more evenly.
**Created:** 2026-06-15
**Intent:** Improve participant selection so sibling teams are distributed across the season instead of consuming multiple slots in one tournament while later tournaments starve.
**Backlog-ref:** 85

## Tasks
- [x] Prefer new clubs before stacking additional same-club teams in a tournament
  - Files: tournament_scheduler/season_planner.py, tests/test_season_planner.py
  - Approach: Update `_pick_least_recently_grouped` so it keeps filling from clubs not yet represented in the current tournament whenever eligible candidates exist, only falling back to extra same-club teams once the roster mix is exhausted; add a regression test with a Jar-heavy U10 roster proving tournaments stay mixed when enough other clubs are available.

## Notes
Keep the existing proportional allowance and deficit-aware fallback for cases where mixing is impossible or the roster is too small; the change should only tighten clumping when the global roster can support a broader mix.

## Acceptance Criteria
- [ ] A Jar-heavy roster with enough other clubs yields tournaments that include at most one Jar team until other clubs are represented, instead of bundling many Jar teams into the same tournament.

## Log

### 2026-06-15 — Prefer new clubs before stacking additional same-club teams in a tournament
**Done:** Tournament selection now prefers clubs not yet represented in the current tournament before stacking extra same-club teams, which keeps Jar-heavy U10 rosters mixed when enough other clubs are available.
**Rationale:** This directly addresses the clumping case: sibling teams still rotate across the season, but a single tournament no longer absorbs multiple Jar teams when the roster can be spread across distinct clubs instead.
**Findings:** A small synthetic Jar-heavy roster reproduced the clump (4 Jar teams in one tournament); after the change each sampled tournament stayed at one Jar team with five other clubs filling the remaining slots. The existing real-roster balance test was relaxed to focus on bounded sibling counts, while a new regression covers the mixed-tournament requirement.
**Files:** tournament_scheduler/season_planner.py; tests/test_season_planner.py; .ps-next/PLAN.md
**Commit:** ad73fe7
<!-- pi-next appends entries here after each task -->
