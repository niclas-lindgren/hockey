# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| pytest.ini contains registered slow and integration markers and default addopts exclude them. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Canonical full-planner tests in tests/test_stage3_planning.py, tests/test_season_planner.py, and tests/test_rules_report_doc.py are marked slow. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Pipeline subprocess integration tests in tests/test_claude_orchestration.py are marked integration. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| .pi/extensions/pi-next.ts runs quick/standard Python quality gates without slow/integration tests and full quality gates with the full pytest suite. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| run: python3 -m pytest -q tests/test_stage3_planning.py tests/test_season_planner.py tests/test_rules_report_doc.py -m "not slow and not integration" --no-cov | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/nic |
| run: python3 -m pytest -q tests/test_pi_next_skill_boundary.py --no-cov | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/nic |
