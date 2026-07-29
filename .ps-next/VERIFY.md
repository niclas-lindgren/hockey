# Verification Report

STATUS: PASS_WITH_MANUAL_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: python3 -m pytest tests/test_activity_export.py tests/test_activity_viewer.py tests/test_stage4_export.py tests/test_pages_bundle.py tests/test_operator_action.py -q | PASS | 137 passed in 8.24s. |
| grep contains: docs/rvv-miniputt-pipeline.md Aktivitetskalender | PASS | `rg -n "Aktivitetskalender" docs/rvv-miniputt-pipeline.md` found output/artifact and WordPress embed documentation. |
| The export pipeline reads only the intended activity table and excludes example/help data. | PASS | `tests/test_activity_export.py` covers help/example row skipping, internal sheet non-exposure, and duplicate year-wheel helper/table header regression. Manual check against `Årshjul for aktiviteter.xlsx` parsed 32 intended activities without helper IDs. |
| It writes valid normalized activities.json and standalone activities/index.html artifacts when an activity sheet exists. | PASS | `tests/test_activity_viewer.py` and `tests/test_stage4_export.py` assert normalized JSON, `activities.json`, and `activities/index.html` output files. |
| The activity page supports date-positioned year-wheel, chronological month-grouped list, age-group filtering, keyboard/touch/mouse details, mobile list default, and responsive iframe embedding. | PASS | `tests/test_activity_viewer.py` inspects date-to-angle positioning, month grouping, age filter controls, keyboard activation handlers, mobile default list CSS/JS, and `rvv-activities-height` postMessage. |
| Timestamped and latest Pages publishing include the activity artifacts while existing plan, calendar, report, and input exports continue to pass tests. | PASS | `tests/test_stage4_export.py`, `tests/test_pages_bundle.py`, and `tests/test_operator_action.py` cover Stage 4 checkpoint entries, sanitized public bundle inclusion, recursive publish/diff handling, and existing export surfaces. |

Additional checks:
- `python3 -m pytest -q -m "not slow and not integration"` passed via `pi_next_quality_gate(level="quick")` after implementation.
- `pi_next_quality_gate(level="full")` / full pytest currently fails on pre-existing canonical roster/input.xlsx assumptions (empty `Lag` sheet), not on issue #33 changes: `tests/test_claude_orchestration.py::TestStage1Config::test_stage1_checkpoint_has_expected_data_keys`, `tests/test_rules_report_doc.py::test_rules_report_markdown_matches_committed_doc`, two real-roster `test_season_planner.py` cases, and two `tests/test_stage3_planning.py` canonical workbook cases.
