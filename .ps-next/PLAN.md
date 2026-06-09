# Plan: LLM-guided browser scraper for SPA calendars

**Goal:** Build an agentic scraper that uses Pi's configured LLM model to interact with JS-rendered calendar SPAs — the LLM examines the page, decides what Playwright action to take (click a button, select a dropdown, etc.), and loops until calendar events are extracted. Replaces the brittle per-source Outlook scraper for all 6 unsupported clubs with JS-rendered booking widgets.

**Created:** 2026-06-09
**Intent:** The current Stage 2 scraper assumes an Outlook-style iframe with month-navigation buttons. 6 clubs (Jutul, Jar, Frisk Asker, Holmen, Tønsberg, Sandefjord) have calendars behind JS-rendered SPAs that require interaction to reveal bookings. An LLM-guided agent loop can handle these dynamically — examining the rendered DOM, deciding what to click, and iterating until events are found — replacing the need for 6 hand-crafted scrapers. The Pi extension handles LLM provider/model configuration; no provider-specific references live in the extension or plan.

**Backlog-ref:** 21

## Tasks

- [x] Define LLM action schema and create a DOM snapshotter utility
  - Files: `tournament_scheduler/pipeline/llm_scraper.py` (new)
  - Approach: Create a new module `llm_scraper.py` in the pipeline subpackage. Define a typed dict / dataclass for the LLM's structured action response with the following action types:
    - `click(selector: str)` — click an element by Playwright selector
    - `select(selector: str, value: str)` — select a dropdown option
    - `type(selector: str, text: str)` — type text into an input
    - `wait(ms: int)` — wait for a given duration
    - `scroll(direction: str, amount: int)` — scroll the page
    - `extract` — extract visible calendar-like data from current DOM
    - `done(events: list)` — signal completion with extracted calendar events
    Create a `DOMSnapshot` function that takes a Playwright page and returns a simplified text representation: page title, URL, visible text (truncated to ~8000 chars), list of interactive elements (buttons with text, input fields with placeholders, select elements with options, links with text), and the current viewport dimensions. Strip `<script>` and `<style>` tags.

- [x] Build the LLM agent loop — `LLMGuidedScraper` class
  - Files: `tournament_scheduler/pipeline/llm_scraper.py`
  - Approach: Add an `LLMGuidedScraper` class with a `run(url, start_date, end_date, max_iterations=20)` method. The loop:
    1. Open the URL with Playwright (headless Chromium)
    2. Capture DOM snapshot via the snapshotter
    3. Send snapshot + date range + instruction prompt to LLM
    4. Parse the structured action from LLM response
    5. If action is `done` with events → return events and exit
    6. If action is an interaction → execute via Playwright, wait for page to settle, loop back to step 2
    7. If max iterations exceeded → log the final DOM state and return empty events (block)
    The system prompt describes what ice hall bookings look like (date ranges, time slots, team names, Norwegian hall names), tells the LLM the available actions with their selectors, and instructs it to keep trying different approaches when calendar data isn't found. The user message includes the DOM snapshot, the date range, the source name, and the iteration count.
    The LLM endpoint is not hardcoded — `LMStudioClient` (or a Pi-provided equivalent) receives the endpoint from the Pi extension's configuration, which Pi manages. The `llm_scraper.py` module accepts an `llm_endpoint` parameter and defaults to whatever Pi passes through.

