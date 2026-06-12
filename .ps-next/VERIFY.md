# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: pytest tests/test_pipeline_state.py | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /usr/bin/python3 |
| run: pytest | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /usr/bin/python3 |
| grep: tournament_scheduler/pipeline/state.py contains stale_from | PASS | found stale_from in tournament_scheduler/pipeline/state.py |
| grep: tests/test_pipeline_state.py contains is_stale(StageName.PLANNING) | PASS | found is_stale(StageName.PLANNING) in tests/test_pipeline_state.py |
| run: python3 - <<'PY' | PASS | exit 0 |
