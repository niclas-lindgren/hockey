# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `season_plan_report.html` shows an executive summary, clear status cards, prioritized warnings/actions, per-age-group summary, per-club review summary, and detailed tournament/diagnostic content in that order. | PASS | `tests/test_stage4_export.py` asserts `id="reportOverview"`, `Kan planen brukes?`, prioritized actions, age-group summary, club review summary, tournament review table, and diagnostics intro are present and ordered before raw diagnostics. |
| Critical warnings/actions are visible before raw fairness metrics in the report HTML. | PASS | Regression assertion checks `Hva må sjekkes eller endres?` appears before `Spredning (motstandervariasjon)` in the generated report HTML. |
| Low-level diagnostics remain available but secondary on the report page. | PASS | Existing assertions keep `Rettferdighetskontroll`, `Rettferdighetsjusteringer`, and `Kvalitetsgjennomgang` present; new assertions require `Detaljerte måltall og kontroller` before those diagnostics. |
| `pytest tests/test_stage4_export.py` passes. | PASS | Ran `pytest tests/test_stage4_export.py -q` → 14 passed. |

Note: full `python3 -m pytest -q` currently fails in unrelated pre-existing planner tests (`tests/test_season_planner.py::TestProportionalHosting::test_hosting_warnings_property_returns_list` and `tests/test_stage3_planning.py::TestRunStage3::test_duplicate_labels_are_disambiguated_in_counts`).
