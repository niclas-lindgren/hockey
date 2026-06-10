# Plan: Credential-aware booking calendar handling
**Goal:** When the scraper encounters a booking/order calendar requiring authentication (e.g. BookUp), the system detects it, stops to ask the user for credentials interactively, and surfaces clear Norwegian-language messages instead of silently returning 0 events.
**Created:** 2026-06-10
**Intent:** Backlog #30 added authenticated BookUp scraping, but the credential workflow is fragile — env vars referenced in strategy initial_navigation are silently empty if not set. Item #32 makes this first-class: detect auth-required sources, prompt interactively, and give helpful error messages when credentials are absent.
**Backlog-ref:** 32

## Tasks
- [x] Add credential_env_vars field to ScraperStrategy and strategy serialisation
  - Files: tournament_scheduler/pipeline/scraper_strategies.py
  - Approach: Add `credential_env_vars: list[str] = field(default_factory=list)` to the dataclass. Set `credential_env_vars=["BOOKUP_EMAIL", "BOOKUP_PASSWORD"]` on Tønsberg and Sandefjord Penguins strategies. Add `requires_credentials` property. Export in `strategy_to_dict()` and `list_strategies()`.

- [x] Improve blocked-source messages in stage2_scraping.py with credential hints
  - Files: tournament_scheduler/pipeline/stage2_scraping.py
  - Approach: When a source returns 0 events, look up its strategy and if `requires_credentials`, append a specific Norwegian message naming the required env vars. E.g.: "Kilde 'Tønsberg' krever innlogging (BookUp). Angi miljøvariablene BOOKUP_EMAIL og BOOKUP_PASSWORD, eller kjør pipeline interaktivt for å bli spurt." The stage already imports scraper strategies (for Jutul); extend that lookup.

- [x] Add interactive credential prompting in rvv-miniputt.ts before ScraperAgent launch
  - Files: .pi/extensions/rvv-miniputt.ts
  - Approach: In the Stage 2 blocked-sources loop, after fetching the strategy, check `credential_env_vars`. For each missing env var, use `ctx.ui.input()` to prompt the user. Set the value in `process.env` so `substituteEnvVars()` picks it up. Surface a summary of what was collected. Only prompt once per missing variable (use a Set of already-prompted vars).

- [x] Add pre-flight credential check to ScraperAgent scrape method
  - Files: .pi/lib/scraper-agent.ts
  - Approach: Before executing initial_navigation steps, scan them for `${...}` placeholders. If any placeholder resolves to an empty string after substitution, log a warning via the worker. This is a safety net — the extension should already prompt, but if someone calls ScraperAgent directly without credentials, the warning will surface.

- [x] Run quality gates (typecheck, lint) and verify acceptance criteria
  - Files: tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/stage2_scraping.py, .pi/extensions/rvv-miniputt.ts, .pi/lib/scraper-agent.ts
  - Approach: Run `python3 -m py_compile` on Python files, check TS compiles with `npx tsc --noEmit` if tsconfig exists, then run verify steps.

## Notes
- The credential mechanism is general: any strategy can declare `credential_env_vars` and the extension will handle it. Currently only BookUp strategies need it, but future forums/systems fit the same pattern.
- The extension's `substituteEnvVars()` function already supports `${VAR_NAME}` syntax — this plan adds the prompting layer above it.
- Do NOT persist credentials to disk or expose them in logs — only set `process.env` in-memory for the current pipeline run.
- The interactive prompt should degrade gracefully if running non-interactively (e.g. `--non-strict` in a headless pipeline) — surface a clear message and exit.

## Acceptance Criteria
- [ ] `ScraperStrategy` has `credential_env_vars` field with default empty list, exported in `strategy_to_dict()`
- [ ] BookUp strategies (Tønsberg, Sandefjord) have `credential_env_vars=["BOOKUP_EMAIL", "BOOKUP_PASSWORD"]`
- [ ] `stage2_scraping.py` blocked messages contain credential-env-var names when a blocked source requires auth
- [ ] `rvv-miniputt.ts` shows interactive credential prompts for missing environment variables before launching the ScraperAgent
- [ ] `scraper-agent.ts` emits a warning when credential placeholders resolve to empty strings during initial navigation
- [ ] grep: `grep -r 'BOOKUP_EMAIL\|BOOKUP_PASSWORD' tournament_scheduler/pipeline/scraper_strategies.py` shows both on BookUp strategies

