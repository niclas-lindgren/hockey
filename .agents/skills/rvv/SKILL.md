---
name: rvv
description: RVV Miniputt season planning pipeline for Norwegian hockey clubs. Runs a four-stage pipeline (config → scraping → planning → export) via /rvv-miniputt commands. Also contains tribal knowledge about clubs, calendar systems, login requirements, and LLM-driven browser scraping. Use when working with scraping, calendar generation, season planning, or pipeline debugging.
---

# RVV Miniputt — season planning pipeline

This skill runs the RVV Miniputt workflow for Norwegian hockey clubs: config, scraping, planning, and export.
Typical use: activate the skill with `/rvv-miniputt run`; the skill handles the command flow for you.

## Agent-callable tools

Use the `/rvv-miniputt ...` slash commands from Pi, not Bash.
If you need to trigger the pipeline from the agent, use these tools:

| Tool | Equivalent slash command |
|---|---|
| `rvv_miniputt_run` | `/rvv-miniputt run` |
| `rvv_miniputt_status` | `/rvv-miniputt status` |
| `rvv_miniputt_logs` | `/rvv-miniputt logs` |
| `rvv_miniputt_calendars` | `/rvv-miniputt calendars` |

Each tool takes the same flags as its slash command via an optional `args` string
(e.g. `rvv_miniputt_run({ args: "--resume-from 2 --log-level verbose" })`).

## Non-Pi / cross-harness usage

When you are not running inside Pi, use the harness-neutral repo entrypoints instead of Pi slash commands:

```bash
scripts/rvv-miniputt status
scripts/rvv-miniputt logs list --count 5
scripts/rvv-miniputt run --resume-from 2 --log-level verbose
# or
python3 -m tournament_scheduler.cli.rvv_cli status
```

These commands are intended for Codex, Claude, OpenCode, or a normal shell. They expose the repo workflow directly without requiring Pi's command registry.

## Pi-only boundary

The following remain Pi-specific adapters on top of the repo workflow:

- `/rvv-miniputt ...` slash-command dispatch itself
- `rvv_miniputt_*` agent-callable tool registration
- `/rvv-miniputt guide` interactive wizard UX
- live Pi notifications/status updates during `/rvv-miniputt run`

## How to use it

1. Activate the skill with `/rvv-miniputt run`
2. Use `/rvv-miniputt status` or `/rvv-miniputt logs` to inspect results
3. Use `/rvv-miniputt calendars` when you want calendar output from cache

## Slash commands

| Command | Description |
|---|---|
| `/rvv-miniputt run` | Run the full pipeline (config → scraping → planning → export) |
| `/rvv-miniputt run --resume-from 3` | Resume from stage 3 (planning) |
| `/rvv-miniputt run --log-level verbose` | Run with verbose logging |
| `/rvv-miniputt status` | Show status of all four stages |
| `/rvv-miniputt logs list` | Show last 10 runs |
| `/rvv-miniputt logs show latest` | Show details for the latest run |
| `/rvv-miniputt logs stats` | Show self-improvement statistics |
| `/rvv-miniputt calendars` | Generate calendars from cache |
| `/rvv-miniputt calendars --refresh` | Force full re-scrape + calendar generation |
| `/rvv-miniputt guide` | Interactive wizard for new users |

### `run` flags

```
--input <path>        Input workbook (default: input.xlsx)
--work-dir <path>     Working directory (default: .pipeline)
--resume-from <N>     Resume from stage N (1-4)
--export-dir <path>   Export directory (default: export)
--log-level <level>   info | verbose
```

## The four stages

1. **Config** — loads `input.xlsx`, validates club configuration
2. **Scraping** — scrapes calendar sources. Two-phase:
   - *Deterministic* — direct iCal feeds, iframe-based Outlook calendars, date-param pages
   - *LLM-driven* — for blocked sources (BookUp, Forumbooking, Sportello, StyledCalendar), the **ScraperAgent** takes over
3. **Planning** — builds a season plan with constraint-solving
4. **Export** — outputs Excel, iCal, CSV, and HTML

## LLM-driven scraping (ScraperAgent)

When deterministic scraping fails for a source, the ScraperAgent in `.pi/lib/scraper-agent.ts` handles it:

