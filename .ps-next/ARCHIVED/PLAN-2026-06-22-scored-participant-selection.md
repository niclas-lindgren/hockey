# Plan: Scored participant selection
**Goal:** Participant selection uses one scored objective that balances club caps, game-count deficits, opponent diversity, and skill-band preferences.
**Created:** 2026-06-22
**Intent:** Replace the current ordered heuristics with a single objective so tournament composition is easier to reason about and fairer in edge cases.
**Backlog-ref:** 194

## Tasks
- [x] Add a scored participant-selection helper and route the planner through it
  - Files: tournament_scheduler/participant_selection.py, tournament_scheduler/season_planner.py
  - Approach: introduce one candidate-scoring function that combines club-cap pressure, deficit priority, repeat-opponent penalties, and skill-band distance; use it from both the small-tournament and max-cap selection paths without changing the existing public planner API.
- [x] Add regression tests that exercise the new balance trade-offs
  - Files: tests/test_season_planner.py
  - Approach: add focused scenarios that force the selector to choose between repeated clubs, high-deficit teams, diverse opponents, and skill-adjacent teams; assert the chosen tournaments stay within the expected caps and still preserve the current fairness invariants.
- [x] Refresh the rules report wording for the new selection objective
  - Files: tournament_scheduler/rules_report.py, docs/rvv-miniputt-rules-report.md
  - Approach: rewrite the participant-selection explanation to describe the scored objective, then update the committed markdown snapshot so the doc regression test continues to match.

## Notes
The existing selector is split across `cap_per_club_deficit_aware()` and `pick_least_recently_grouped()`; the refactor should keep their behavior recognizable but collapse the decision-making into one score. Preserve the current soft nature of club caps and skill bands.

## Acceptance Criteria
- [ ] `pytest tests/test_season_planner.py tests/test_rules_report_doc.py` passes.
- [ ] `render_rules_markdown(planner)` still matches `docs/rvv-miniputt-rules-report.md`.

## Log



### 2026-06-22 — Refresh the rules report wording for the new selection objective
**Done:** Reworded the participant-selection rule to describe the new scored objective and synced the committed markdown snapshot.
**Rationale:** The rules report needs to explain the new balance model in the same terms the code now uses, and the doc snapshot must stay aligned with the regression test.
**Findings:** The rendered markdown now matches the committed rules-report snapshot again after the wording update.
**Files:** tournament_scheduler/rules_report.py; docs/rvv-miniputt-rules-report.md
**Commit:** not committed
### 2026-06-22 — Add regression tests that exercise the new balance trade-offs
**Done:** Added focused regression coverage for the shared participant-selection score: repeat-history vs. skill-band, deficit pressure vs. repeat pressure, and near-band vs. far-band skill choices.
**Rationale:** The new scoring path needs direct proof that its trade-offs are behaving as intended, not just end-to-end plan snapshots.
**Findings:** The scorer is now the single point where club-cap pressure, deficit, repeat history, and skill band interact, so the new tests target that helper directly and keep the existing season-planner invariants green.
**Files:** tests/test_season_planner.py
**Commit:** not committed
### 2026-06-22 — Add a scored participant-selection helper and route the planner through it
**Done:** Introduced a single scored participant-selection path and kept the existing public planner API intact.
**Rationale:** The old selection flow split the decision across separate heuristics; a shared score now balances club caps, deficit pressure, repeat-opponent history, and skill-band fit in one place.
**Findings:** The planner already delegated participant selection through tournament_scheduler.participant_selection, so the core refactor stayed localized there. I also added a direct SeasonPlanner binding for the new scored helper and refreshed the rules-report wording/doc snapshot to match the new explanation.
**Files:** tournament_scheduler/participant_selection.py; tournament_scheduler/season_planner.py; tournament_scheduler/rules_report.py; docs/rvv-miniputt-rules-report.md; tests/test_season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
