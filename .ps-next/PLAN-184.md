# Plan: Scope game count spread check per age group

**Goal:** Fix the critic/rules check so the spread calculation is scoped per age group (e.g. U7 vs U7, not U7 vs U12).
**Created:** 2026-06-21
**Intent:** Prevent misleading warnings caused by comparing game counts across age groups with structurally different game totals.
**Backlog-ref:** 184

## Tasks

- [x] Added game_count_spread_by_age_group: Dict[str, int] field to SeasonPlan with doc comment explaining its purpose. — 2026-06-21
  - Files: tournament_scheduler/models.py
  - Approach: Add a new field `game_count_spread_by_age_group: Dict[str, int]` (default empty dict) to SeasonPlan alongside the existing global `game_count_spread`. This is the foundation that downstream components will populate and consume.

- [x] Populated game_count_spread_by_age_group in season_planner.py by grouping per-team counts by age_group during the existing loop and computing max-min spread within each group. — 2026-06-21
  - Files: tournament_scheduler/season_planner.py
  - Approach: After building `public_team_game_counts` (line ~325), group counts by `team.age_group` using `self.roster.by_age_group()` or by filtering `public_team_game_counts` keys against teams per age group. Compute spread (max - min) within each age group and store in `plan.game_count_spread_by_age_group`. Keep the global `plan.game_count_spread` update but derive it as `max(per_age_group_spreads.values())` so it still reflects the worst-case group.

- [x] Replaced global spread check with per-age-group spread calculation so U7 is only compared against U7, not against U12. — 2026-06-21
  - Files: tournament_scheduler/warnings.py
  - Approach: In `scan_game_count_warnings`, replace the global `max(planner._team_game_counts.values()) - min(...)` with a loop over `planner.roster.age_groups()`, grouping `planner._team_game_counts` entries by age group and computing and comparing spread per group. Emit one warning entry per age group that exceeds the threshold, naming the affected age group in the message.

- [x] Replaced flat max/min team lookup in generate_critic_summary with per-age-group loop using game_count_spread_by_age_group; each age group with spread > 4 emits its own issue naming the outlier teams within that group. — 2026-06-21
  - Files: tournament_scheduler/cli/plan_critic.py
  - Approach: In `generate_critic_summary`, replace the flat `max(team_game_counts, ...)` / `min(team_game_counts, ...)` lookup with a loop over age groups (inferred from the SeasonPlan or from team keys). For each age group where spread exceeds 4, emit a separate outlier entry naming the age group and the offending teams within it.

- [x] Added per-age-group spread recomputation after manual adjustments in manual_adjustment_workflow.py, mirroring the logic in season_planner.py. — 2026-06-21
  - Files: tournament_scheduler/pipeline/manual_adjustment_workflow.py
  - Approach: In lines 309-311, after updating `plan.game_count_spread`, also recompute `plan.game_count_spread_by_age_group` using the same per-age-group grouping logic added in season_planner.py. Extract the grouping logic into a shared helper if needed to avoid duplication.

- [x] When game_count_spread_by_age_group is populated the table caption now shows per-group spreads (e.g. 'U7: 1, U12: 3 kamper'); falls back to the global spread display when the field is absent. — 2026-06-21
  - Files: tournament_scheduler/utils/rich_output.py
  - Approach: In the game count spread display block (line ~496), replace `plan.game_count_spread` with per-age-group output when `plan.game_count_spread_by_age_group` is populated, showing each age group's spread on its own line with the group label.

- [ ] Add/update tests to validate per-age-group spread scoping
  - Files: tests/test_season_planner.py, tests/test_warnings.py
  - Approach: Add a test with a two-age-group roster (e.g. U7 and U12) where U7 teams have equal game counts but U12 teams have a large imbalance — verify the warning fires only for U12 and not U7, and that the global spread is not inflated by comparing across groups. Run `pytest` to confirm all tests pass.

## Notes

Constraints: none