- [ ] Integrate the agentic scraper into Stage 2 as a replacement for the Outlook-specific scraper for HTML-based sources
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`, `tournament_scheduler/pipeline/llm_scraper.py`
  - Approach: In `_scrape_source`, when `source_type == "outlook"` (which covers all Playwright-based HTML sources), dispatch to `LLMGuidedScraper` instead of `_run_outlook_scraper`. Keep the existing iCal path unchanged. The LLM quality gate and HTML fallback in Stage 2 become redundant since the agentic loop already handles both verification and fallback extraction — remove them or fold them into the scraper's internal logic. Update source config to include a new source type `"html"` (distinct from `"outlook"`) for JS-rendered SPAs that need the full agentic loop; keep `"outlook"` as an alias for backward compatibility but internally both go through the agent. Also update the `club_registry.py` entries for Jutul, Jar, Frisk Asker, and Holmen to set `kind=OUTLOOK` and `skip=False` (since the agentic scraper can handle them now), with a note that they use the LLM-guided scraper rather than the old regex parser.

- [ ] Make LLM endpoint and max iterations configurable via the Pi extension
  - Files: `tournament_scheduler/pipeline/llm_scraper.py`, `.pi/extensions/rvv-miniputt.ts`
  - Approach: `LLMGuidedScraper.__init__` accepts `llm_endpoint` and `max_iterations` params. The Pi extension (`rvv-miniputt.ts`) passes the LLM endpoint through based on Pi's own model configuration (Pi handles provider selection — the extension just passes the endpoint to Python). The Stage 1 config (input.json) can include optional fields `llm_endpoint` and `scraper_max_iterations` to override. The extension's `/rvv-miniputt run` handler reads `--llm-endpoint` and `--scraper-max-iterations` flags and passes them as env vars or CLI args to the Python stage. No hardcoded provider or model names anywhere in the extension or Python code.

- [ ] Activate all 6 currently-skipped clubs in the club registry (Jutul, Jar, Frisk Asker, Holmen, Tønsberg, Sandefjord)
  - Files: `tournament_scheduler/club_registry.py`
  - Approach: Update the registry entries for all 6 clubs that currently have `skip=True`:
    - **Jutul** (baerumishall.no/kalender/ — StyledCalendar JS widget): set `kind=OUTLOOK, skip=False`, use existing URL as source.
    - **Jar** (forumbooking.no — Forumbooking ical.aspx returns empty): set `kind=OUTLOOK, skip=False`, use existing `https://www.forumbooking.no/schema.aspx?obj=2&schema=Jarhallen%20(ishall)&kalender=true&safarifix=true` as source URL. The LLM agent will interact with the HTML schema viewer instead of the broken iCal export.
    - **Frisk Asker** (friskaskerhockey.no — Sportality/s8y SPA): set `kind=OUTLOOK, skip=False`, source URL `https://www.friskaskerhockey.no/`.
    - **Holmen** (kalender.sportello.no/booking/11055 — Sportello SPA): set `kind=OUTLOOK, skip=False`, source URL `https://kalender.sportello.no/booking/11055`.
    - **Tønsberg** (BookUp SPA, was missing source URL — now known via PROJECT.md): set `kind=OUTLOOK, skip=False`, source URL `https://www.bookup.no/utleie/Index/860`.
    - **Sandefjord Penguins** (BookUp SPA, was missing source URL — now known via PROJECT.md): set `kind=OUTLOOK, skip=False`, source URL `https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen`.
    Update their `note` fields to document that they use the LLM-guided agentic scraper. The source type is `OUTLOOK` (meaning Playwright + LLM agent, not literal Outlook scraping) — may need a new source kind like `AGENTIC` for clarity, but `OUTLOOK` works as an alias since the dispatch in Stage 2 will route all Playwright-based sources to the agent.

- [ ] Test the LLM-guided scraper with mocked LLM responses
  - Files: `tests/test_llm_scraper.py`
  - Approach: Create tests that mock the `LMStudioClient.complete` method to return controlled action responses. Test scenarios: (1) LLM immediately finds events and returns `done` with event data, (2) LLM needs a "click 'Vis kalender'" action before finding events, (3) LLM needs a "select month/year" action before finding events, (4) max iterations exceeded without finding events — verify blocking behavior, (5) a source that's iCal-based bypasses the agent entirely. Use the existing patch pattern from `test_stage2_scraping.py`. Also test that non-Playwright sources (iCal) are not passed to the agent.