1. Launches a headless Playwright browser via the Python `browser_worker.py`
2. Executes **pre-loop navigation** from the club's scraper strategy (e.g. login steps for BookUp)
3. Enters an **agent loop** (up to 25 iterations):
   - Sends a page snapshot (HTML, interactive elements, already-extracted events) to Pi's configured LLM
   - The LLM returns a JSON action: `click`, `goto`, `extract`, `done`, `wait`, or `scroll`
   - The Python worker executes the action and returns a new snapshot
   - The loop continues until the LLM returns `done` or max iterations are reached
4. All extracted calendar events are collected and written to the scraping cache

The LLM evaluates the page content, decides what to click or navigate to, and calls the built-in calendar parser (`extract`) when it finds event data. It handles dynamic SPA calendars that deterministic scrapers can't handle.

## Clubs and calendar systems

### BookUp SPA (requires login for some clubs)

**⚠️ Sandefjord Penguins — ALWAYS requires login.** The BookUp page for Bugårdshallen (`Index/4497`) is behind authentication. The ScraperAgent's initial navigation handles login automatically, but the credentials must be set as environment variables:

- `BOOKUP_EMAIL` — BookUp account email
- `BOOKUP_PASSWORD` — BookUp account password

If these are not set, the pipeline prompts interactively during scraping. Without them, Sandefjord scraping will fail.

**Tønsberg** also uses BookUp but does *not* require login — the "Se tilgjengelighet" button is publicly accessible.

### All clubs

| Club | System | Scraping method | Notes |
|---|---|---|---|
| Kongsberg (ishall) | Outlook iframe | Deterministic | Works without LLM |
| Kongsberg (ballhall) | Outlook iframe | Deterministic | Works without LLM |
| Skien | Date param (brp.exigo.no) | Deterministic | `?date=YYYY-MM-DD` |
| Ringerike | Teamup iCal | Deterministic | Pure iCal feed |
| Frisk Asker | Teamup iCal | Deterministic | iCal feed |
| Tønsberg | BookUp SPA | Deterministic + LLM | Public availability view |
| **Sandefjord Penguins** | **BookUp SPA** | **LLM-driven** | **Requires `BOOKUP_EMAIL` + `BOOKUP_PASSWORD`** |
| Jar | Forumbooking | LLM-driven | HTML schema viewer with JS navigation |
| Holmen | Sportello | LLM-driven | SPA booking widget |
| Jutul / Bærum ishall | StyledCalendar | LLM-driven | JS widget |

## Running with a local LLM

The ScraperAgent uses Pi's currently configured model (`ctx.model`) for the agent loop. You can use a local model via LM Studio, Ollama, or any OpenAI-compatible endpoint — just configure it as a provider in Pi.

### Model requirements

The agent loop is demanding. The model must:
- **Follow JSON-only output instructions** — every response must be a raw JSON object with no surrounding text, markdown fences, or explanations
- **Parse HTML snapshots** — up to 3000 characters of page HTML + iframe HTML + interactive element lists, all in Norwegian
- **Make navigation decisions** — choose from `click`, `goto`, `extract`, `done`, `wait`, `scroll` based on what it sees on the page
- **Handle Norwegian content** — the system prompt, page content, and club names are all in Norwegian

### Recommended local models

Models known to work for the agent loop (≥8B parameters recommended):
- **Qwen 2.5 14B/32B** — strong JSON output discipline, handles Norwegian well
- **Llama 3.1 8B/70B** — good instruction following, but may wrap JSON in markdown fences
- **Mistral Nemo 12B** — decent multilingual support
- **Gemma 3 12B/27B** — good JSON mode

Models likely to struggle:
- **<7B parameter models** — often fail to parse HTML snapshots correctly
- **Models without JSON mode** — will frequently produce invalid JSON wrapped in prose
- **English-only models without multilingual training** — miss Norwegian calendar content

### How the agent handles LLM failures

The ScraperAgent is resilient to individual failures:
- If the LLM returns invalid JSON, the iteration is skipped and the loop continues
- If the LLM throws an API error, the agent tries a **generic fallback**: click "next month" button (for iframe calendars) and continue
- After all 25 iterations are exhausted, whatever events were collected so far are used

However, if the LLM consistently fails, the agent loop produces no useful events and the blocked sources remain unscraped.

### Testing if your local model works

Run a targeted scrape of a single blocked source to see if your model can handle the agent loop:

```bash
# In a Pi session with your local model active:
/rvv-miniputt run --resume-from 2
```

Then check the log:

