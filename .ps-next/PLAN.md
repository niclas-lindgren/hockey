# Plan: Per-club dashboard view in HTML report
**Goal:** When a user selects a club in the filter dropdown, a focused summary card appears showing that club's season at a glance: tournaments hosted, away tournaments, total travel distance, and team roster.
**Created:** 2026-06-10
**Intent:** Each club contact can open the report, select their club, and immediately see their season summary without digging through all 9 clubs.
**Backlog-ref:** 27

## Tasks
- [x] Compute per-club aggregate stats in HtmlExporter.export()
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Build a `CLUB_STATS` dict from the plan tournaments. For each club: count of tournaments hosted (non-cancelled), count of tournaments where club's teams participate but are not hosting ("away"), list of team labels for that club, and total travel km (reuse existing travel dict). Serialize as `$CLUB_STATS_JSON$`. Also add `$ALL_CLUBS_JSON$` (sorted list of all host clubs).

- [x] Add club dashboard summary card to HTML template
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Add a hidden `#clubDashboard` div between the score bar and team-stats sections. Contains four stat badges (hostet, borte, reise, lag) that populate dynamically when a specific club is selected in the filter. Wire the club filter's `change` event to show/hide and populate the dashboard. Use amber styling for the dashboard to match the travel section.

## Acceptance Criteria
- [ ] Selecting a club in the filter dropdown shows a club dashboard summary card with hosted count, away count, total travel km, and team count.
- [ ] `run:pytest tests/test_stage4_export.py -x -q` passes.
- [ ] Clearing the club filter removes the dashboard card from view.

## Log


### 2026-06-10 — Add club dashboard summary card to HTML template
**Done:** Added club dashboard card: hidden by default, appears when a club is selected in filter. Shows 4 stat badges (hosted, away, travel km, teams) with coloured icons and amber left border. Clears on filter reset.
**Rationale:** Dashboard uses existing stat-badge component with club-specific colours. Wired to filterClub change event and filterClear click. Ambert-style left border and header make it visually distinct from surrounding sections.
**Findings:** Added back filterSearch listener that was accidentally removed in first edit. FilterClear now hides dashboard AND resets filters as before.
**Files:** tournament_scheduler/html/html_exporter.py (+55 lines: HTML dashboard section, JS wiring, CSS)
**Commit:** not committed
### 2026-06-10 — Compute per-club aggregate stats in HtmlExporter.export()
**Done:** Computed per-club stats: hosted count, away count, team count, travel km, team list. Serialized as CLUB_STATS_JSON and ALL_CLUBS_JSON for template.
**Rationale:** Club hosted/away counts derived from tournament host_club and team.club membership. Travel km summed from per-team travel dict matched to clubs by label prefix. Team lists collected from tournament.teams.
**Findings:** html_exporter.py at 82% coverage (up from 78%). All 25 tests pass.
**Files:** tournament_scheduler/html/html_exporter.py (+44 lines: club stats computation + template markers)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
