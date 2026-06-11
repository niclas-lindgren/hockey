# Plan: Avoid BookUp password leaking to the LLM

**Goal:** Investigate how to avoid the BookUp password leaking to the LLM when it's entered on-demand during the run flow — the pipeline currently prompts for BookUp credentials interactively (added for booking-calendar handling, backlog item #32) and the value may end up in LLM prompts/context (e.g. via ScraperAgent or scrape-llm). Audit the credential-prompt and scraper-agent code paths to ensure the password is never included in any text sent to a local or remote LLM, and propose a safer pattern (e.g. env var injection, redaction, out-of-band browser auth) if it currently is.
**Created:** 2026-06-11
**Intent:** Backlog #32 added interactive BookUp credential prompting for ScraperAgent-driven login, but the password is filled into a live page via Playwright and the resulting DOM snapshot/interactive-element list is embedded verbatim into the LLM prompt — this audit confirms the leak vector and closes it with sanitization at the source plus a defense-in-depth redaction layer.
**Backlog-ref:** 54

## Tasks
- [x] Added a module-level _sanitize_html() helper using a regex to blank value attributes on password/email/username input fields, and applied it to html and iframe_html in _snapshot() so credential values never leave the browser worker. — 2026-06-11
  - Files: tournament_scheduler/pipeline/browser_worker.py
  - Approach: Add a `_sanitize_html(html: str) -> str` helper that strips/blanks `value="..."` attributes from `<input type="password">` and `<input type="email">`/`<input>` elements matched against known credential field selectors (`#email`, `input[type='password']`). Call it on the `html` and `iframe_html` fields inside `_snapshot()` (lines ~102-134) before the dict is returned, so both `cmd_type`/`cmd_click`/`cmd_goto` results and the TS layer never see raw credential values.

- [x] Added a _redact_credentials() helper that replaces literal occurrences of os.environ BOOKUP_EMAIL/BOOKUP_PASSWORD values with '[REDACTED]', and applied it to label_text in _interactive_elements() before truncation/inclusion in the snapshot. — 2026-06-11
  - Files: tournament_scheduler/pipeline/browser_worker.py
  - Approach: In `_interactive_elements()` (lines ~136-177), after building each element dict, scrub `text`/`placeholder`-derived `label_text` fields by replacing any substring equal to `os.environ.get("BOOKUP_EMAIL")` or `os.environ.get("BOOKUP_PASSWORD")` (when set and non-empty) with `"[REDACTED]"`, so credential values can't surface via input placeholders or echoed labels.

- [x] Added an exported redactCredentials(text) helper near substituteEnvVars() that replaces literal occurrences of process.env.BOOKUP_EMAIL/BOOKUP_PASSWORD with '[REDACTED]', and applied it to snapshot.html, snapshot.iframe_html, and each interactive element's text inside userMessage() before the message is built. — 2026-06-11
  - Files: .pi/lib/scraper-agent.ts
  - Approach: Add a `redactCredentials(text: string): string` helper near `substituteEnvVars()` (lines ~559-564) that replaces any occurrence of `process.env.BOOKUP_EMAIL` and `process.env.BOOKUP_PASSWORD` (when set and length > 0) in a given string with `"[REDACTED]"`. Apply it to the `snapshot.html`/`snapshot.iframe_html`/interactive-element text inside `userMessage()` (lines 137-174) before the message is returned to `callLLM()` (line 462), as a second layer in case the Python-side sanitization in browser_worker.py misses a path.

- [ ] Sanitize llm_scraper.py DOM snapshot and prompt building for the scrape-llm CLI path
  - Files: tournament_scheduler/pipeline/llm_scraper.py
  - Approach: In `capture_dom_snapshot()` (around line 63, `page.content()`-based) and in the prompt-building code around line 829 (`visible_text` embedded as "Synlig tekst fra kalender-siden"), reuse the same redaction approach as scraper-agent.ts: after `_detect_and_login()` runs, scrub any literal occurrences of the resolved `BOOKUP_EMAIL`/`BOOKUP_PASSWORD` env var values from `raw_html`/`visible_text` before they are used to build the LLM user message.

- [ ] Add unit tests for sanitization in browser_worker.py
  - Files: tests/test_browser_worker.py
  - Approach: New test file (no existing `test_browser_worker.py`; follow conventions in `tests/test_ical_scraper.py`). Test `_sanitize_html()` strips `value="secret123"` from `<input type="password" value="secret123">` and `<input id="email" value="user@example.com">`, and test `_interactive_elements()`-style label scrubbing replaces a credential substring with `"[REDACTED]"` when `BOOKUP_EMAIL`/`BOOKUP_PASSWORD` env vars are set (use `monkeypatch.setenv`).

- [ ] Add unit tests for redaction in scraper-agent.ts
  - Files: .pi/lib/scraper-agent.test.ts
  - Approach: New colocated test file following the `.pi/lib/parsers.test.ts` convention. Test `redactCredentials()` replaces a literal password/email substring (set via `process.env.BOOKUP_PASSWORD`/`BOOKUP_EMAIL` in the test) with `"[REDACTED]"` inside arbitrary HTML/text, and confirm `userMessage()` output no longer contains the raw credential value when `snapshot.html` includes it.

