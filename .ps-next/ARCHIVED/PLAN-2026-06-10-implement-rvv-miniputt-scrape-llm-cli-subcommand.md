# Plan: Implement `rvv-miniputt scrape-llm` CLI subcommand
**Goal:** `rvv-miniputt scrape-llm` is a working CLI subcommand that launches the LLM-guided browser scraper for any blocked source (BookUp SPA, StyledCalendar, etc.)
**Created:** 2026-06-10
**Intent:** The pipeline already outputs `Kjør rvv-miniputt scrape-llm for å skrape disse kildene interaktivt.` but the command doesn't exist. The `LLMGuidedScraper` class in `llm_scraper.py` (deleted from working tree, recoverable from git at 4c14ad6^) has all the machinery. We need to restore it and wire it up as a CLI subcommand.
**Backlog-ref:** 41

## Tasks
- [x] Restore `tournament_scheduler/pipeline/llm_scraper.py` from git history
  - Files: tournament_scheduler/pipeline/llm_scraper.py
  - Approach: Recover from `git show 4c14ad6^:tournament_scheduler/pipeline/llm_scraper.py`. Verify it imports cleanly against current `lm_studio_client.py` and `models.py`. Fix any import/dataclass drift since the file was deleted.

- [x] Add `scrape-llm` subcommand to `rvv_cli.py`
  - Files: tournament_scheduler/cli/rvv_cli.py
  - Approach: Add `scrape_llm` subparser with `--club` (required), `--work-dir`, `--endpoint`, `--model` flags. Implement `_cmd_scrape_llm()` that: (1) reads Stage 1 config for date range, (2) looks up the scraper strategy for the named club, (3) instantiates `LLMGuidedScraper` with the strategy URL, (4) runs the agent loop, (5) outputs event count and caches results if any. Handle the case where the source has no strategy or doesn't need LLM.

- [x] Verify end-to-end with a dry run on Sandefjord Penguins
  - Files: tournament_scheduler/pipeline/llm_scraper.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: Run `python3 -m tournament_scheduler.cli.rvv_cli scrape-llm --club "Sandefjord Penguins"` and verify it launches Playwright, navigates the BookUp SPA, and either returns events or surfaces a useful error. Test with non-strict flag.

## Notes
- `llm_scraper.py` was 905 lines and fully functional before being deleted in commit 4c14ad6 (marked "wip"). Restore it verbatim first, then fix any import drift.
- The `LLMGuidedScraper` imports `LMStudioClient` from `..llm.lm_studio_client` — verify this path still works.
- The CLI already has `scrape` (deterministic single-source scrape). `scrape-llm` is distinct — it uses the LLM agent loop for JS-rendered SPAs.
- `needs_llm_agent(strategy)` from `scraper_strategies.py` tells us which sources need this path.
- The existing `browser_worker.py` and Pi extension `scraper-agent.ts` are separate — the Python `scrape-llm` uses `LLMGuidedScraper` directly, not the TypeScript agent.
- LM Studio must be running at the configured endpoint for this to work. Surface a clear error if unreachable.

## Acceptance Criteria
- [ ] `grep:rvv_cli.py` contains `scrape-llm` as a subparser entry
- [ ] `grep:rvv_cli.py` contains `_cmd_scrape_llm` handler
- [ ] `python3 -m tournament_scheduler.cli.rvv_cli scrape-llm --help` prints usage
- [ ] `run:python3 -m tournament_scheduler.pipeline.llm_scraper` imports without error
- [ ] `run:python3 -m tournament_scheduler.cli.rvv_cli scrape-llm --club "Sandefjord Penguins"` runs without crashing (may return 0 events if LM Studio not running, but must not crash)

## Log



### 2026-06-10 — Verify end-to-end with a dry run on Sandefjord Penguins
**Done:** Dry run executed: `rvv-miniputt scrape-llm --club "Sandefjord Penguins" --max-iterations 2` — Playwright launches, navigates BookUp SPA, captures redirect to login, surfaces clear blocked message with Norwegian troubleshooting tips. No crashes.
**Rationale:** Ran `rvv-miniputt scrape-llm --club "Sandefjord Penguins" --max-iterations 2`. Command launched Playwright, navigated to BookUp, captured the login redirect, ran 2 LLM iterations, and surfaced a clear Norwegian-language blocked message. No crashes, no import errors. The output correctly shows the navigation steps, period, and useful troubleshooting tips.
**Findings:** BookUp requires authentication before the calendar is visible — the redirect to Account/Auth happens immediately. The LLM scraper correctly detects page state and reports the block. For full scraping of authenticated sources, credential support (like the Pi extension's ScraperAgent has) would be needed as a follow-up.
**Files:** tournament_scheduler/pipeline/llm_scraper.py, tournament_scheduler/cli/rvv_cli.py
**Commit:** not committed
### 2026-06-10 — Add `scrape-llm` subcommand to `rvv_cli.py`
**Done:** Added scrape-llm subparser with --club, --work-dir, --endpoint, --model, --max-iterations, --cache-results flags; _cmd_scrape_llm handler reads Stage 1 config, looks up strategy, validates LLM needed, instantiates LLMGuidedScraper, runs agent loop, caches results
**Rationale:** Added subparser with --club, --work-dir, --endpoint, --model, --max-iterations, --cache-results flags. Handler reads Stage 1 config, looks up strategy, validates LLM is needed, instantiates LLMGuidedScraper, runs the agent loop, caches results. Smoke-tested against Sandefjord Penguins — it launches Playwright, navigates to BookUp, surfaces the login redirect, and handles 0-event cases gracefully without crashing.
**Findings:** BookUp redirects to login immediately — LLM needs credentials to proceed past auth gate. The command handles this gracefully, surfacing the blocked state. The --cache-results flag writes events to the unified cache at .pipeline/cache/scraped_data.json.
**Files:** tournament_scheduler/cli/rvv_cli.py (+386/-0 lines for scrape-llm subcommand)
**Commit:** not committed
### 2026-06-10 — Restore `tournament_scheduler/pipeline/llm_scraper.py` from git history
**Done:** Recovered from git show 4c14ad6^ — all 905 lines restored verbatim. Verified import: LLMGuidedScraper, capture_dom_snapshot, LLMAction, action_from_dict all importable. CalendarEvent model compatible — no dataclass drift.
**Rationale:** File was deleted in a wip commit but the .pyc remained, confirming it was recently used. git recovery is clean — no modifications needed.
**Findings:** parse_action is named action_from_dict in the actual code — docstring mismatch but functionally correct. All imports resolve against current codebase.
**Files:** tournament_scheduler/pipeline/llm_scraper.py (+905 lines, restored from git)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
