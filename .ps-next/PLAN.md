# Plan: Capacity-aware host and slot selection
**Goal:** The season planner should pick host clubs and start slots together so it avoids unnecessary fallback hosts when another club has a viable slot on the same date.
**Created:** 2026-06-22
**Intent:** Make host assignment reflect each club's real calendar capacity instead of only balancing host counts on paper.
**Backlog-ref:** 195

## Tasks
- [x] Add capacity-aware fallback host substitution during plan assembly
  - Files: tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py
  - Approach: after participants and games are known for a tournament, probe the originally assigned host's slot first, then search eligible fallback clubs in age-group order for the earliest viable slot on that date; if a fallback is chosen, update arena/host/start time together and record the substitution so downstream reports stay accurate.
- [x] Refresh rules/report wording and add regression coverage for fallback-host behavior
  - Files: tournament_scheduler/rules_report.py, tests/test_season_planner.py, tests/test_host_assignment.py
  - Approach: update the explanatory text so it describes when host substitution is allowed, and add tests for (1) keeping the original host when no fallback slot exists and (2) selecting a fallback host when the original arena is full but another club has capacity.

## Notes
The current planner already has `fallback_host_substitutions` plumbing and a host-first/home-team invariant, but it never actually swaps hosts when a slot is unavailable. Any change must preserve home-team ordering, same-day arena collision handling, and the existing default-start-time fallback.

## Acceptance Criteria
- [ ] A tournament with no slot in its assigned host arena can switch to a fallback host with a viable slot on the same date, and the substitution is recorded.
- [ ] When no club has a viable slot, the planner keeps the original host and default start time.
- [ ] `pytest` passes for the host-assignment and season-planner coverage added for this behavior.

## Log


### 2026-06-22 — Refresh rules/report wording and add regression coverage for fallback-host behavior
**Done:** Updated the rules report text and added regression coverage for both fallback-host selection and the no-slot fallback case.
**Rationale:** The user-facing explanation had to match the new behavior, and the regression tests lock down both the successful cross-club fallback path and the preserve-original-host path when nothing is available.
**Findings:** The existing no-slot test already covered the preserve-original-host case; the new coverage focuses on the successful cross-club fallback path. The new host-assignment unit test exercises the reusable slot search helper directly.
**Files:** tournament_scheduler/rules_report.py, tests/test_host_assignment.py, tests/test_season_planner.py
**Commit:** not committed
### 2026-06-22 — Add capacity-aware fallback host substitution during plan assembly
**Done:** Planner now probes candidate host clubs in priority order, falls back when the original arena has no viable slot, and records the chosen substitution.
**Rationale:** The host decision needs to happen together with slot lookup so the planner can avoid unnecessary fallback hosts instead of locking in the first theoretical host and discovering the calendar is full later.
**Findings:** Candidate ordering based on age-group host targets plus current assigned host counts was enough to keep the selection fair while still honoring a real slot. The fallback path also exposed a stale arena alias in club_for_arena('Varner Arena'), so the reverse lookup now accepts slash-separated arena aliases; otherwise the existing host-resolution tests would fail against the current registry label.
**Files:** tournament_scheduler/season_planner.py, tournament_scheduler/host_assignment.py, tournament_scheduler/club_registry.py, tournament_scheduler/rules_report.py, tests/test_host_assignment.py, tests/test_season_planner.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