- [ ] Document the defense-in-depth credential-leak mitigation and out-of-band-auth alternative
  - Files: tournament_scheduler/pipeline/browser_worker.py, .pi/lib/scraper-agent.ts, tournament_scheduler/pipeline/llm_scraper.py
  - Approach: Add inline code comments at each sanitization point explaining the two-layer defense (Python-side DOM sanitization as primary, TS/Python regex redaction as fallback) and note as a code comment near `_detect_and_login()`/`initial_navigation` that a longer-term alternative is out-of-band browser auth (persistent authenticated browser profile/cookie session established once outside the LLM loop), which would avoid feeding any login UI state to the LLM at all — out of scope for this fix.

## Notes
- Do not re-implement the existing `credential_env_vars` mechanism, interactive prompting in `rvv-miniputt.ts`, or the empty-placeholder pre-flight warning in `scraper-agent.ts` — these already exist (backlog #32, archived plan PLAN-2026-06-10-credential-aware-booking-calendar-handling.md).
- The leak is conditional: it depends on whether the target site's DOM reflects the filled `value` attribute back via `page.content()`. Sanitize unconditionally regardless of whether a given site currently exhibits the reflection, since this is a security property that must hold for all sites.
- Redaction must only trigger when the env var is set and non-empty, to avoid replacing common short strings (e.g. avoid redacting on empty-string env vars).

## Acceptance Criteria
- `tournament_scheduler/pipeline/browser_worker.py` contains a sanitization function that removes `value="..."` attributes from password and email `<input>` elements before `_snapshot()` returns its result.
- Calling `userMessage()` in `.pi/lib/scraper-agent.ts` with a snapshot whose `html` field contains a literal `BOOKUP_PASSWORD` value does not return that literal value in the resulting message string.
- `tournament_scheduler/pipeline/llm_scraper.py` does not pass `BOOKUP_EMAIL` or `BOOKUP_PASSWORD` env var values through to the LLM prompt text built around `capture_dom_snapshot()`.
- Running `pytest tests/test_browser_worker.py` passes and reports that sanitization tests for password/email input redaction succeed.
- Running the new `.pi/lib/scraper-agent.test.ts` test suite passes and shows that `redactCredentials()` replaces credential substrings with `"[REDACTED]"`.

## Log


<!-- pi-next appends entries here after each task -->

### 2026-06-11 — Added a module-level _sanitize_html() helper using a regex to blank value attributes on password/email/username input fields, and applied it to html and iframe_html in _snapshot() so credential values never leave the browser worker.
**Rationale:** Regex-based approach chosen over a full HTML parser to avoid adding a new dependency and keep the change minimal/fast for stdin/stdout snapshot serialization.
**Findings:** Verified the regex correctly blanks value attrs on typepassword, typeemail, and id/nameemail/username/password/login inputs while leaving unrelated inputs (checkboxes, plain text fields) untouched. Full test suite: 311 passed, 1 pre-existing unrelated failure (test_zero_events_blocks_source, confirmed pre-existing via git stash), 1 skipped.
LESSONS: none
**Files:** tournament_scheduler/pipeline/browser_worker.py (+27/-2)
**Commit:** a286846 (hockey)

### 2026-06-11 — Added a _redact_credentials() helper that replaces literal occurrences of os.environ BOOKUP_EMAIL/BOOKUP_PASSWORD values with '[REDACTED]', and applied it to label_text in _interactive_elements() before truncation/inclusion in the snapshot.
**Rationale:** Used a simple substring-replace approach against resolved env var values, consistent with the redaction approach planned for scraper-agent.ts and llm_scraper.py, rather than a regex, since the exact credential strings are known at runtime.
**Findings:** Verified _redact_credentials replaces both BOOKUP_EMAIL and BOOKUP_PASSWORD substrings with [REDACTED] and is a no-op when env vars are unset/empty. Full test suite: 310 passed, 2 pre-existing/flaky failures unrelated to this change (test_zero_events_blocks_source and test_sources_run_in_different_threads, both confirmed failing on main via git stash).
LESSONS: test_sources_run_in_different_threads is a pre-existing flaky test unrelated to credential sanitization work; do not attempt to fix it as part of this plan.
**Files:** tournament_scheduler/pipeline/browser_worker.py (+19/-1)
**Commit:** fdbc143 (hockey)

### 2026-06-11 — Added an exported redactCredentials(text) helper near substituteEnvVars() that replaces literal occurrences of process.env.BOOKUP_EMAIL/BOOKUP_PASSWORD with '[REDACTED]', and applied it to snapshot.html, snapshot.iframe_html, and each interactive element's text inside userMessage() before the message is built.
**Rationale:** Mirrors the same env-var-substring-replace approach used in the Python browser_worker.py redaction (task 2) for consistency across the two layers; function declaration hoisting in TS/JS allows redactCredentials to be defined after userMessage without issue.
**Findings:** tsc --noEmit type-check on scraper-agent.ts shows no new type errors related to redactCredentials or userMessage. No package.json/test runner found for .pi/lib in this repo (node_modules appears to be a stray artifact), so a runtime test could not be executed for this file; unit test for redactCredentials is covered by the next planned task (scraper-agent.test.ts).
LESSONS: No package.json/test runner exists for .pi/lib TS files in this repo; tsc --noEmit is the only available verification. The next task (scraper-agent.test.ts) should check whether a test runner needs to be set up first.
**Files:** .pi/lib/scraper-agent.ts (+21/-3)
**Commit:** [pending — fill after commit]
