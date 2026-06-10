# PLAN: Fix duplicate quality metrics in season plan report (Spredning vs Nye matchups)

**Feature:** Fix duplicate quality metrics in season plan report: 'Spredning' (diversity_score) and 'Nye matchups' (pairwise_matchup_score) always show the same percentage because season_planner.py _diversity_score() simply returns _pairwise_matchup_score() (season_planner.py:1209-1222) - a leftover from a refactor. Either compute a genuinely distinct diversity metric (e.g. opponent variety per team across the season) or remove the redundant 'Spredning' label/field from the report templates and exporters.

**Goal:** 'Spredning' and 'Nye matchups' in the season plan HTML report no longer show the same percentage by definition. Either implement a genuinely distinct diversity metric for 'Spredning' (e.g. opponent variety per team across the season) or remove the redundant 'Spredning' label/field from the report templates and exporters.

**Backlog-ref:** 47

**Constraints:** none

**Date:** 2026-06-10

**Intent:** Resolve a leftover refactor bug where two distinct-sounding quality metrics in the season plan report are mathematically identical, misleading organizers about schedule quality.

## Tasks

- [x] Reworked _diversity_score to compute, per team, the ratio of distinct opponents faced (from _opponent_history) to eligible opponents (same age group, different club, per max_club_teams_per_tournament1), averaged across teams that have played; returns 0.0 if no games played. — 2026-06-10
  - Files: `tournament_scheduler/season_planner.py`
  - In `_diversity_score(self, tournaments)` (season_planner.py:1209-1222), replace `return self._pairwise_matchup_score(tournaments)` with a new computation: for each team appearing in `tournaments`, count its distinct opponents from `self._opponent_history` (keys are `frozenset` pairs of team labels) and divide by the number of "available opponents" for that team (other teams in the same age group from `self.roster.teams`, excluding same-club teams per the existing `max_club_teams_per_tournament=1` constraint, since intra-club matchups never occur). Average this ratio across all teams that played at least one game this season, rounded to 3 decimals (1.0 = every team has played every eligible opponent at least once; lower values indicate teams repeatedly facing a narrow set of opponents). Return `0.0` when no teams have played any games.

- [x] Added a field-level docstring comment for diversity_score in models.py describing the opponent-variety-per-team metric and explicitly distinguishing it from pairwise_matchup_score; the _diversity_score docstring in season_planner.py was already updated as part of the prior task's implementation. — 2026-06-10
  - Files: `tournament_scheduler/season_planner.py`, `tournament_scheduler/models.py`
  - Rewrite the `_diversity_score` docstring (season_planner.py:1209-1221) to describe the new opponent-variety-per-team calculation and remove the claim that it is "equivalent to `_pairwise_matchup_score`". Update the `diversity_score` field comment in `models.py` (near line 171, above the `pairwise_matchup_score` docstring at 172-176) to describe the new metric (opponent variety per team) as distinct from the pairwise novel-pairing fraction.

- [x] Updated scores.html: relabeled 'Spredning' to 'Spredning (motstandervariasjon)' and 'Nye matchups' to 'Nye matchups (ferske motstanderpar)', and added title tooltips on each score-item explaining the distinct underlying calculation, so the two metrics no longer appear to measure the same thing. — 2026-06-10
  - Files: `tournament_scheduler/html/templates/scores.html`
  - In `scores.html` (line 5, `Spredning: <strong>$DIVERSITY_SCORE$%</strong>`), keep the existing `$DIVERSITY_SCORE$` token (already wired in `html_exporter.py:323` to `plan.diversity_score`) but adjust the label text if needed (e.g. add a short tooltip/title attribute or adjacent text such as "Spredning (motstandervariasjon)") so it is visually distinguishable from "Nye matchups" (line 13, `$PAIRWISE_SCORE$`) now that the underlying values genuinely differ.

- [x] Reworded the diversity_score line in print_diversity_summary from 'Mangfoldscore (andel nye lagkonstellasjoner)' to 'Motstandervariasjon (andel mulige motstandere møtt)' to accurately describe opponent-pool coverage; left the pairwise_matchup_score line ('Kampmangfold (andel ferske motstanderpar)') unchanged since it already correctly describes first-time pairings. — 2026-06-10
  - Files: `tournament_scheduler/utils/rich_output.py`
  - Update the two summary lines (rich_output.py:331 and :335) so the Norwegian descriptions accurately describe each distinct metric: line 331 (`Mangfoldscore (andel nye lagkonstellasjoner)` for `plan.diversity_score`) should describe opponent-variety-per-team (e.g. "andel mulige motstandere møtt"), and line 335 (`Kampmangfold (andel ferske motstanderpar)` for `plan.pairwise_matchup_score`) should keep describing the fraction of first-time pairings — ensure the two labels no longer imply they measure the same thing.

- [x] Added test_diversity_score_returns_zero_when_no_games_scheduled (fresh planner with empty _opponent_history) and test_diversity_score_and_pairwise_score_can_diverge (4-team scenario where opponent-variety  1/3 but pairwise-novelty  0.5, asserting they differ). — 2026-06-10
  - Files: `tests/test_season_planner.py`
  - Add a test that builds a small `tournaments`/`_opponent_history` fixture where opponent-variety-per-team and pairwise-novel-pairing-fraction produce different numeric results, and asserts `_diversity_score(tournaments) != _pairwise_matchup_score(tournaments)` for that fixture. Also add a test confirming `_diversity_score` returns `0.0` when no games were scheduled, matching the existing `_pairwise_matchup_score` empty-input behavior.

