# Plan: Explicit skipped-age-group metadata and reporting
**Goal:** Skipped small age groups (<3 teams) are tracked with metadata, excluded from fairness metrics, and surfaced in all output formats.
**Created:** 2026-06-15
**Intent:** When an age group has fewer than MIN_TEAMS_PER_TOURNAMENT (3) configured teams, the planner currently silently skips it, but the teams still appear with 0 game counts in fairness/team_game_counts, making reports look like failures. We need explicit tracking, proper exclusion, and clear visibility.
**Backlog-ref:** 97

## Tasks
- [x] Add `skipped_age_groups` field to `SeasonPlan` model and populate it in `SeasonPlanner.build_plan()` when teams < MIN_TEAMS_PER_TOURNAMENT
  - Files: tournament_scheduler/models.py, tournament_scheduler/season_planner.py
  - Approach: Add `skipped_age_groups: List[Dict]` dataclass field to `SeasonPlan` (each entry: age_group, team_count, reason). In `build_plan()`, when `len(participants) < MIN_TEAMS_PER_TOURNAMENT`, append a skip entry instead of silently continuing. Preserve the skip in checkpoint round-trips via stage3_helpers.py and stage4_helpers.py.

- [x] Exclude skipped age groups from game-count fairness metrics and warnings
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/fairness_model.py
  - Approach: In `_scan_per_team_share_warnings()`, skip teams whose age_group is in the skipped set. In `adjustment_rows_for_plan()` (fairness_model.py), filter out skipped age groups. In `_build_fairness_gate()` and `_scan_game_count_warnings()`, exclude skipped teams from spread/fairness calculations. Also exclude them when building `plan.team_game_counts` and `plan.game_count_spread` in `build_plan()`.

- [ ] Surface skipped age groups in Rich console output
  - Files: tournament_scheduler/utils/rich_output.py
  - Approach: Add a `print_skipped_age_groups()` static method showing skip reasons. Call it from the `print_plan_summary()` or the `TournamentOutput` flow. Use a mild warning style (yellow) to indicate intentional skips.

- [ ] Surface skipped age groups in HTML season-plan report and review summary
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: In `export()`, pass `skipped_age_groups` data into the template context. Add a new review-summary finding category for skipped groups ("Aldersgrupper som er hoppet over") with skip count and reason. In the season plan table/pages, show a "Hoppet over" section listing skipped age groups.

- [ ] Surface skipped age groups in Excel review packets
  - Files: tournament_scheduler/review/review_packet_exporter.py
  - Approach: Add a "Hoppet over" sheet or an info row/list in the club review packet that lists skipped age groups and the reason, so organizers know JU12 was intentionally skipped (only 2 teams).

## Notes
- The `scheduled` list in `build_plan()` still contains (date, age_group) tuples for skipped groups — those are silently dropped. The host assignment for those date/age combos is also wasted. We could optionally avoid allocating host slots for skipped groups (improvement, not required for this task).
- The `_record_month` call happens before the skip check — this will slightly inflate month counts. Not critical but worth noting.
- Checkpoint round-trips: stage3_helpers.py serializes plan fields, stage4_helpers.py deserializes them. Need to add skipped_age_groups there.
- Backlog item #99 (team participation balancing) moved some code around `_team_game_counts` — make sure to rebase/merge cleanly.

## Acceptance Criteria
- [ ] `SeasonPlan.skipped_age_groups` is populated with entries like `{"age_group": "JU12", "team_count": 2, "reason": "Kun 2 lag konfigurert; minimum er 3"}` when an age group has <3 teams.
- [ ] `plan.team_game_counts` contains zero entries for skipped age group teams.
- [ ] `plan.game_count_spread` is computed only from non-skipped age groups.
- [ ] Fairness gate does not fail game-count spread due to intentionally skipped teams.
- [ ] Rich console output shows skipped age groups with reason.
- [ ] HTML season-plan report shows a "Hoppet over" section for skipped age groups.
- [ ] Excel review packet worksheets contain a row listing skipped age groups.
- [ ] Deserializing `stage3_planning.json` returns `skipped_age_groups` matching the original list.

## Log


### 2026-06-15 — Exclude skipped age groups from game-count fairness metrics and warnings
**Done:** Excluded skipped age groups from fairness gate (age_group_spreads computation), per-team share warnings (skipped teams excluded via parameter), and team_game_counts/game_count_spread (already done in Task 1). Fairness gate in `_build_fairness_gate` now skips age groups in `plan.skipped_age_groups`. `_scan_per_team_share_warnings` now accepts an optional skipped_age_groups parameter and excludes those teams.
**Rationale:** The skipped set is derived from `plan.skipped_age_groups` (populated in Task 1) and passed to methods that need it. The fairness gate skip is the most important change — without it, age_group_spreads would still include 0-count skipped groups (normalized to 0, so harmless, but semantically wrong).
**Findings:** `adjustment_rows_for_plan()` in fairness_model.py already excludes skipped age groups implicitly since they have no tournaments (teams_by_age_group is built from tournament teams only). `_scan_game_count_warnings` uses `self._team_game_counts` which also has no entries for skipped teams (no games generated), so it's already safe.
**Files:** tournament_scheduler/season_planner.py (+18/-3)
**Commit:** not committed
### 2026-06-15 — Add `skipped_age_groups` field to `SeasonPlan` model and populate it in `SeasonPlanner.build_plan()` when teams < MIN_TEAMS_PER_TOURNAMENT
**Done:** Added `skipped_age_groups: List[Dict]` field to `SeasonPlan` model; populated it in `build_plan()` when len(participants) < MIN_TEAMS_PER_TOURNAMENT; excluded skipped age group teams from `team_game_counts`/`game_count_spread`; added checkpoint serialization/deserialization in stage3_helpers.py and stage4_helpers.py.
**Rationale:** Followed the planned approach: added the dataclass field, recorded skip entries instead of silent continue, excluded skipped teams from fairness-relevant counts, and preserved through checkpoint round-trips.
**Findings:** `team_game_counts` is built by iterating ALL roster teams including skipped ones, causing them to get 0 counts and inflate game_count_spread. The exclusion check at the iteration site is the cleanest fix.
**Files:** tournament_scheduler/models.py (+4), tournament_scheduler/season_planner.py (+13), tournament_scheduler/pipeline/stage3_helpers.py (+1), tournament_scheduler/pipeline/stage4_helpers.py (+1)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
