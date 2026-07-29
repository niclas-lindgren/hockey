# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: python3 -m pytest tests/test_activity_export.py tests/test_activity_viewer.py tests/test_stage4_export.py tests/test_pages_bundle.py tests/test_operator_action.py -q | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/nic |
| grep contains: docs/rvv-miniputt-pipeline.md Aktivitetskalender | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The export pipeline reads only the intended activity table and excludes example/help data. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| It writes valid normalized activities.json and standalone activities/index.html artifacts when an activity sheet exists. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The activity page supports date-positioned year-wheel, chronological month-grouped list, age-group filtering, keyboard/touch/mouse details, mobile list default, and responsive iframe embedding. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Timestamped and latest Pages publishing include the activity artifacts while existing plan, calendar, report, and input exports continue to pass tests. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