```bash
/rvv-miniputt logs show latest
```

Look for lines like `Jar: 45 events funnet` vs `Jar: 0 events funnet`. If blocked sources consistently return 0 events, the local model is not capable enough for the agent loop.

### Workarounds for weak local models

1. **Swap models for scraping** — use a cloud model (e.g. Gemini Flash, Claude Haiku) for the `/rvv-miniputt run` that does scraping, then switch back to local for everything else
2. **Deterministic-only run** — skip the LLM-driven scraping entirely by using only the `--resume-from 3` flag. This runs planning/export using whatever cached data already exists from a previous cloud-model run
3. **Pre-populate cache** — run the full pipeline once with a capable cloud model to populate `.pipeline/cache/scraped_data.json`, then subsequent runs can use `--resume-from 3` with a local model

## Troubleshooting

### Pipeline fails on scraping

```bash
# Check which sources were blocked (i.e. need LLM scraping)
cat .pipeline/stage2_scraping.json | python3 -m json.tool | grep blocked

# View the latest run log
/rvv-miniputt logs show latest
```

### Sandefjord failures

Almost always a missing login. Verify:
1. `BOOKUP_EMAIL` and `BOOKUP_PASSWORD` are set in the environment
2. The BookUp account is active and can access Sandefjord's calendar
3. Re-run scraping only: `/rvv-miniputt run --resume-from 2`

### Stale calendar data

```bash
/rvv-miniputt calendars --refresh
```

This forces a full re-scrape instead of using cached data.

### Checkpoints for resumption

The pipeline saves checkpoints in `.pipeline/`:
- `stage1_config.json` — after config
- `stage2_scraping.json` — after scraping (includes blocked sources)
- `stage3_planning.json` — after planning
- `stage4_export.json` — after export

Resume from any stage with `--resume-from N`.

### Claude Code: stage-by-stage orchestration

When running inside Claude Code (not Pi), invoke each stage individually and review its checkpoint before proceeding. This mirrors the inter-stage pause logic in Pi's `pipeline-runner.ts`.

**Stage 1 — Config**

```bash
python3 -m tournament_scheduler.pipeline.stage1_config [--input input.xlsx] [--work-dir .pipeline]
```

After Stage 1 completes, read the checkpoint and the full merged config before continuing:

```bash
# Human-readable summary of the checkpoint
python3 -m tournament_scheduler.cli.checkpoint_printer stage1

# Full merged config including fields from input.xlsx that are not stored in the checkpoint
python3 -c "
from tournament_scheduler.pipeline.stage1_config import load_effective_config
import json, pprint
pprint.pprint(load_effective_config('.pipeline'))
"
```

`load_effective_config` returns the merged view with these fields relevant to semantic checks:
- `start_date` — season start (from input.xlsx)
- `end_date` — season end (from input.xlsx)
- `teams` — list of `{club, label, age_group}` dicts
- `age_groups` — list of active age group strings
- `parallel_games` — dict of age group → simultaneous games per time slot
- `target_tournament_count` — desired tournaments per team (integer or `null`)
- `sources` — list of calendar sources to scrape

Verify the checkpoint before continuing:
- `teams` is non-empty and contains all 9 RVV clubs
- `age_groups` is populated
- `parallel_games` config is present
- `target_tournament_count` ≥ 1
- `sources` list is non-empty

## Semantic validation (Stage 1)

After reading the effective configuration, perform semantic validation to ensure tournament feasibility before advancing to Stage 2. For each age group in the configuration:

1. **Count available weekends** — iterate every Saturday from `start_date` to `end_date` (inclusive) and subtract any that fall on Norwegian public holidays. This gives the pool of usable tournament weekends.
2. **Count teams per age group** — filter the `teams` list by `age_group` and count the entries.
3. **Estimate teams per tournament** — use `parallel_games[age_group] × 2` as a lower bound (each simultaneous game needs 2 teams; actual tournament size may be larger).
4. **Compute required tournaments** — `ceil(target_tournament_count × teams_in_age_group / teams_per_tournament)`.
5. **Flag overcommitment** — if `required_tournaments > available_weekends` for an age group, that is a semantic error.

The harness should reason through these calculations inline using the actual values from `load_effective_config`, performing weekend counting and arithmetic directly before deciding whether to proceed.

**Check: parallel_games feasibility**

