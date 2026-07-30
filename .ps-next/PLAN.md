# Plan: GitHub issue 44 application-use-case slice
**Goal:** Implement a first typed application-layer slice for operator state/questions and replace one RVV CLI dispatch chain with explicit handler registration while preserving CLI behavior.
**Created:** 2026-07-30
**Intent:** GitHub issue #44 asks for typed application use cases and thinner adapters; the highest-priority already-open GitHub issues #45/#46 are already implemented in history, so this starts the next non-duplicated P1 issue with a small, testable migration slice.

## Tasks
- [x] Add typed operator state/question use cases
  - Files: tournament_scheduler/application/__init__.py, tournament_scheduler/application/dto.py, tournament_scheduler/application/operator_state.py, tests/test_application_operator_state.py
  - Approach: Create dataclass DTOs/results for operator questions and manifest health, wrap existing pipeline escalation/run-manifest APIs in pure in-process functions, and test them with temporary work directories without CLI/Rich/HTTP imports.
- [ ] Wire operator CLI handlers through the application layer
  - Files: tournament_scheduler/cli/rvv_cli.py, tests/test_escalation.py, tests/test_manifest_persistence.py
  - Approach: Keep current public output and argparse contracts, but have questions/answer/promote/health handlers call the new application functions; use a local operator subcommand handler map so patched handler functions in existing tests still route correctly.
- [ ] Document and enforce the architecture boundary slice
  - Files: docs/application-architecture.md, tests/test_application_architecture.py
  - Approach: Document dependency rules and examples for adding a use case; add lightweight import-boundary tests that prevent application modules from importing CLI, Rich console, desktop HTTP, or subprocess transport code.

## Notes
- Source issue: GitHub #44 `[P1] Refactor CLI and orchestration into typed application use cases`.
- `.ps-next/HISTORY.md` shows GitHub issues #45 and #46 already have archived implementation plans today even though they remain open on GitHub; avoid duplicating that work.
- This is deliberately a first migration slice, not the whole monolith refactor. Preserve existing `rvv-miniputt` CLI commands and JSON outputs.
- `AGENTS.md` says to use RVV command tools rather than shell slash commands and to review docs when scheduling logic changes; this slice does not change scheduling rules.

## Acceptance Criteria
- [ ] `pytest tests/test_application_operator_state.py tests/test_application_architecture.py tests/test_escalation.py tests/test_manifest_persistence.py` passes.
- [ ] `python3 -m tournament_scheduler.cli.rvv_cli operator questions --work-dir .pipeline --json` runs without parser/dispatch errors.
- [ ] `docs/application-architecture.md` contains the application dependency rules and a command/use-case addition example.
- [ ] Application modules do not import `tournament_scheduler.cli`, `tournament_scheduler.desktop_server`, `rich`, or `subprocess`.

## Log

### 2026-07-30 — Add typed operator state/question use cases
**Done:** Added a typed application package slice for operator question listing/answering/promotion and manifest health checks, with DTO round-tripping and direct use-case tests.
**Rationale:** This moves operator-state policy behind an in-process application API before adapters are rewired, matching the first incremental step of GitHub issue #44 without changing public CLI behavior.
**Findings:** Existing pipeline escalation and RunManifest APIs already provide the durable persistence primitives; the application layer can wrap them without importing CLI/Rich/HTTP transports.
**Files:** tournament_scheduler/application/__init__.py (new); tournament_scheduler/application/dto.py (new); tournament_scheduler/application/operator_state.py (new); tests/test_application_operator_state.py (new)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
