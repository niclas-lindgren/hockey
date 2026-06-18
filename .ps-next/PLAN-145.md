# Plan: Add scraping confidence assessment after Stage 2
**Goal:** Add scraping confidence assessment after Stage 2: before Stage 3 begins, pass the scraping summary (source names, event counts, date ranges covered, blocked sources) to an LLM and ask it to assess whether the data looks complete and trustworthy. Flag sources that look suspiciously sparse relative to their expected volume, or date ranges with unexplained gaps. Output surfaced as a Stage 2 warning in the CLI and report.
**Created:** 2026-06-18
**Intent:** Catch incomplete or suspicious scraping results before the season planner runs on potentially bad data, so organizers can review quality issues before committing to a plan.
**Backlog-ref:** 145

## Tasks
- [x] Created scraping_confidence.py with ScrapingConfidenceVerdict dataclass and run_confidence_assessment function mirroring llm_approval_gate.py structure. — 2026-06-18
  - Files: tournament_scheduler/pipeline/scraping_confidence.py, tournament_scheduler/pipeline/__init__.py
  - Approach: Create a new module `scraping_confidence.py` mirroring the structure of `llm_approval_gate.py` — define a `ScrapingConfidenceVerdict` dataclass (suspicious_sources list, gaps list, overall_assessment str, verdict "OK"/"WARN") and a `run_confidence_assessment(scraping_checkpoint, cfg, client)` function that formats the Stage 2 checkpoint fields (source names, event counts, blocked sources) plus config date range into an LLM prompt and parses the structured JSON response.

- [ ] Add LLM prompt and response parsing for confidence assessment
  - Files: tournament_scheduler/pipeline/scraping_confidence.py
  - Approach: Implement the prompt template inside `scraping_confidence.py`, instructing the LLM to evaluate each source's event count relative to the season length and expected booking volume, flag blocked sources, and identify date range gaps; parse the JSON response into `ScrapingConfidenceVerdict` with a fallback for malformed JSON, following the same error-handling pattern used in `llm_approval_gate.py`.

- [ ] Wire confidence assessment into the pipeline orchestrator between Stage 2 and Stage 3
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py
  - Approach: In `_cmd_run`, after reading the Stage 2 scraping checkpoint and before calling `stage3_run`, call `run_confidence_assessment(scraping, cfg, lm_client)` and store the verdict; if the LLM client is unavailable, skip silently and log a debug message consistent with how other optional LLM steps are guarded.

- [ ] Persist confidence assessment verdict to Stage 2 checkpoint
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/state.py
  - Approach: After running the confidence assessment, write the `ScrapingConfidenceVerdict` (serialized to dict) into the stage2 checkpoint under a `"confidence"` key using the existing `state.write_*` or checkpoint-update pattern, so downstream stages and reports can read it.

- [ ] Surface confidence assessment warnings in CLI output
  - Files: tournament_scheduler/cli/pipeline_orchestrator.py, tournament_scheduler/utils/rich_output.py
  - Approach: After the confidence assessment runs, use `_console.print()` with Rich formatting (Panel or warning-styled text) to list any suspicious sources and gaps identified by the LLM, displayed immediately after the existing blocked/fallback source warnings in `_cmd_run`, keeping Norwegian-language wording consistent with other Stage 2 output.

- [ ] Show confidence assessment in the calendars.html report
  - Files: tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: In `calendar_viewer.py`, read the `"confidence"` key from the stage2 checkpoint (if present) and inject any suspicious sources or gap warnings into the HTML report as a new warning section below the per-source freshness indicators, following the existing template-injection pattern used for blocked/stale sources.

- [ ] Add unit tests for confidence assessment prompt formatting and verdict parsing
  - Files: tests/test_scraping_confidence.py
  - Approach: Write pytest tests covering: correct prompt construction from a sample stage2 checkpoint, JSON verdict parsing (WARN/OK/malformed-JSON fallback), suspicious sources and gaps propagate correctly to `ScrapingConfidenceVerdict` fields, and that passing `client=None` returns `None` without raising — mirroring the test structure in `tests/test_llm_approval_gate.py`.

## Acceptance Criteria
- [ ] When Stage 2 completes, the pipeline orchestrator calls the confidence assessment before Stage 3 starts, and the CLI output contains a warning section listing suspicious sources or gaps when the LLM flags them.
- [ ] The Stage 2 checkpoint has a `"confidence"` key that contains the verdict fields (suspicious_sources, gaps, overall_assessment) after a successful assessment run.
- [ ] `calendars.html` shows confidence assessment warnings when the stage2 checkpoint reports suspicious or low-event sources.
- [ ] Unit tests in `tests/test_scraping_confidence.py` pass, covering prompt formatting with real checkpoint data, verdict parsing including the malformed-JSON fallback path, and that `client=None` returns `None` without error.
- [ ] When the LLM client is unavailable, the pipeline does not fail — it skips the confidence step and proceeds to Stage 3 without error.

## Log

<!-- pi-next appends entries here after each task -->

### 2026-06-18 — Created scraping_confidence.py with ScrapingConfidenceVerdict dataclass and run_confidence_assessment function mirroring llm_approval_gate.py structure.
**Rationale:** Mirrored llm_approval_gate.py pattern: build summary dict from checkpoint, call client.complete with system/user prompts, parse JSON from fence or raw text, fall back to OK.
**Findings:** Module imports cleanly; per_source_event_counts uses event_count field from source dicts; sources_with_zero_events excludes already-blocked sources.
LESSONS: none
**Files:** tournament_scheduler/pipeline/scraping_confidence.py (+142/-0)
**Commit:** [pending — fill after commit]