- [ ] Run the full test suite and verify the HTML/console outputs render distinct values end-to-end
  - Files: `tests/test_season_planner.py`, `tournament_scheduler/season_planner.py`
  - Run `pytest` to confirm no regressions in existing tests that reference `diversity_score` or `pairwise_matchup_score` (e.g. tests covering `build_plan`, stage3/stage4 checkpoint round-trips, or HTML export). Manually verify (or add an assertion) that `plan.diversity_score` and `plan.pairwise_matchup_score` differ for a realistic multi-tournament season plan fixture.

## Acceptance Criteria

- The 'Spredning' and 'Nye matchups' fields in the season plan HTML report show different percentage values when the schedule contains varied opponent pairings, instead of always matching.
- The `_diversity_score()` function in `tournament_scheduler/season_planner.py` no longer simply returns `_pairwise_matchup_score()` and computes opponent variety per team using `_opponent_history`.
- Tests in `tests/test_season_planner.py` pass and include a case where `_diversity_score` and `_pairwise_matchup_score` return different values for the same set of tournaments.
- The console summary output from `tournament_scheduler/utils/rich_output.py` no longer describes the diversity score and pairwise matchup score with overlapping wording that implies they are the same metric.
- Running `pytest` completes with no failures related to `diversity_score`, `pairwise_matchup_score`, or season plan export/report generation.

## Log

- [2026-06-10] Plan created for backlog #47.

### 2026-06-10 — Reworked _diversity_score to compute, per team, the ratio of distinct opponents faced (from _opponent_history) to eligible opponents (same age group, different club, per max_club_teams_per_tournament1), averaged across teams that have played; returns 0.0 if no games played.
**Rationale:** Pairwise-matchup score measures repeat games while diversity score now measures opponent-pool coverage per team, so the two metrics are genuinely independent.
**Findings:** All 39 season_planner tests pass; updated test_diversity_and_month_balance_metrics_present_on_plan which previously asserted diversity_score  pairwise_matchup_score (now an outdated invariant). One pre-existing unrelated failure (test_zero_events_blocks_source) confirmed present before this change too.
LESSONS: none
**Files:** tests/test_season_planner.py (+3/-2), tournament_scheduler/season_planner.py (+50/-12)
**Commit:** 55a65d0 (hockey)

### 2026-06-10 — Added a field-level docstring comment for diversity_score in models.py describing the opponent-variety-per-team metric and explicitly distinguishing it from pairwise_matchup_score; the _diversity_score docstring in season_planner.py was already updated as part of the prior task's implementation.
**Rationale:** none
**Findings:** diversity_score field comment in models.py now accurately describes the new metric and no longer implies equivalence with pairwise_matchup_score; all 39 season_planner tests still pass.
LESSONS: none
**Files:** tournament_scheduler/models.py (+8/-0)
**Commit:** bd273a7 (hockey)

### 2026-06-10 — Updated scores.html: relabeled 'Spredning' to 'Spredning (motstandervariasjon)' and 'Nye matchups' to 'Nye matchups (ferske motstanderpar)', and added title tooltips on each score-item explaining the distinct underlying calculation, so the two metrics no longer appear to measure the same thing.
**Rationale:** The scores.html template was previously untracked and matched the repo's *.html gitignore rule; force-added it since it is a source template consumed by html_exporter.py, not a generated artifact.
**Findings:** All 14 html/export tests pass; labels and tooltips now clearly differentiate diversity_score (opponent-pool coverage) from pairwise_matchup_score (first-time pairings).
LESSONS: scores.html and other files under tournament_scheduler/html/templates/ are blocked by the repo's '*.html' gitignore rule and were untracked before this task; use 'git add -f' for any further edits to template .html files in that directory until the gitignore is fixed.
**Files:** tournament_scheduler/html/templates/scores.html (+19/-0, force-added, was gitignored by *.html)
**Commit:** e7a731d (hockey)

### 2026-06-10 — Reworded the diversity_score line in print_diversity_summary from 'Mangfoldscore (andel nye lagkonstellasjoner)' to 'Motstandervariasjon (andel mulige motstandere møtt)' to accurately describe opponent-pool coverage; left the pairwise_matchup_score line ('Kampmangfold (andel ferske motstanderpar)') unchanged since it already correctly describes first-time pairings.
**Rationale:** none
**Findings:** No tests reference the old/new label strings directly; full suite still passes (276 passed, 1 pre-existing unrelated failure in test_zero_events_blocks_source, 1 skipped).
LESSONS: none
**Files:** tournament_scheduler/utils/rich_output.py (+1/-1)
**Commit:** 2c16453 (hockey)

### 2026-06-10 — Added test_diversity_score_returns_zero_when_no_games_scheduled (fresh planner with empty _opponent_history) and test_diversity_score_and_pairwise_score_can_diverge (4-team scenario where opponent-variety  1/3 but pairwise-novelty  0.5, asserting they differ).
**Rationale:** Used a from-scratch SeasonPlanner/roster fixture rather than reusing planner_and_plan, since the latter's build_plan already populates _opponent_history nonzero, making a true 'no games' zero-score case impossible to reach via that fixture.
**Findings:** All 41 season_planner tests pass, including the two new tests confirming diversity_score and pairwise_matchup_score are independently computed and can diverge.
LESSONS: none
**Files:** tests/test_season_planner.py (+65/-0)
**Commit:** d5a30d5 (hockey)
