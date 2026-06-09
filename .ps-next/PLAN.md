# Plan: Agentic season-planning pipeline

**Intent:** Build the `rvv-miniputt` pi extension — a four-stage agentic pipeline running inside pi.dev that orchestrates the existing Python season scheduler. Each stage has an LLM quality gate. The extension is a TypeScript file at `.pi/extensions/rvv-miniputt.ts` that registers pi tools/commands and invokes the Python stage modules via `execFile`. The pipeline has resumable intermediate state and multi-format export.

**Backlog-ref:** 22
**Created:** 2026-06-09
**Goal:** Agentic season-planning pipeline — restructure the tool as a four-stage pipeline where each stage has an LLM quality gate before the next stage runs. Stage 1 (Config): parse and validate input.json — teams, clubs, age groups, date range, parallel-games config — and surface clear Norwegian-language errors on bad input. Stage 2 (Scraping): per calendar source, run the existing Playwright/iCal scraper, then pass the result to a local LLM (host.lima.internal:1234, Qwen2.5-32B-Instruct Q4_K_M via LM Studio) that evaluates 'do these look like valid ice hall bookings in the expected date range?'; on low confidence or empty result the LLM attempts its own extraction from the raw HTML; if both fail, gate blocks with a clear message ('Source X returned 0 events — scraper broken or hall closed?') rather than silently proceeding with bad data. iCal sources (Teamup, Google Calendar) skip the LLM path. Stage 3 (Planning): run the season scheduler, then LLM evaluates the output for coverage (every team plays enough games), diversity (varied opponents), and time balance (no month overloaded); can re-run scheduler with adjusted params if result looks poor, up to N retries. Stage 4 (Export): generate Excel + iCal + CSV outputs. Each stage writes its output to a structured intermediate file so the pipeline can be resumed from any stage without re-running earlier stages.
**Constraints:** none

## Tasks

- [x] Created tournament_scheduler/llm subpackage with LMStudioClient HTTP wrapper and module-level complete()/extract_confidence() helpers. — 2026-06-09
  - Files: `tournament_scheduler/llm/__init__.py`, `tournament_scheduler/llm/lm_studio_client.py`
  - Approach: Create a new `llm` subpackage with an HTTP client (using stdlib `urllib` or `httpx` if available) that POSTs to `http://host.lima.internal:1234/v1/chat/completions` with the Qwen2.5-32B model; expose a `complete(system, user, temperature)` function returning the text response and a confidence extraction helper that parses a structured JSON response from the LLM.

- [x] Created tournament_scheduler/pipeline subpackage with PipelineState class writing per-stage JSON checkpoint files; supports status tracking (pending/running/done/failed), read/write/mark_done/mark_failed helpers, and stages_to_run() for --resume-from logic. — 2026-06-09
  - Files: `tournament_scheduler/pipeline/__init__.py`, `tournament_scheduler/pipeline/state.py`
  - Approach: Create a `PipelineState` class that reads/writes JSON checkpoint files to a configurable `--work-dir` (default `.pipeline/`); one file per stage (`stage1_config.json`, `stage2_scraping.json`, `stage3_plan.json`, `stage4_export.json`) with a `status` field (`pending`, `done`, `failed`) so a `--resume-from` flag can skip completed stages.

- [x] Created stage1_config.py with run(), validate_config(), and _parse_config() covering date parsing, age group validation, parallel_games limits vs federation defaults, team list and external file references — all error messages in Norwegian. — 2026-06-09
  - Files: `tournament_scheduler/pipeline/stage1_config.py`
  - Approach: Load `input.json` (new canonical input format) using existing `RosterLoader` and `ParallelGamesConfig` from `season_config.py`; add a validation pass that emits Norwegian error messages for missing fields, invalid date ranges, unknown age groups, and parallel-games rule violations, then writes a validated config object to the Stage 1 checkpoint.

- [x] Created stage2_scraping.py with run(), per-source scraping dispatch (Playwright/iCal/Google), LLM quality gate with confidence threshold (0.6), HTML fallback extraction, and Norwegian block messages on zero events. — 2026-06-09
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`, `tournament_scheduler/data_sources/calendar_scraper.py`
  - Approach: For each Playwright/Outlook source run the existing `CalendarScraper.scrape_calendar`; expose raw HTML from the `iframe.content()` call via an optional `return_raw_html=True` param so the LLM fallback can attempt extraction; pass scraped events to `lm_studio_client.complete()` for validation; skip LLM for iCal sources (`ical_scraper.py`); block with a Norwegian message if both scraper and LLM return zero events, writing per-source results to the Stage 2 checkpoint.

- [x] Created stage3_planning.py with run(), LLM evaluation of coverage/diversity/balance (Norwegian prompts), retry loop up to MAX_RETRIES3 resetting SeasonPlanner on each attempt, and _plan_to_dict serialiser. — 2026-06-09
  - Files: `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: Call `SeasonPlanner.build_plan(start, end)` using calendar events from the Stage 2 checkpoint; pass the resulting `SeasonPlan` as JSON to `lm_studio_client.complete()` asking it to evaluate coverage, opponent diversity, and monthly load balance; if the LLM returns low confidence retry up to `MAX_RETRIES` (default 3) times with adjusted `diversity_weight` params; write the accepted plan to the Stage 3 checkpoint.