Key context:
- fairness_scoring.py already correctly groups by age_group — use it as a reference for the grouping pattern.
- The global `game_count_spread` field on SeasonPlan is serialized to checkpoint JSON (stage3_helpers.py:70) and deserialized in stage4_helpers.py:71 and tournament_updater.py:122 — keep it populated (as max of per-group values) to avoid breaking downstream serialization.
- `rules_report.py` references `max_game_count_spread` threshold in Norwegian text (lines 127, 136) — the text does not need to change, only the runtime check.
- `participant_selection.py` also uses `planner.max_game_count_spread` (line 207) — verify this is a threshold reference and not a spread computation before touching it.

## Acceptance Criteria

- [ ] Running `pytest tests/test_season_planner.py tests/test_warnings.py` passes with a test that has two age groups where only one group has an imbalance, and the warning output contains only that group's label.
- [ ] The game count warning output produced by `scan_game_count_warnings` does not contain team names from different age groups in the same spread comparison.
- [ ] The critic summary generated by `generate_critic_summary` reports game count spread violations per age group and does not compare a U7 team against a U12 team as max/min pair.
- [ ] `plan.game_count_spread_by_age_group` is not empty after plan generation and has one entry per age group present in the roster.
- [ ] Running `pytest` passes with no regressions across the full test suite.

## Log

<!-- PS:next appends entries here after each task is executed -->

### 2026-06-21 — Added game_count_spread_by_age_group: Dict[str, int] field to SeasonPlan with doc comment explaining its purpose.
**Rationale:** none
**Findings:** New field is a Dict[str, int] with default empty dict; doc comment explains max-min spread scoped per age group.
LESSONS: none
**Files:** tournament_scheduler/models.py (+6/-0)
**Commit:** e4a3353 (hockey)

### 2026-06-21 — Populated game_count_spread_by_age_group in season_planner.py by grouping per-team counts by age_group during the existing loop and computing max-min spread within each group.
**Rationale:** none
**Findings:** global game_count_spread is now derived as max of per-age-group spreads so the worst-case group still surfaces.
LESSONS: none
**Files:** tournament_scheduler/season_planner.py (+16/-2)
**Commit:** b8162d0 (hockey)

### 2026-06-21 — Replaced global spread check with per-age-group spread calculation so U7 is only compared against U7, not against U12.
**Rationale:** none
**Findings:** Warnings now loop per age_group using planner.roster.teams grouped by age_group; each group's max-min spread is compared against max_game_count_spread independently.
LESSONS: none
**Files:** tournament_scheduler/warnings.py (+20/-8)
**Commit:** 743ec48 (hockey)

### 2026-06-21 — Replaced flat max/min team lookup in generate_critic_summary with per-age-group loop using game_count_spread_by_age_group; each age group with spread > 4 emits its own issue naming the outlier teams within that group.
**Rationale:** Used label-to-age-group mapping built from plan.tournaments since plan_critic has no roster access.
**Findings:** team-label-to-age-group lookup handles both plain labels and 'label (Club)' public key formats.
LESSONS: team public keys in team_game_counts may be plain 'label' or 'label (Club)' — strip parenthetical suffix before age-group lookup
**Files:** tournament_scheduler/cli/plan_critic.py (+57/-11)
**Commit:** 03dd71e (hockey)

### 2026-06-21 — Added per-age-group spread recomputation after manual adjustments in manual_adjustment_workflow.py, mirroring the logic in season_planner.py.
**Rationale:** none
**Findings:** Both game_count_spread_by_age_group and global game_count_spread are now kept in sync after manual adjustments.
LESSONS: none
**Files:** tournament_scheduler/pipeline/manual_adjustment_workflow.py (+24/-2)
**Commit:** 7b31463 (hockey)

### 2026-06-21 — When game_count_spread_by_age_group is populated the table caption now shows per-group spreads (e.g. 'U7: 1, U12: 3 kamper'); falls back to the global spread display when the field is absent.
**Rationale:** none
**Findings:** getattr with default {} guards against old checkpoint data that lacks the new field.
LESSONS: none
**Files:** tournament_scheduler/utils/rich_output.py (+11/-1)
**Commit:** [pending — fill after commit]