## Notes
- The LLM action schema uses Playwright-compatible selectors (CSS, `:text()`, etc.) so the agent loop can directly call `page.click()`, `page.select_option()`, `page.fill()`, etc.
- The DOM snapshot is a text representation, not raw HTML — the LLM only sees what's useful for interaction decisions (buttons, links, inputs) plus the visible page text.
- Max iterations default of 20 should be enough for most SPAs (typical flow: 1-3 clicks to reveal calendar + 1-12 month navigations). Each iteration takes ~2-5 seconds (LLM inference + Playwright action).
- The existing `_run_outlook_scraper` function is kept during transition but can be removed once the agentic scraper is validated against real Outlook calendars.
- Cache check happens at the source level (before the agent loop) — cached results skip LLM interaction entirely.

## Acceptance Criteria
- [ ] `LLMGuidedScraper` opens a URL with Playwright, captures DOM snapshot, sends to LLM, executes returned action, and loops until events are extracted.
- [ ] The LLM can return `click`, `select`, `type`, `wait`, `scroll`, `extract`, and `done` structured actions.
- [ ] Running Stage 2 with a source configured as `"type": "html"` dispatches to the agentic scraper instead of the old Outlook scraper.
- [ ] Jutul, Jar, Frisk Asker, and Holmen are activated in the club registry with `skip=False, kind=OUTLOOK`.
- [ ] iCal sources (Teamup, Google Calendar) still bypass the LLM agent entirely.
- [ ] Max iterations exceeded produces a Norwegian blocking message with the final page state.
- [ ] All existing pipeline tests (Stage 1, Stage 3, Stage 4, tournament updater) still pass.
- [ ] 5+ tests in `tests/test_llm_scraper.py` cover immediate extraction, multi-step discovery, iCal bypass, and iteration limits.

## Log


### 2026-06-09 — Build the LLM agent loop — `LLMGuidedScraper` class
**Done:** Added LLMGuidedScraper class to llm_scraper.py with run(url, name, start_date, end_date, max_iterations=20) method implementing the full agent loop: (1) open URL with Playwright, (2) capture DOM snapshot, (3) send snapshot + context to LLM, (4) parse structured action from response, (5) execute action via Playwright, (6) loop until done with events or max iterations, (7) block with Norwegian message when exhausted.
**Rationale:** Follows existing codebase patterns (Playwright sync API, LMStudioClient). System prompt describes ice hall bookings in Norwegian, lists 7 action types with JSON examples. User message includes DOM snapshot with interactive elements table. Action executor maps to Playwright click/select_option/fill/scroll/wait operations.
**Findings:** All 171 tests pass. LLM endpoint configurable via constructor — LMStudioClient is created with the given base_url and model. The run() method handles graceful degradation on page load errors and LLM failures. Max iterations default 20.
**Files:** M tournament_scheduler/pipeline/llm_scraper.py (+498)
**Commit:** 11d6e59
### 2026-06-09 — Define LLM action schema and create a DOM snapshotter utility
**Done:** Created tournament_scheduler/pipeline/llm_scraper.py with LLMAction dataclass (7 action types), action_from_dict parser with snake_case/camelCase fallback, capture_dom_snapshot() function with <script>/<style> stripping and interactive element extraction.
**Rationale:** Follows existing codebase patterns (dataclasses, type hints, docstrings). action_from_dict tolerates LLM output variations (camelCase, extra keys). DOM snapshot strips script/style tags, extracts buttons/links/inputs/selects, and generates Playwright-compatible selectors.
**Findings:** All imports and unit tests pass. BeautifulSoup used for text extraction when available with a regex fallback. Selector builder tries data-testid, aria-label, id, and text-based selectors in priority order.
**Files:** A tournament_scheduler/pipeline/llm_scraper.py (+405)
**Commit:** 1a5993b
<!-- pi-next appends entries here after each task -->