- [x] Created stage4_export.py, ICalExporter (ical/ subpackage), and CsvExporter (csv/ subpackage); Stage 4 run() reconstructs SeasonPlan from checkpoint dict and calls all three exporters, writing file paths to the Stage 4 checkpoint. — 2026-06-09
  - Files: `tournament_scheduler/pipeline/stage4_export.py`, `tournament_scheduler/excel/plan_exporter.py`, `tournament_scheduler/ical/ical_exporter.py`, `tournament_scheduler/ical/__init__.py`, `tournament_scheduler/csv/csv_exporter.py`, `tournament_scheduler/csv/__init__.py`
  - Approach: Extend Stage 4 to call the existing `SeasonPlanExporter().export()` for Excel; add `ICalExporter` in a new `ical/` subpackage that writes one VEVENT per game using the `icalendar` library already in requirements; add `CsvExporter` in a new `csv/` subpackage using stdlib `csv`; write output file paths to the Stage 4 checkpoint.

- [x] Created .pi/extensions/rvv-miniputt.ts with /rvv-miniputt run (accepts --input, --work-dir, --resume-from, --export-dir) and /rvv-miniputt status commands; also added __main__ blocks to all four stage modules for python3 -m invocation. — 2026-06-09
  - Files: `.pi/extensions/rvv-miniputt.ts`
  - Approach: Create a TypeScript pi extension that imports `ExtensionAPI` from `@earendil-works/pi-coding-agent`; register a `/rvv-miniputt run` command that accepts `--input <path>`, `--work-dir <path>`, `--resume-from <stage>`, and `--export-dir <path>` flags; use `execFileAsync` (promisified Node.js `execFile`) to invoke each Python stage module as `python3 -m tournament_scheduler.pipeline.stage1_config <args>`, passing the work-dir and checkpoint paths; print stage results back to the pi session using the command context; also register a `/rvv-miniputt status` command that reads checkpoint JSON files from the work-dir and renders a stage-by-stage summary.

- [x] Created 6 test files covering PipelineState, LMStudioClient, and all four stages with mocked LLM calls (58 new tests); also fixed HolidayChecker→HolidayConflictChecker and strictFalse path in stage1_config. — 2026-06-09
  - Files: `tests/test_pipeline_state.py`, `tests/test_stage1_config.py`, `tests/test_stage2_scraping.py`, `tests/test_stage3_planning.py`, `tests/test_stage4_export.py`, `tests/test_lm_studio_client.py`
  - Approach: Mock the `lm_studio_client.complete()` call using `unittest.mock.patch` to avoid real HTTP calls; test Stage 1 validation with known-bad input.json fixtures; test Stage 2 LLM gate blocking and bypass for iCal sources; test Stage 3 retry logic; test Stage 4 produces all three output file types; each stage module must be runnable as `python3 -m tournament_scheduler.pipeline.stageN` so the pi extension can invoke it via execFile.

## Acceptance Criteria

The file `.pi/extensions/rvv-miniputt.ts` exists and exports a default pi extension function that registers at minimum a `/rvv-miniputt run` command and a `/rvv-miniputt status` command.
Running the pipeline with a valid `input.json` and reachable calendar sources completes all four stages, writes four checkpoint JSON files to the work directory, and produces Excel, iCal, and CSV output files.
The pipeline prints a Norwegian-language error message and exits without creating a checkpoint when `input.json` is missing a required field such as `teams` or `date_range`.
When a Playwright calendar source returns zero events and the LLM fallback also returns zero events, Stage 2 prints a blocking message containing the source name and does not write a Stage 2 checkpoint.
iCal sources (Google Calendar, Teamup) are not passed to the LLM quality gate and still produce valid scraping results in the Stage 2 checkpoint.
Running the pipeline with `--resume-from stage3` when valid Stage 1 and Stage 2 checkpoints already exist skips scraping and runs Stage 3 and Stage 4 without re-scraping any calendar source.

## Log

(no entries yet)

### 2026-06-09 — Created tournament_scheduler/llm subpackage with LMStudioClient HTTP wrapper and module-level complete()/extract_confidence() helpers.
**Rationale:** Used stdlib urllib to avoid extra dependencies; extract_confidence handles JSON embedded in prose and degrades gracefully on parse failure.
**Findings:** All 108 tests pass; imports verified.
LESSONS: none
**Files:** tournament_scheduler/llm/__init__.py (+5), tournament_scheduler/llm/lm_studio_client.py (+269)
**Commit:** 2a5064c (hockey)

