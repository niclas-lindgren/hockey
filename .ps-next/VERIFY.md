# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Expected host counts are explainable per age group. | PASS | `SeasonPlanner._hosting_fairness_breakdown()` returns per-age rows with `age_group`, `club`, `teams`, `actual`, `expected`, `deviation`, and a Norwegian detail string beginning `Aldersgruppevis vertskapsfordeling`. |
| Removing or adding U10 teams does not increase U7 hosting expectation. | PASS | `tests/test_season_planner.py::TestProportionalHosting::test_host_targets_are_age_group_aware` compares U7 targets before/after adding many U10 teams and asserts both remain Kongsberg/Jar/Frisk Asker = 2 each. |
| Tests show Kongsberg/Jar/Frisk-style host counts align with per-age rosters rather than total club roster size. | PASS | `test_host_assignment_uses_per_age_rosters` asserts U7 assignments are even while U10 assigns more hosting to Jar because Jar has more U10 teams. |
| Fairness report includes per-age expected vs actual hosting breakdown. | PASS | `tests/test_stage4_export.py` asserts `Per aldersgruppe: faktisk vs forventet vertskap` and `Aldersgruppevis vertskapsfordeling...` appear in the generated report HTML. |
| `pytest tests/test_season_planner.py tests/test_stage4_export.py -q` passes. | PASS | Ran command successfully: 81 passed. |

Additional quality evidence:
- `pytest tests/test_season_planner.py -q` → 67 passed.
- `pytest tests/test_stage4_export.py -q` → 14 passed.
- Standard full-suite gate (`python3 -m pytest -q`) still fails one unrelated Stage 3 fixture: `tests/test_stage3_planning.py::TestRunStage3::test_duplicate_labels_are_disambiguated_in_counts`, where the test config has only two teams per age group and Stage 3 rejects <3-team tournaments.
