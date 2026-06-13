# Plan: Allow same-club matchups when needed
**Goal:** Round-robin game generation can include same-club pairings, and the season planner/tests reflect that behavior.
**Created:** 2026-06-13
**Intent:** Remove the last planner-side filter that silently drops same-club games so tournaments can be fully scheduled even when sibling teams share a bracket.
**Backlog-ref:** 79

## Tasks
- [x] Remove the intra-club game filter from round-robin generation and update the surrounding docs/comments to describe the new behavior.
  - Files: tournament_scheduler/season_planner.py
  - Approach: delete the `home.club == away.club` skip in `generate_round_robin_games`, keep the existing round/slot packing logic intact, and revise any docstrings/comments that still promise same-club games are impossible.
- [x] Add regression coverage for same-club tournament draws.
  - Files: tests/test_season_planner.py, tests/test_round_robin.py
  - Approach: add focused tests that build a tournament containing multiple teams from the same club and assert the generated games include the intra-club pairing(s) instead of dropping them; keep existing round-count and bye behavior assertions intact.

## Notes
The repo already has unrelated working-tree changes and generated exports; avoid touching those files. Keep the fix narrowly scoped to planner game generation and tests.

## Acceptance Criteria
- [ ] `generate_round_robin_games()` returns same-club pairings when they are part of the selected participant set.
- [ ] A regression test fails before the change and passes after the change.
- [ ] Existing round-robin scheduling still produces the expected game count for a small all-same-club roster.

## Log


### 2026-06-13 — Add regression coverage for same-club tournament draws.
**Done:** Added regression coverage for both the generic round-robin generator and the season-planner test suite so same-club pairings are preserved and full round counts still hold.
**Rationale:** The planner change needed direct coverage at the generator level plus an end-to-end regression in the season planner tests to prevent the old filter from coming back.
**Findings:** A generator-level test was the clearest way to lock in the new behavior; the existing season-planner tests also needed expectation updates because same-club games now change the warning distribution.
**Files:** tests/test_round_robin.py, tests/test_season_planner.py
**Commit:** not committed
### 2026-06-13 — Remove the intra-club game filter from round-robin generation and update the surrounding docs/comments to describe the new behavior.
**Done:** Removed the same-club skip in round-robin generation so intra-club pairings are now emitted normally, and updated the surrounding docs/comments to match.
**Rationale:** The planner should no longer silently drop same-club matchups; allowing them preserves complete round-robins when sibling teams share a bracket.
**Findings:** The only code path that actually suppressed same-club games was the safety filter inside `generate_round_robin_games`; the surrounding docs had to be updated to stop promising that such matchups could never occur.
**Files:** tournament_scheduler/season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
