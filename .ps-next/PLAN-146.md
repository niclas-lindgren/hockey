# Plan: LLM fallback scraper for Stage 2
**Goal:** When the normal scraping script fails or returns zero events for a source, attempt to scrape that source using the LLM (via StrategyDrivenScraper) before marking it as blocked; integrate as a per-source fallback inside the Stage 2 loop with a --no-llm-scrape flag; surface LLM-scraped sources distinctly in CLI output and checkpoint so confidence assessment can weight them appropriately.
**Created:** 2026-06-18
**Intent:** Recover blocked calendar sources automatically during Stage 2 so the pipeline produces a more complete event set without manual intervention.
**Backlog-ref:** 146

## Tasks
- [x] Added no_llm_scrape parameter to run() and LLM fallback loop that retries blocked sources with StrategyDrivenScraper after the ThreadPoolExecutor block. — 2026-06-18
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/llm_scraper.py
  - Approach: Add `no_llm_scrape: bool = False` parameter to `run()`. After the ThreadPoolExecutor finishes (after the `for future in as_completed(...)` block), iterate over `source_results` for entries where `blocked=True` and `llm_fallback=True`. For each, when `no_llm_scrape=False`, instantiate `StrategyDrivenScraper` (from `llm_scraper.py`) and call `run(url, name, start_date, end_date, initial_navigation=..., month_selector=..., event_pattern=...)` using fields from `source_result["llm_strategy"]`. If it returns events, update the source_result in-place: set `blocked=False`, populate `events` and `event_count`, keep `llm_fallback=True`. Remove the source from `blocked` if it was added there. (`_scrape_source` already marks `llm_fallback=True` — no changes needed there.)

- [x] Added --no-llm-scrape to args.py run subparser, passed it via getattr to stage2_run() in pipeline_orchestrator.py, and added matching flag with pass-through in stage2_scraping.py __main__ block. — 2026-06-18
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: Add `--no-llm-scrape` argparse argument to the `run` subparser in `pipeline_orchestrator.py` (add `parser_run.add_argument("--no-llm-scrape", action="store_true")`). Pass `no_llm_scrape=args.no_llm_scrape` to the `stage2_run()` call at line ~487. Also add `--no-llm-scrape` to the `__main__` CLI block in `stage2_scraping.py` so the module can be run standalone with this flag.

- [ ] Ensure the Stage 2 checkpoint records LLM-scraped sources with sufficient metadata
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: When `_scrape_source` sets `llm_fallback=True` on a successful LLM result, add a dict with at least `{name, url, event_count, fallback_reason}` to the `llm_fallback` list in the checkpoint; update the per-source result dict to include `llm_fallback_used: True` so downstream readers can distinguish it from both normal success and true blocks.

- [ ] Update scraping_confidence.py to weight LLM-scraped sources distinctly
  - Files: tournament_scheduler/pipeline/scraping_confidence.py
  - Approach: Read the `llm_fallback` list from the checkpoint and cross-reference it against `sources[].name`; pass a count of LLM-scraped sources to the LLM confidence prompt as an additional field (e.g. `llm_scraped_sources`) so the model can apply lower confidence weight to those sources in its verdict.

- [ ] Surface LLM-scraped sources distinctly in Stage 2 CLI output
  - Files: tournament_scheduler/utils/rich_output.py, tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: After the scraping loop, collect sources where `llm_fallback=True` and pass them to a Rich output helper that prints them with a yellow/amber label (e.g. "[LLM]") distinct from the green normal-success and red blocked styles already used; also add a summary line like "N source(s) recovered via LLM fallback" in the Stage 2 completion banner.

- [ ] Add unit tests for LLM fallback path, --no-llm-scrape flag, and checkpoint metadata
  - Files: tests/test_stage2_scraping.py
  - Approach: Add three test cases to `test_stage2_scraping.py`: (1) mock `StrategyDrivenScraper.run` to return events and assert `llm_fallback=True` in the source result and checkpoint `llm_fallback` list; (2) pass `llm_fallback=False` and assert the LLM scraper is never called; (3) mock the LLM scraper to return zero events and assert the source remains blocked in the checkpoint.

## Notes
Constraints: none

Key patterns:
- `_scrape_source` in `stage2_scraping.py` returns a dict with `blocked`, `llm_fallback`, `events`, `event_count` fields.
- `StrategyDrivenScraper.run(url, name, start_date, end_date)` in `llm_scraper.py` returns `list[CalendarEvent]`; use `_events_to_dicts()` from `scraper_event_helpers` to convert to the checkpoint format.
- Checkpoint `llm_fallback` list already exists as a key — just needs to be populated with real data.
- `scraping_confidence.py` reads `sources[].event_count`, `sources[].blocked` — extend it to also read the `llm_fallback` list count.
- Rich output convention: use `rich_output.py` helpers, avoid raw `print`.

## Acceptance Criteria
- [ ] When the normal scraper fails or returns zero events for a source, the pipeline produces a result dict with `llm_fallback=True` and a non-empty events list for that source (verifiable by running the Stage 2 tests with a mocked LLM scraper).
- [ ] When --no-llm-scrape is passed, the system does not call StrategyDrivenScraper and marks the source as blocked with `llm_fallback=False`.
- [ ] The Stage 2 checkpoint contains an entry in the `llm_fallback` list for each source recovered via LLM, with at least `name` and `event_count` fields.
- [ ] The CLI output shows a distinct label (e.g. "[LLM]") for LLM-scraped sources and a summary count line, not mixing them with normally succeeded or blocked sources.
- [ ] scraping_confidence.py reads the `llm_fallback` count from the checkpoint and includes it in the LLM prompt payload, so the confidence verdict has visibility into how many sources are LLM-sourced.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-18 — Added no_llm_scrape parameter to run() and LLM fallback loop that retries blocked sources with StrategyDrivenScraper after the ThreadPoolExecutor block.
**Rationale:** Straightforward addition after ThreadPoolExecutor; imported StrategyDrivenScraper from llm_scraper.py and iterated source_results for blocked+llm_fallback entries.
**Findings:** LLM fallback loop executes after main scraper loop; if StrategyDrivenScraper returns events, source is unblocked in-place and removed from blocked list.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+31/-0)
**Commit:** 6b5c25e (hockey)

### 2026-06-18 — Added --no-llm-scrape to args.py run subparser, passed it via getattr to stage2_run() in pipeline_orchestrator.py, and added matching flag with pass-through in stage2_scraping.py __main__ block.
**Rationale:** Used getattr(args, 'no_llm_scrape', False) for defensive access since args may come from different contexts.
**Findings:** Flag wired through all three touch points; no_llm_scrape defaults to False so existing behavior is unchanged.
LESSONS: none
**Files:** args.py (+5/-0), pipeline_orchestrator.py (+1/-0), stage2_scraping.py (+5/-0)
**Commit:** [pending — fill after commit]