For each age group:
- Count the number of distinct clubs represented in `teams` for that age group.
- Flag if `parallel_games[age_group] > distinct_clubs_in_age_group` — you cannot run more simultaneous games than there are clubs available to field teams.

**Check: minimum team count**

For each age group:
- Count `teams_in_age_group`.
- Flag if `teams_in_age_group < 2` — a tournament requires at least 2 teams to be meaningful.

**Check: age groups with zero teams**

- List all age group strings from the `age_groups` field of the effective config.
- For each age group in that list, check whether at least one entry in `teams` has a matching `age_group` value.
- Flag any age group that appears in `age_groups` but has no corresponding team records — this is a semantic error that will cause planning to produce an empty schedule for that age group.

**Escalation: semantic failures block Stage 2**

If any of the above checks flag an issue, **do not proceed to Stage 2**. Instead:

1. Print a plain-language summary of each issue in Norwegian. Examples:
   - `Aldergruppe JU10: 24 turneringer kreves men bare 18 helger tilgjengelig (start: 2025-09-01, slutt: 2026-04-30)`
   - `Aldergruppe U7: parallel_games=5 men bare 4 klubber er representert`
   - `Aldergruppe U12: minst 2 lag kreves, men bare 1 lag er registrert`
   - `Aldergruppe JU11: oppført i age_groups men ingen lag er registrert`
2. Instruct the user to correct `input.xlsx` and re-run Stage 1 (`python3 -m tournament_scheduler.pipeline.stage1_config`).
3. Stop — do not invoke any Stage 2 commands.

If all checks pass, proceed to Stage 2 as normal.

**Stage 2 — Scraping**

```bash
python3 -m tournament_scheduler.pipeline.stage2_scraping [--work-dir .pipeline] [--force-refresh] [--non-strict] [--allow-missing-sources]
```

Read `.pipeline/stage2_scraping.json` and verify before continuing:
- `sources` contains scraped events for the expected clubs
- `blocked` list is empty (or user has approved the missing sources)
- Note any `cached` sources that were not re-fetched

**Stage 3 — Planning**

```bash
python3 -m tournament_scheduler.pipeline.stage3_planning [--work-dir .pipeline]
```

Read `.pipeline/stage3_planning.json` and verify before continuing:
- `plan` is present and contains a non-empty list of tournaments
- Each tournament has a date, host club, and age group
- No two tournaments with overlapping player pools share a weekend
- `rules_report` shows no critical violations

**Stage 4 — Export**

```bash
python3 -m tournament_scheduler.pipeline.stage4_export [--work-dir .pipeline] [--export-dir export] [--no-timestamped-export]
```

Read `.pipeline/stage4_export.json` and report:
- Files written under `export/` (or the timestamped subfolder)
- Any `errors` in the checkpoint

**Checkpoint review helper**

Pretty-print any checkpoint in compact human-readable form:

```bash
python3 -m tournament_scheduler.cli.checkpoint_printer stage1
python3 -m tournament_scheduler.cli.checkpoint_printer stage2
python3 -m tournament_scheduler.cli.checkpoint_printer stage3
python3 -m tournament_scheduler.cli.checkpoint_printer stage4
```

## Output files

After a successful run:
- `export/calendars.html` — interactive calendar viewer
- `export/season_plan.html` — season plan HTML
- `export/season_plan.xlsx` — season plan Excel
- `.pipeline/logs/run-<date>.jsonl` — structured run log

## Project layout

```
.pi/extensions/rvv-miniputt.ts   # Extension — slash commands
.pi/lib/pipeline-runner.ts       # Pipeline orchestration
.pi/lib/pipeline-helpers.ts      # Helpers
.pi/lib/pipeline-logger.ts       # Structured logging
.pi/lib/scraper-agent.ts         # LLM-driven browser scraper
.pi/lib/interactive-guide.ts     # Interactive wizard
.pi/lib/log-inspector.ts         # Log viewing and stats
.pi/lib/parsers.ts               # Argument parsing
.pi/lib/types.ts                 # Type definitions

tournament_scheduler/pipeline/         # Python pipeline stages
tournament_scheduler/pipeline/scraper_strategies.py  # Per-club strategies
tournament_scheduler/pipeline/browser_worker.py      # Playwright browser worker
```

## Python environment

The pipeline runs Python from `venv/bin/python3`. If no venv exists, it falls back to the system `python3`. All Python modules live under `tournament_scheduler/`.
