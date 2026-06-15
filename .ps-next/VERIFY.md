# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `season_plan_report.html` contains a visible all-club summary table rather than an unreachable hidden club dashboard. | PASS | `tests/test_stage4_export.py` asserts `id="clubSummary"`, `id="clubSummaryBody"`, and `Samlet klubbstatus` are present in the generated report. |
| `season_plan_report.html` does not contain schedule filter controls, count bar, or selector-only dashboard behavior. | PASS | `tests/test_stage4_export.py` asserts no report `id="timeline"`, `class="filters"`, `class="count-bar"`, `id="clubDashboard"`, hidden dashboard style, or `clubDashName` in report script. |
| `pytest tests/test_stage4_export.py` passes. | PASS | `python3 -m pytest -q tests/test_stage4_export.py` passed; full `pi_next_quality_gate(level="full")` also passed with 381 passed, 1 skipped. |
