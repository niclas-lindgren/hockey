# Plan: Per-team travelled distance metrics in HTML report
**Goal:** The HTML season report shows each team's total travel distance over the season and flags the team with the highest burden.
**Created:** 2026-06-10
**Intent:** Organizers need to see which teams bear the heaviest travel load across the season — especially useful for fairness discussions and potential scheduling adjustments.
**Backlog-ref:** 33

## Tasks
- [x] Add `compute_team_travel_distances(plan: SeasonPlan) -> dict` to `club_distances.py`
  - Files: tournament_scheduler/club_distances.py
  - Approach: Iterates all tournaments in the plan; for each team in a tournament where the host club differs from the team's club, looks up `distance(team_club, host_club)` and accumulates it. Returns a dict mapping team label → total km. Uses `arena_to_club()` and falls back to `tournament.host_club` for host resolution (same pattern as `furthest_traveling_team`). Skips cancelled tournaments.

- [x] Expose per-team travel distances and "most-traveled" team in HtmlExporter
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: Call `compute_team_travel_distances(plan)` during export. Serialize result to JSON for the template. Compute the max-travel team (name + km) from the dict. Add `$TEAM_TRAVEL_JSON$` and `$MOST_TRAVEL_TEAM$` / `$MOST_TRAVEL_KM$` template placeholders. Render a new collapsible `<details>` table under the existing "Kamper per lag" block, sorted by distance descending with the top team highlighted in amber.

- [x] Add unit tests for `compute_team_travel_distances`
  - Files: tests/test_club_distances.py
  - Approach: Test with a small SeasonPlan with known distances — verify correct accumulation, that cancelled tournaments are skipped, that local tournaments (same club as host) yield 0 addition, and that the dict keys match team labels.

## Acceptance Criteria
- [ ] `grep:SeasonPlan\) -> dict` matches a type annotation in tournament_scheduler/club_distances.py
- [ ] The generated HTML contains a "Reiseavstand per lag" section with a `<details>` element.
- [ ] `run:pytest tests/test_club_distances.py -x -q` passes with the new tests.
- [ ] The most-traveled team is visually distinct in the HTML (amber/highlight styling).

## Log



### 2026-06-10 — Add unit tests for `compute_team_travel_distances`
**Done:** Added 6 new unit tests covering: empty plan, local tournament (zero), accumulation across multiple away tournaments, cancelled tournaments skipped, unknown host arena handling, and dict key correctness
**Rationale:** Tests cover all edge cases in the acceptance criteria. Fixed a minor implementation issue during testing — teams from unknown-host tournaments were not registered in the dict; now they are registered with 0 km.
**Findings:** Fixed bug discovered during testing: skipped tournaments previously never registered team labels in the result dict. Moved team registration to happen before the host_club bail-out. club_distances.py now at 100% line coverage.
**Files:** tests/test_club_distances.py (+97 lines: new TestComputeTeamTravelDistances class + import)
**Commit:** not committed
### 2026-06-10 — Expose per-team travel distances and "most-traveled" team in HtmlExporter
**Done:** Added per-team travel distances table to HTML report — new collapsible "Reiseavstand per lag" section with amber highlight on most-traveled team, away-tournament count column, and summary text in the section header
**Rationale:** Added compute_team_travel_distances call in export(), serialized to JSON for the template. Template has new $TEAM_TRAVEL_JSON$, $MOST_TRAVEL_TEAM$, $MOST_TRAVEL_KM$, $TRAVEL_COUNT_ESTIMATE_HTML$ markers. JS renderer sorts by distance desc, highlights max-travel team with amber background, car emoji, and "(lengst reisevei)" label. Away-tournament counts computed client-side from TOURNAMENTS data.
**Findings:** Module imports cleanly. All 12 existing tests pass unchanged. Pre-existing @staticmethod duplication on _plan_to_json is existing code — not introduced here.
**Files:** tournament_scheduler/html/html_exporter.py (+60 lines: import, Python computation, template markers, HTML table + JS renderer)
**Commit:** not committed
### 2026-06-10 — Add `compute_team_travel_distances(plan: SeasonPlan) -> dict` to `club_distances.py`
**Done:** Added compute_team_travel_distances() to club_distances.py — iterates non-cancelled tournaments, resolves host club, accumulates away distances per team label
**Rationale:** Follows the same host-resolution pattern as furthest_traveling_team (arena_to_club fallback to host_club). Type-annotated return dict[str, int] to pass acceptance criterion `grep` check.
**Findings:** All 12 existing tests pass unchanged. The new function is not yet exercised by any test (will be added in task 3).
**Files:** tournament_scheduler/club_distances.py (+36 lines)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
