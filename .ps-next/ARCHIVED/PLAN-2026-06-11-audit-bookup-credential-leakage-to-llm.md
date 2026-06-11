# Plan: Audit BookUp credential leakage to LLM
**Goal:** Verify that BOOKUP_EMAIL/BOOKUP_PASSWORD credential values cannot reach any LLM prompt, log file, or error message — and document all defense layers and any gaps found.
**Created:** 2026-06-11
**Intent:** Backlog #57 — defense-in-depth audit following #54's investigation. The pipeline already has 4-layer credential sanitization; this verifies every layer works, traces all credential flow paths, and identifies any residual gaps.
**Backlog-ref:** 57

## Tasks
- [x] Trace and document the full credential flow end-to-end (env var / interactive prompt → browser input → snapshot → LLM prompt)
  - Files: .pi/lib/scraper-agent.ts, .pi/lib/pipeline-runner.ts, tournament_scheduler/pipeline/browser_worker.py, tournament_scheduler/pipeline/scraper_strategies.py
  - Approach: Walk every code path where BOOKUP_EMAIL/BOOKUP_PASSWORD could enter, be stored, or be forwarded. Document the 4 defense-in-depth layers and verify they cover every path. Check the Sandefjord strategy specifically (only types email, not password — verify this is intentional). Verify no llm-bridge exists.

- [x] Check all log/error-message paths for credential leakage
  - Files: .pi/lib/pipeline-logger.ts, .pi/lib/pipeline-runner.ts, tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/pipeline/llm_scraper.py
  - Approach: Search for any `console.log`, `console.error`, `logger.info`, `print`, or `lines.push` that could include credential values. Verify pipeline logger's stdout/stderr capture doesn't persist credential data from Python stages. Check deterministic scraper path (`_run_credentialed_bookup_or_outlook`) for error-message leaks.

- [x] Verify sanitization coverage end-to-end with tests
  - Files: tests/test_browser_worker.py, tournament_scheduler/pipeline/browser_worker.py, .pi/lib/scraper-agent.ts
  - Approach: Run existing credential sanitization tests. Verify `_sanitize_html()` regex coverage — the regex matches `type="password"`, `type="email"`, `id/name="email/password/username/user/login"` but could miss non-standard input names. Confirm Layers 2-3 substring-based redaction catches anything Layer 1 misses. Write any missing edge-case tests.

## Notes
- The pipeline already has 4 defense-in-depth layers for credential-leak mitigation (documented in browser_worker.py, scraper-agent.ts, llm_scraper.py).
- Sandefjord Penguins is the only source with `credential_env_vars` (`BOOKUP_EMAIL`, `BOOKUP_PASSWORD`).
- The Sandefjord strategy's `initial_navigation` only types `${BOOKUP_EMAIL}` via a `type` step — the password env var is declared but not used in any navigation step. Need to verify this is intentional (BookUp may use email-only first step or magic-link flow).
- No `llm-bridge` module exists in the codebase — this was mentioned in the backlog item as a theoretical path.
- The deterministic scraper path (`stage2_scraping.py` / `_run_credentialed_bookup_or_outlook`) handles credentials directly via Playwright but never sends data to an LLM.

## Acceptance Criteria
- [x] All 4 defense-in-depth layers are verified to work on the current code.
- [x] No path exists where BOOKUP_EMAIL or BOOKUP_PASSWORD values could appear in text sent to a local or remote LLM (scraper-agent.ts `callLLM`, llm_scraper.py `_extract_events_via_llm`).
- [x] No path exists where credential values could appear in pipeline log files (`.pipeline/logs/run-*.jsonl`).
- [x] No path exists where credential values could appear in error messages surfaced to stderr/stdout.
- [x] run: pytest tests/test_browser_worker.py -v
- [x] Any gaps found are documented and, if fixable within this plan, addressed.

## Log



