# Plan: Add subjective weight to planning stage
**Goal:** Add subjective weight to planning stage: (1) add preferanse_vekt: float = 0.0 to the Tournament dataclass and parse it from the Excel input sheet; (2) add a new Datopreferanser sheet (fra, til, vekt columns) for global date-range penalties (e.g. Easter weekend); (3) inject both as an additive term in SeasonPlanner._score_candidate_date (positive=penalise, negative=reward); (4) cap weight magnitude and expose weight components in plan JSON and CLI summary. See .notes/improvements.md for full design sketch.
**Created:** 2026-06-19
**Intent:** Allow organizers to bias the season planner toward or away from specific dates (e.g. Easter, school holidays) by attaching per-tournament and global date-range weights that feed transparently into the scoring function.
**Backlog-ref:** 140

## Tasks
- [x] Added preferanse_vekt: float  0.0 field to Tournament dataclass in models.py. — 2026-06-19
  - Files: tournament_scheduler/models.py
  - Approach: Add `preferanse_vekt: float = 0.0` as a typed field with default to the existing Tournament dataclass, following the same pattern as `cancelled: bool = False` and `start_time: Optional[str] = None`.

- [x] Added optional preferanse_vekt column parsing in _read_age_groups (Aldersgrupper sheet); surfaced as preferanse_vekt dict in the raw config output of load_workbook_config. — 2026-06-19
  - Files: tournament_scheduler/pipeline/input_workbook.py
  - Approach: In `load_workbook_config`, detect an optional `preferanse_vekt` column in the Turneringer (or Aldersgrupper) sheet and map it to a float, defaulting to 0.0 when absent; follow the existing optional-column pattern used for `region` and `skill_level` in the Lag sheet.

- [x] Added DatePreference dataclass to models.py and _parse_datopreferanser helper in input_workbook.py; Datopreferanser sheet is now read and surfaced as 'datopreferanser' list in the raw config dict. — 2026-06-19
  - Files: tournament_scheduler/pipeline/input_workbook.py, tournament_scheduler/models.py
  - Approach: Add a new `DatePreference` datatype (fra: date, til: date, vekt: float) to models.py and add a `_parse_datopreferanser` helper in input_workbook.py that reads the new sheet's rows and returns a list of DatePreference objects; surface the list through the return value of `load_workbook_config`.

- [x] Extended _score_candidate_date with tournament_weight and date_preferences params; added date_preferences and preferanse_vekt_by_age_group to SeasonPlanner __init__; updated participant_selection.py call site to pass per-age-group weight. — 2026-06-19
  - Files: tournament_scheduler/season_planner.py
  - Approach: Extend `_score_candidate_date` to accept `tournament_weight: float = 0.0` and `date_preferences: list[DatePreference] = []`; sum any DatePreference whose fra–til range contains `candidate_date`, add both to the return value (positive = penalise, negative = reward), and cap magnitude at `max(abs(repeat_penalty), abs(month_penalty)) * 2` before adding.

- [ ] Cap weight magnitude and emit warnings for excessive weights
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/pipeline/input_workbook.py
  - Approach: In `input_workbook.py`, validate parsed vekt values against a configurable cap (read from Innstillinger sheet, default 1.0× cap multiplier) and log a warning for any value that would exceed ±2× max organic penalty; in `season_planner.py` enforce the same cap silently so runaway weights cannot dominate scoring.

- [ ] Expose weight components in plan JSON checkpoint
  - Files: tournament_scheduler/pipeline/stage3_planning.py, tournament_scheduler/models.py
  - Approach: Add `date_preference_weights: List[Dict]` to SeasonPlan and a `scoring_weight_term: float` field to Tournament; populate both during planning, then serialize them in `_plan_to_dict` alongside the existing `diversity_score` and `month_balance_score` fields.

- [ ] Show weight components in CLI summary
  - Files: tournament_scheduler/utils/rich_output.py
  - Approach: In `TournamentOutput.print_diversity_summary`, add a new section to the existing Rich Panel that lists any active global date-range penalties from `plan.date_preference_weights` and the per-tournament weight terms, following the style used for arena counts and arena/day collisions.

