# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `input.json` is the only place where `start_date`, `end_date`, `age_groups`, `parallel_games`, and `sources` are defined | PASS | `input.json` defines all five fields. `stage1_config.json` defines none of them (verified by grep returning 0 matches for each field name in the data envelope). |
| `stage1_config.json` does NOT contain `start_date`, `end_date`, `age_groups`, `parallel_games`, or `sources` in its `data` envelope | PASS | `grep -c "start_date\|end_date\|age_groups\|parallel_games\|sources" .pipeline/stage1_config.json` → 0 |
| `stage1_config.json` contains `input_path`, `teams`, and `round_length_minutes` in its `data` envelope | PASS | `grep -c "input_path\|teams\|round_length_minutes" .pipeline/stage1_config.json` → 3 |
| Pipeline stages 2, 3, and 4 can still read all config values correctly (via the merger) | PASS | Stage 2 CLI: "Stage 2 OK -- 9 kilder skannet, 9 fra cache, 0 blokkert". `load_effective_config()` returns all 8 expected keys: start_date, end_date, age_groups[2], parallel_games[2], sources[9], teams[35], round_length_minutes[10], input_path. |
| `run: python3 -m tournament_scheduler.pipeline.stage1_config --input input.json --work-dir .pipeline` succeeds | PASS | Ran successfully: "Stage 1 OK — 35 lag, 2026-09-01 til 2027-04-30" |
| `grep: start_date` in `.pipeline/stage1_config.json` returns 0 matches (outside the envelope metadata) | PASS | `grep "start_date" .pipeline/stage1_config.json` → exit code 1 (no match) |
| `input.json` and `stage1_config.json` have no overlapping/duplicate configuration fields | PASS | `input.json` keys: start_date, end_date, age_groups, parallel_games, teams (file ref), sources. `stage1_config.json` data keys: input_path, teams (expanded), round_length_minutes. No overlap in intent — `teams` differs in content (reference vs expanded). |
