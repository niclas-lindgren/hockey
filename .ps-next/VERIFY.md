# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: make registered-teams CSV=/tmp/rvv-registered-teams-empty.csv ARGS='--export-dir /tmp/rvv-registered-teams-review --generated-at 2026-07-30T12:00:00Z --no-base-latest' | PASS | exit 0; generated `/tmp/rvv-registered-teams-review/registered-teams/pameldte-lag.html` and `pameldte-lag.json` without publishing. |
| run: python3 -m pytest tests/test_registered_teams.py tests/test_registered_teams_publish.py tests/test_pages_bundle.py | PASS | exit 0; 35 passed. |
| Makefile contains registered-teams-publish target (grep: Makefile:registered-teams-publish) | PASS | `rg -n "registered-teams-publish" Makefile` found target at `Makefile:143` and help text at `Makefile:62`. |
| README.md contains Påmeldte lag operator guidance (grep: README.md:Påmeldte lag) | PASS | `rg -n "Påmeldte lag" README.md` found operator table/guidance at `README.md:36-52`. |
| CLI parser contains registered-teams command (grep: tournament_scheduler/cli/args.py:registered-teams) | PASS | `rg -n "registered-teams" tournament_scheduler/cli/args.py` found parser command at `args.py:59-61`. |