### 2026-06-11 — Verify sanitization coverage end-to-end with tests
**Done:** Sanitization coverage verified. Added 6 edge-case tests proving defense-in-depth: Layer 1 regex misses non-standard input names (pwd, credential, passwd), but Layer 2 substring redaction reliably catches the credential values.
**Rationale:** The regex gap is documented and acceptable — it's the expected trade-off between tight regex specificity (no false positives on unrelated input fields) and defense-in-depth via the substring-based Layer 2. The gap is covered by design.
**Findings:** (1) Existing 10 tests all pass, covering standard Layer 1/2 scenarios. (2) New TestDefenseInDepth class with 6 tests: verifies regex gap for name='pwd' and name='credential'; verifies Layer 2 catches what Layer 1 misses; verifies both layers combined; verifies credential redaction in iframe-snapshot and error-text contexts. (3) Defense-in-depth is proven: even when Layer 1 misses, Layer 2 substring matching catches the literal credential value. Layer 3 (TS redactCredentials) provides identical substring-based protection at the prompt-building boundary.
**Files:** tests/test_browser_worker.py (+56 lines, 6 new tests), .pi/lib/scraper-agent.ts (verified Layer 3)
**Commit:** not committed
### 2026-06-11 — Check all log/error-message paths for credential leakage
**Done:** All log/error-message paths verified safe — no credential values ever reach logs, console, or error messages.
**Rationale:** Traced every lines.push, console.log/warn/error, logger.info/warning, and error return path. None include resolved credential values. The only line that touches a credential value is pipeline-runner.ts:186 which only shows its length.
**Findings:** (1) pipeline-runner.ts line 186 logs only credential NAME and LENGTH (not value): `${envVar} satt (${value.length} tegn)`. (2) scraper-agent.ts console.warn line 397 logs env var NAMES only — checks process.env existence, not values. (3) scraper-agent.ts console.error lines 313/435/467/487 log browser stderr, step indices, LLM errors, and LLM response text — none contain credential values. (4) Python logger.info line 622 (llm_scraper.py) logs env var NAME only: 'Attempting BookUp login with BOOKUP_EMAIL'. (5) stage2_scraping.py error strings only contain env var NAMES, not values. (6) stage2_scraping.json checkpoint stores credential_env_vars names and unresolved ${PLACEHOLDER} patterns, never resolved values. (7) _run_credentialed_bookup_or_outlook exception handlers use silent pass — no credential values echoed in errors.
**Files:** .pi/lib/pipeline-logger.ts (verified), .pi/lib/pipeline-runner.ts (verified), .pi/lib/scraper-agent.ts (verified), tournament_scheduler/pipeline/stage2_scraping.py (verified), tournament_scheduler/pipeline/llm_scraper.py (verified)
**Commit:** not committed
### 2026-06-11 — Trace and document the full credential flow end-to-end (env var / interactive prompt → browser input → snapshot → LLM prompt)
**Done:** Full credential flow traced and documented. Verified no llm-bridge exists. All 4 defense layers verified.
**Rationale:** Traced every code path: env vars → process.env, ctx.ui.input → process.env, substituteEnvVars/Template.safe_substitute → browser fill, _sanitize_html / _redact_credentials / redactCredentials / _redact_credential_values scrubbing → LLM prompt. Sandefjord strategy only types EMAIL (not password) in its initial_navigation — BOOKUP_PASSWORD is declared but never substituted into any navigation step, so it physically cannot reach browser input fields today. The 4 defense layers would catch it even if a future strategy added a password type step.
**Findings:** Key findings: (1) No llm-bridge module exists in codebase. (2) BOOKUP_PASSWORD is declared in credential_env_vars but never used in any initial_navigation step — only BOOKUP_EMAIL is typed. (3) Layer 1 regex (_CREDENTIAL_INPUT_RE) misses non-standard input names (pwd, credential, passwd) but Layers 2/3 substring redaction catches them. (4) Layer 3 (TS redactCredentials) is applied to html, iframe_html, AND interactive element text in userMessage(). (5) Layer 4 (Python _redact_credential_values) in llm_scraper.py applied to visible_text before LLM prompt.
**Files:** .pi/lib/scraper-agent.ts (verified), .pi/lib/pipeline-runner.ts (verified), tournament_scheduler/pipeline/browser_worker.py (verified), tournament_scheduler/pipeline/scraper_strategies.py (verified)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
