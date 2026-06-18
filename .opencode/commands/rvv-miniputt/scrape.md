Scrape a single club's calendar source and report the result.

Rules:
- Never run `/rvv-miniputt ...` as a shell command.
- Use `scripts/rvv-miniputt scrape --club "<name>" <user-args>`.
- Fallback if needed: `python3 -m tournament_scheduler.cli.rvv_cli scrape --club "<name>" <user-args>`.
- `--club` is required. The name must match a source in `input.xlsx` (e.g. `Jar`, `Holmen`, `Sandefjord`).
- Report the event count, whether the source was blocked, and any LLM-fallback hint.
- If the source requires LLM scraping, suggest running `/rvv-miniputt:scrape-llm`.

Flags:
```
--club <name>      Source name (required)
--work-dir <path>  Pipeline work directory (default: .pipeline)
```

Examples:
- `/rvv-miniputt:scrape --club Jar`
- `/rvv-miniputt:scrape --club "Sandefjord"`