### 2026-06-09 — Created tournament_scheduler/pipeline subpackage with PipelineState class writing per-stage JSON checkpoint files; supports status tracking (pending/running/done/failed), read/write/mark_done/mark_failed helpers, and stages_to_run() for --resume-from logic.
**Rationale:** Envelope wraps data with stage/status/updated_at fields for easy introspection; resolve_resume_from accepts integer, name, and alias inputs.
**Findings:** All 108 tests pass; round-trip and resume-logic unit checks verified manually.
LESSONS: none
**Files:** tournament_scheduler/pipeline/__init__.py (+9), tournament_scheduler/pipeline/state.py (+299)
**Commit:** b2802a3 (hockey)

### 2026-06-09 — Created stage1_config.py with run(), validate_config(), and _parse_config() covering date parsing, age group validation, parallel_games limits vs federation defaults, team list and external file references — all error messages in Norwegian.
**Rationale:** Reused KNOWN_AGE_GROUPS and FEDERATION_PARALLEL_GAMES_DEFAULTS from season_config.py; kept _parse_config separate from validation for clarity.
**Findings:** All 108 tests pass; manual smoke test confirms Norwegian error messages and valid-config pass.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage1_config.py (+304)
**Commit:** 07bf518 (hockey)

### 2026-06-09 — Created stage2_scraping.py with run(), per-source scraping dispatch (Playwright/iCal/Google), LLM quality gate with confidence threshold (0.6), HTML fallback extraction, and Norwegian block messages on zero events.
**Rationale:** Used monkey-patch on _parse_outlook_calendar to capture raw HTML without modifying base scraper; LMStudioUnavailableError handled gracefully — skips LLM gate and logs reason.
**Findings:** All 108 tests pass; Stage2 imports verified.
LESSONS: LMStudioUnavailableError must be imported from lm_studio_client not from llm/__init__.py since __init__.py does not re-export it
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+477)
**Commit:** e19cd40 (hockey)

### 2026-06-09 — Created stage3_planning.py with run(), LLM evaluation of coverage/diversity/balance (Norwegian prompts), retry loop up to MAX_RETRIES3 resetting SeasonPlanner on each attempt, and _plan_to_dict serialiser.
**Rationale:** Game model only has parallel_slot not time_slot/rink — fixed serialiser; CLUB_REGISTRY has arena field, not a separate CLUB_ARENAS constant.
**Findings:** All 108 tests pass; Stage3 imports verified.
LESSONS: CLUB_REGISTRY (not CLUB_ARENAS) is the arena source; Game has parallel_slot not time_slot
**Files:** tournament_scheduler/pipeline/stage3_planning.py (+329)
**Commit:** 6733fac (hockey)

### 2026-06-09 — Created stage4_export.py, ICalExporter (ical/ subpackage), and CsvExporter (csv/ subpackage); Stage 4 run() reconstructs SeasonPlan from checkpoint dict and calls all three exporters, writing file paths to the Stage 4 checkpoint.
**Rationale:** Relative imports in ical/csv subpackages use .. not ... since they are one level below tournament_scheduler.
**Findings:** All 108 tests pass; all imports verified.
LESSONS: ical/ and csv/ subpackages live inside tournament_scheduler/ (one level deep), so use  not  for relative imports
**Files:** stage4_export.py (+193), ical/__init__.py (+5), ical/ical_exporter.py (+128), csv/__init__.py (+5), csv/csv_exporter.py (+86)
**Commit:** cdf7ad9 (hockey)

### 2026-06-09 — Created .pi/extensions/rvv-miniputt.ts with /rvv-miniputt run (accepts --input, --work-dir, --resume-from, --export-dir) and /rvv-miniputt status commands; also added __main__ blocks to all four stage modules for python3 -m invocation.
**Rationale:** Used existing pi extension patterns (execFileAsync, registerCommand, Type from typebox); __main__ blocks read Stage N-1 checkpoint to extract date args rather than duplicating config parsing.
**Findings:** All 108 tests pass.
LESSONS: none
**Files:** .pi/extensions/rvv-miniputt.ts (+282), stage*_*.py (+129 total)
**Commit:** 1ee52e9 (hockey)

### 2026-06-09 — Created 6 test files covering PipelineState, LMStudioClient, and all four stages with mocked LLM calls (58 new tests); also fixed HolidayChecker→HolidayConflictChecker and strictFalse path in stage1_config.
**Rationale:** Two bugs found and fixed during test writing: wrong HolidayChecker class name, and stage1 non-strict path crashed on invalid config in _parse_config.
**Findings:** 166/167 total tests pass (1 pre-existing skip).
LESSONS: HolidayConflictChecker not HolidayChecker; stage1 strictFalse must return early with errors dict not call _parse_config on invalid input
**Files:** tests/test_pipeline_state.py (+87), test_lm_studio_client.py (+99), test_stage1_config.py (+147), test_stage2_scraping.py (+142), test_stage3_planning.py (+116), test_stage4_export.py (+116), pipeline fixes (+18)
**Commit:** [pending — fill after commit]