## Log





### 2026-06-10 — Run quality gates (typecheck, lint) and verify acceptance criteria
**Done:** Ran py_compile on both Python files (OK). All 6 acceptance criteria verified: credential_env_vars field exists on dataclass, BookUp strategies have BOOKUP_EMAIL/BOOKUP_PASSWORD, stage2 blocked messages include credential hints, rvv-miniputt prompts for missing env vars, scraper-agent warns on empty placeholders, and grep confirms BOOKUP references in strategies.
**Rationale:** All 6 ACs pass. The credential mechanism is general — any future strategy that needs auth simply declares credential_env_vars and gets prompting for free.
**Findings:** scraper-agent.ts is in .gitignore so its changes won't appear in git diff, but the credential pre-flight check is on disk. The drift warning about pipeline checkpoint files (.pipeline/*) is from previous runs — not our changes.
**Files:** tournament_scheduler/pipeline/scraper_strategies.py, tournament_scheduler/pipeline/stage2_scraping.py, .pi/extensions/rvv-miniputt.ts, .pi/lib/scraper-agent.ts
**Commit:** not committed
### 2026-06-10 — Add pre-flight credential check to ScraperAgent scrape method
**Done:** Added credential pre-flight check before the initial_navigation loop in the ScraperAgent scrape method. Scans all nav steps for ${...} placeholders, checks process.env, and emits a console.warn with the list of unresolved variable names when any are missing.
**Rationale:** Uses console.warn (visible in stderr) rather than an exception — missing credentials shouldn't crash the agent, just warn. The extension logs may also capture stderr from the browser worker.
**Findings:** The check is a safety net — the rvv-miniputt extension should already prompt before calling ScraperAgent, but if the agent is called directly (e.g., from tests or custom scripts), the warning surfaces the credential gap.
**Files:** .pi/lib/scraper-agent.ts (+22/-0)
**Commit:** not committed
### 2026-06-10 — Add interactive credential prompting in rvv-miniputt.ts before ScraperAgent launch
**Done:** Added credential pre-flight in the Stage 2 blocked-sources loop: after fetching the strategy, checks credential_env_vars and prompts the user via ctx.ui.input() for each missing env var. Sets them in process.env so substituteEnvVars() picks them up. Reports what was set (with character count, not the value) and warns when a value was skipped.
**Rationale:** Interactive prompting is the most user-friendly way to get credentials — no manual env var export needed. The character-count-only report avoids logging credentials.
**Findings:** The prompting re-runs for each blocked source with the same env var, but only if still unset — once the user provides a value, subsequent sources skip the prompt because process.env is already populated.
**Files:** .pi/extensions/rvv-miniputt.ts (+19/-0)
**Commit:** not committed
### 2026-06-10 — Improve blocked-source messages in stage2_scraping.py with credential hints
**Done:** Added import of get_strategy/requires_credentials from scraper_strategies. Added _credential_hint_for_source() helper that looks up the strategy and produces a Norwegian message naming required env vars when applicable. Extended the block_reason in _scrape_source() to append the credential hint.
**Rationale:** The lookup uses the canonical club name from the source config, matching the strategy registry key. The hint function is defensive — any exception gracefully returns empty string so scraping never crashes on hint generation.
**Findings:** The stage already has scraper_strategies import for Jutul; this extends that integration cleanly.
**Files:** tournament_scheduler/pipeline/stage2_scraping.py (+23/-1)
**Commit:** not committed
### 2026-06-10 — Add credential_env_vars field to ScraperStrategy and strategy serialisation
**Done:** Added credential_env_vars field to ScraperStrategy dataclass with default_factory=list. Added requires_credentials() helper. Set credential_env_vars=["BOOKUP_EMAIL", "BOOKUP_PASSWORD"] on Tønsberg and Sandefjord Penguins strategies. Exported in strategy_to_dict() and list_strategies(). All other strategies default to empty list.
**Rationale:** The field explicitly declares which env vars a strategy needs for auth, making it discoverable by both the Python stage2 scraping and the TypeScript extension without hardcoding club names.
**Findings:** BookUp strategies are the only ones currently needing credentials. The field is backward-compatible — all existing strategies get empty list by default.
**Files:** tournament_scheduler/pipeline/scraper_strategies.py (+12/-0)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
