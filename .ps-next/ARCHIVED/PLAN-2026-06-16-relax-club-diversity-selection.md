# Plan: Relax club-diversity selection
**Goal:** Tournament participant selection prefers one team per club first, only repeats clubs when needed to fill a feasible tournament, while still keeping the proportional soft caps and fairness overrides.
**Created:** 2026-06-16
**Intent:** Improve tournament variety and readability for skewed rosters without reintroducing a rigid max-1-team-per-club rule.
**Backlog-ref:** 112

## Tasks
- [x] Rework participant selection scoring to strongly prefer new clubs before repeated clubs, with a clear feasibility fallback when the roster cannot fill a tournament otherwise.
  - Files: tournament_scheduler/participant_selection.py
  - Approach: replace the binary club-mix gate with a soft diversity penalty that prioritizes clubs not yet represented in the current tournament, keep the proportional `_max_club_teams_for` allowance as the soft cap, and leave deficit-aware overrides in place so heavily skewed age groups can still fill a valid roster.
- [x] Add regression coverage for skewed club distributions so the picker is proven to maximize distinct clubs when possible and only repeats clubs when necessary.
  - Files: tests/test_season_planner.py
  - Approach: add a focused tournament-selection regression that inspects the chosen participant mix for a skewed age group and asserts the first available clubs are diversified before any club repeats, while still allowing multiple teams from the same club when the roster would otherwise be infeasible.

## Notes
- Participant selection lives in `tournament_scheduler/participant_selection.py` and is re-exported onto `SeasonPlanner` at the bottom of `season_planner.py`.
- The existing proportional cap logic (`_max_club_teams_for`) should remain soft; this change only strengthens the tournament-mix preference.

## Acceptance Criteria
- [ ] A skewed age-group roster produces a tournament with the maximum feasible number of distinct clubs before any club is repeated.
- [ ] Existing season-planner tests pass after the selection change and the new regression test.

## Log


### 2026-06-16 — Add regression coverage for skewed club distributions so the picker is proven to maximize distinct clubs when possible and only repeats clubs when necessary.
**Done:** Added a regression test that builds a skewed U10 roster and asserts the first tournament uses every available club before repeating Jar to fill the last slot.
**Rationale:** The new test locks down the intended behavior for the soft club-diversity rule and protects against future regressions that reintroduce same-club clustering.
**Findings:** The first generated tournament now contains all 5 available clubs in the skewed-roster scenario, with Jar repeated only once to fill the final slot.
**Files:** tests/test_season_planner.py
**Commit:** not committed
### 2026-06-16 — Rework participant selection scoring to strongly prefer new clubs before repeated clubs, with a clear feasibility fallback when the roster cannot fill a tournament otherwise.
**Done:** Updated tournament participant selection so new clubs are chosen before repeating a club whenever possible, while preserving the proportional soft cap and deficit-aware fallback behavior for skewed rosters.
**Rationale:** The previous binary club-mix gate could still cluster same-club teams when the deficit score was high. A hard novelty-first ordering makes the intended tournament variety explicit and keeps repeats as a feasibility fallback.
**Findings:** Added a dedicated club-diversity penalty helper and reweighted the participant sort so unrepresented clubs are preferred first; the proportional per-club allowance still acts as a soft cap and same-club repeats remain possible once no new clubs are available.
**Files:** tournament_scheduler/participant_selection.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