- [ ] Add unit tests for weight injection and capping
  - Files: tests/test_season_planner.py
  - Approach: Add test cases to the existing `_score_candidate_date` test suite that verify: a positive tournament weight increases the returned score, a negative weight decreases it, a weight exceeding the cap is clamped, and a DatePreference whose range does not contain the candidate date has no effect.

## Notes
The weight cap should be computed relative to the organic penalties already present in `_score_candidate_date` (repeat penalty + month penalty) so that the subjective weight can influence but not override the structural constraints. All new fields must default safely so existing `input.json`-only runs continue to work unchanged.

## Acceptance Criteria
- [ ] When a Tournament dataclass is loaded from Excel input, it contains a preferanse_vekt field with default value 0.0 and the value is read from the optional column in the sheet.
- [ ] When a Datopreferanser sheet is present in the Excel input, load_workbook_config produces a list of date-range penalty objects with fra, til, and vekt fields.
- [ ] When SeasonPlanner._score_candidate_date is called with a non-zero tournament weight or a matching date preference, it returns a score that differs from the base score by the capped weight term.
- [ ] When the plan JSON checkpoint is written, it contains preferanse_vekt per tournament and the list of active global date-range penalties.
- [ ] The pytest suite passes with no regressions after the new unit tests for weight injection, date-range matching, and cap enforcement are added.

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-19 — Added preferanse_vekt: float  0.0 field to Tournament dataclass in models.py.
**Rationale:** Simple field addition following existing pattern (cancelled: bool  False). No alternatives needed.
**Findings:** Field added successfully; all tests pass.
LESSONS: none
**Files:** tournament_scheduler/models.py (+1/-0)
**Commit:** 528503d (hockey)

### 2026-06-19 — Added optional preferanse_vekt column parsing in _read_age_groups (Aldersgrupper sheet); surfaced as preferanse_vekt dict in the raw config output of load_workbook_config.
**Rationale:** Extended _read_age_groups to return a 4-tuple adding a per-age-group float dict; absent column defaults to empty dict (0.0 effective). No alternatives needed.
**Findings:** All 529 tests pass; the new key only appears in raw config when at least one row has a non-empty preferanse_vekt value.
LESSONS: none
**Files:** tournament_scheduler/pipeline/input_workbook.py (+11/-4)
**Commit:** fd11ef6 (hockey)

### 2026-06-19 — Added DatePreference dataclass to models.py and _parse_datopreferanser helper in input_workbook.py; Datopreferanser sheet is now read and surfaced as 'datopreferanser' list in the raw config dict.
**Rationale:** Added _to_date helper to normalise openpyxl cell values (datetime, date, or string) to Python date. Missing fra/til rows are skipped; vekt defaults to 0.0.
**Findings:** All 529 tests pass; DatePreference objects are created correctly for all three date formats.
LESSONS: none
**Files:** tournament_scheduler/models.py (+14/-0), tournament_scheduler/pipeline/input_workbook.py (+47/-0)
**Commit:** 28504f0 (hockey)

### 2026-06-19 — Extended _score_candidate_date with tournament_weight and date_preferences params; added date_preferences and preferanse_vekt_by_age_group to SeasonPlanner __init__; updated participant_selection.py call site to pass per-age-group weight.
**Rationale:** Weight is capped at 2x max organic penalty (repeat+month); cap is 0 when both penalties are 0 (no structural constraints yet), so raw weight flows through uncapped at that point.
**Findings:** All season_planner and models tests pass (88 collected).
LESSONS: When both repeat_penalty and month_penalty are 0.0 (early scheduling), the cap is also 0 and raw_weight passes uncapped. This is safe since there are no structural constraints to override, but note the asymmetry.
**Files:** tournament_scheduler/season_planner.py (+25/-1), tournament_scheduler/participant_selection.py (+3/-1)
**Commit:** [pending — fill after commit]
