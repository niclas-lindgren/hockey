---
name: rvv-miniputt
description: RVV Miniputt season planning pipeline for Norwegian hockey clubs. Runs a four-stage pipeline (config → scraping → planning → export) via /rvv-miniputt commands. Also contains tribal knowledge about clubs, calendar systems, login requirements, and LLM-driven browser scraping. Use when working with scraping, calendar generation, season planning, or pipeline debugging.
---

# RVV Miniputt — season planning pipeline

The extension at `.pi/extensions/rvv-miniputt.ts` provides slash commands for execution. This skill provides tribal knowledge, usage patterns, and troubleshooting that don't belong in code.

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
--input <path>        Input JSON file (default: input.json)
--work-dir <path>     Working directory (default: .pipeline)
--resume-from <N>     Resume from stage N (1-4)
--export-dir <path>   Export directory (default: export)
--log-level <level>   info | verbose
```

## The four stages

1. **Config** — loads `input.json`, validates club configuration
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
