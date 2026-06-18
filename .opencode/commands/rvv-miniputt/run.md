Run the RVV Miniputt pipeline from this repository.

Rules:
- Never run `/rvv-miniputt ...` as a shell command.
- Use `scripts/rvv-miniputt run <user-args>`.
- If that fails because the launcher is unavailable, retry with `python3 -m tournament_scheduler.cli.rvv_cli run <user-args>`.
- Report the actual command used and summarize the result.
- Do not reimplement the pipeline by calling `tournament_scheduler.pipeline.stageN_*` modules directly.
- If stage 2 reports blocked sources, use `/rvv-miniputt:scrape-llm` per blocked club, then resume with `--resume-from 3`.

Flags:
```
--input <path>              Input workbook (default: input.xlsx)
--work-dir <path>           Pipeline work directory (default: .pipeline)
--resume-from <N>           Resume from stage N or alias (1-4, config, scraping, planning, export)
--export-dir <path>         Export directory (default: export)
--log-level <level>         info | verbose (default: info)
--force-refresh             Clear calendar cache before stage 2
--non-strict                Continue on blocked sources or warnings
--allow-missing-sources     Treat blocked sources as operator-approved and keep partial results
--timestamped-export        Write exports to a timestamped subfolder
```

Examples:
- `scripts/rvv-miniputt run`
- `scripts/rvv-miniputt run --resume-from 2 --log-level verbose`
- `scripts/rvv-miniputt run --non-strict --allow-missing-sources`
- `scripts/rvv-miniputt run --force-refresh`
