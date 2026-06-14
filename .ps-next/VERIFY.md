# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: pytest -q tests/test_stage1_config.py tests/test_stage4_export.py | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/nic |
| run: bash -lc '! rg -n "derived_age_groups\|maxTeamsPerTournament\|max_teams_per_tournament" tournament_scheduler tests' | PASS | exit 0 |
| run: pytest -q tests/test_stage1_config.py tests/test_stage4_export.py -k "age_group" | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/nic |
