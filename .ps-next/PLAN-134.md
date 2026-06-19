# Plan: Add duplicate label detection in _validate_team_list
**Goal:** Add duplicate label detection in stage1_helpers._validate_team_list — two teams with the same label cause silent collisions in stage3's _find_team lookup.
**Created:** 2026-06-19
**Intent:** Prevent silent data corruption in stage3 planning caused by two teams sharing the same label, which makes _find_team always return the first match and silently discard the second.
**Backlog-ref:** 134

## Tasks
- [x] Added duplicate label detection to _validate_team_list — after the per-team loop, collects labels from valid dict teams, detects duplicates via a dict, and appends a Norwegian error message naming the duplicate label and conflicting team indices. — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tournament_scheduler/pipeline/stage1_helpers.py
  - Approach: After the per-team loop, collect all label values (skipping teams that failed the `isinstance` check), use a `Counter` or `seen` set to detect duplicates, and append a Norwegian-language error for each duplicate label in the same pattern as existing errors (e.g., "duplikat 'label': Lag #1 og Lag #3 har samme etikett.").
- [x] Added two tests to TestValidateConfig: test_duplicate_label_produces_norwegian_error (verifies a Norwegian 'duplikat' error is present when two teams share a label) and test_unique_labels_no_extra_errors (confirms the baseline valid config still returns no errors). — 2026-06-19
  - Files: /Users/niclasl/src/hockey/tests/test_stage1_config.py
  - Approach: Add a test in `TestValidateConfig` that calls `validate_config(_make_valid_raw_with_duplicate_labels(), _DUMMY_INPUT_PATH)` and asserts the returned errors list is non-empty and contains a Norwegian string indicating a duplicate label; follow the same assert pattern as `test_unknown_age_group_in_team`.

## Notes
- Error messages must be in Norwegian to match the existing style in stage1_helpers.py.
- The fix is purely additive — no changes to stage3_helpers._find_team are required; the goal is to block duplicate labels before they reach stage3.
- Constraints: none

## Acceptance Criteria
- [ ] When two teams with the same label are provided, `_validate_team_list` returns a non-empty list containing a Norwegian error message that includes the duplicated label string.
- [ ] `validate_config` called with a team list containing duplicate labels produces at least one error, so the config is rejected before reaching stage3.
- [ ] `pytest tests/test_stage1_config.py` passes with a new test that asserts a Norwegian duplicate-label error is present when two teams share a label.
- [ ] A valid config with all unique team labels has no additional errors introduced by this change — `validate_config` still returns an empty list for the baseline `_make_valid_raw()` fixture.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Added duplicate label detection to _validate_team_list — after the per-team loop, collects labels from valid dict teams, detects duplicates via a dict, and appends a Norwegian error message naming the duplicate label and conflicting team indices.
**Rationale:** Purely additive change; existing 28 tests all still pass.
**Findings:** Duplicate labels now produce a Norwegian error before reaching stage3.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage1_helpers.py (+14/-0)
**Commit:** e202edc (hockey)

### 2026-06-19 — Added two tests to TestValidateConfig: test_duplicate_label_produces_norwegian_error (verifies a Norwegian 'duplikat' error is present when two teams share a label) and test_unique_labels_no_extra_errors (confirms the baseline valid config still returns no errors).
**Rationale:** Following same assert pattern as test_unknown_age_group_in_team.
**Findings:** 30 tests pass; both new tests verify the acceptance criteria.
LESSONS: none
**Files:** tests/test_stage1_config.py (+16/-0)
**Commit:** [pending — fill after commit]
