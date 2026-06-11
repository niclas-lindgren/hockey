# PLAN

**Feature:** Verify/improve driving distance calculation: current values look incorrect. Implement a more reliable algorithm to compute from-to distances between venues (e.g. using a proper geocoding/distance matrix approach) and aggregate per-team/season travel distances correctly.
**Goal:** Verify/improve driving distance calculation: current values look incorrect. Implement a more reliable algorithm to compute from-to distances between venues (e.g. using a proper geocoding/distance matrix approach) and aggregate per-team/season travel distances correctly.
**Backlog-ref:** 46
**Constraints:** none
**Date:** 2026-06-11

## Intent
The hand-typed `_DISTANCE_MATRIX` in `club_distances.py` contains rough/inconsistent guesses (e.g. Tønsberg<->Sandefjord Penguins listed as 15km when the real road distance is closer to 30km); replacing it with a coordinate-based haversine + road-correction calculation gives accurate, verifiable, offline-computable distances that feed the existing per-team/season travel aggregation correctly.

## Tasks

- [x] Replaced the static hand-tuned distance matrix in club_distances.py with a haversine-based calculation using real (lat, lon) coordinates for each of the 9 RVV club arenas, scaled by a _ROAD_DISTANCE_FACTOR of 1.3 to approximate driving distance. — 2026-06-11
  - Files: tournament_scheduler/club_distances.py
  - Add a `_CLUB_COORDINATES: Dict[str, Tuple[float, float]]` dict with real (latitude, longitude) pairs for each of the 9 RVV club arenas (Kongsberg/Kongsberghallen, Jar/Jarhallen, Holmen/Holmenkollen ishall, Ringerike/Ringerikshallen, Skien/Skien ishall, Jutul/Bærum ishall, Frisk Asker/Varner Arena, Tønsberg/Tønsberghallen, Sandefjord Penguins/Sandefjord ishall), plus a `_haversine_km(coord_a, coord_b) -> float` helper and a `_ROAD_DISTANCE_FACTOR` constant (e.g. 1.3) applied to the great-circle distance to approximate real driving distance.

- [x] This was implemented together with task 1 — distance() now computes results purely from _CLUB_COORDINATES via _haversine_km and _ROAD_DISTANCE_FACTOR, with the same-club and unknown-pair contracts preserved. — 2026-06-11
  - Files: tournament_scheduler/club_distances.py
  - Rewrite `distance(club_a, club_b) -> int` to return 0 for `club_a == club_b`, look up both clubs in `_CLUB_COORDINATES`, return 0 if either is missing (preserving the "unknown pair -> 0" contract), and otherwise return `round(_haversine_km(...) * _ROAD_DISTANCE_FACTOR)`; remove `_DISTANCE_MATRIX` and `_normalise_key` (haversine is naturally symmetric) once no longer referenced.

- [x] Verified _ARENA_TO_CLUB, arena_to_club(), furthest_traveling_team(), and compute_team_travel_distances() all continue to work unchanged against the new coordinate-based distance(); module docstring already describes the haversine + road-correction approach (updated as part of the initial rewrite). — 2026-06-11
  - Files: tournament_scheduler/club_distances.py
  - Verify these functions only depend on `distance()`/`arena_to_club()` (no direct `_DISTANCE_MATRIX`/`_normalise_key` references survive); update module docstring to describe the haversine + road-correction approach instead of "static distance lookups".

- [x] Updated test docstrings/comments to describe the haversine-based approach instead of the old static matrix, and added a new test_all_pairs_are_symmetric covering all 9x9 club pairs symmetrically; existing magic-number assertions already used distance() computed values rather than hardcoded km figures. — 2026-06-11
  - Files: tests/test_club_distances.py
  - Replace exact magic-number assertions tied to the old static matrix (e.g. "Holmen ~85km vs Jar ~80km from Kongsberg", "Kongsberg-Jar > 50") with assertions appropriate to the new haversine-based values: same-club returns 0, symmetric for all club pairs, all 9x9 distinct-club pairs > 0, and `furthest_traveling_team`/`compute_team_travel_distances` pick the team with the actual greater computed `distance()` (computed via the function itself rather than hardcoded km figures) so tests stay correct if coordinates are later refined.

- [ ] Add a unit test for the haversine + road-correction calculation itself
  - Files: tests/test_club_distances.py
  - Add a `TestHaversineDistance` (or similar) test class that checks: distance between identical coordinates is 0, a known real-world pair (e.g. Kongsberg <-> Oslo-area clubs such as Jar) falls within a realistic km range (e.g. 60-100km, reflecting the corrected Tønsberg<->Sandefjord ~30km style fix), and the result scales with the `_ROAD_DISTANCE_FACTOR` (i.e. is greater than the raw great-circle haversine distance).

- [ ] Verify downstream consumers still render correctly with the new distances
  - Files: tournament_scheduler/excel/plan_exporter.py, tournament_scheduler/utils/rich_output.py, tournament_scheduler/html/html_exporter.py, tournament_scheduler/cli/season_command.py, tournament_scheduler/csv/csv_exporter.py
  - Run `pytest` across the full suite (these modules only call `distance()`/`furthest_traveling_team()`/`compute_team_travel_distances()` through the existing public API, so no signature changes are expected); spot-check by running the season-plan generation CLI and confirming travel-distance figures in HTML/CSV/Excel output now reflect realistic km values (e.g. Tønsberg<->Sandefjord Penguins around 25-35km, not 15km).

## Acceptance Criteria

- `tournament_scheduler/club_distances.py` no longer contains `_DISTANCE_MATRIX` or `_normalise_key`, and `distance()` computes its result from `_CLUB_COORDINATES` via a haversine helper.
- Running `pytest tests/test_club_distances.py` passes with no failures, including new tests for the haversine+road-correction calculation.
- `distance("Tønsberg", "Sandefjord Penguins")` returns a value in the 20-40km range (correcting the previous incorrect 15km static estimate).
- `distance(club, club)` returns 0 for every club, and `distance(a, b) == distance(b, a)` for every pair of the 9 RVV clubs.
- Running the full `pytest` suite from the repo root exits with code 0, confirming downstream exporters (Excel, CSV, HTML, CLI, rich output) still produce output using the new distance values without errors.

## Log
- 2026-06-11: Plan created for backlog item #46 (driving distance calculation fix).

### 2026-06-11 — Replaced the static hand-tuned distance matrix in club_distances.py with a haversine-based calculation using real (lat, lon) coordinates for each of the 9 RVV club arenas, scaled by a _ROAD_DISTANCE_FACTOR of 1.3 to approximate driving distance.
**Rationale:** none
**Findings:** distance() now computes great-circle distance via _haversine_km and applies the road factor; the old _DISTANCE_MATRIX and _normalise_key were removed. One existing test asserted Holmen was farther than Jar from Kongsberg based on old approximate numbers, but real coordinates show Jar (~75km) is actually farther than Holmen (~64km), so that test assertion was corrected to match.
LESSONS: Real coordinates change relative ordering of some club distances vs the old hand-picked matrix; downstream code/tests assuming old relative orderings (e.g. Jar vs Holmen distance from Kongsberg) need updating to match real-world geography.
**Files:** tournament_scheduler/club_distances.py (+84/-71 combined with test), tests/test_club_distances.py (+3/-2)
**Commit:** f17fbf2 (hockey)

### 2026-06-11 — This was implemented together with task 1 — distance() now computes results purely from _CLUB_COORDINATES via _haversine_km and _ROAD_DISTANCE_FACTOR, with the same-club and unknown-pair contracts preserved.
**Rationale:** none
**Findings:** Verified no remaining references to _DISTANCE_MATRIX or _normalise_key in club_distances.py; the rewrite was already completed in the prior task's commit.
LESSONS: none
**Files:** none (already implemented in previous commit)
**Commit:** 1b4b47f (hockey)

### 2026-06-11 — Verified _ARENA_TO_CLUB, arena_to_club(), furthest_traveling_team(), and compute_team_travel_distances() all continue to work unchanged against the new coordinate-based distance(); module docstring already describes the haversine + road-correction approach (updated as part of the initial rewrite).
**Rationale:** none
**Findings:** No code changes needed — these functions only call distance()/arena_to_club() and never referenced _DISTANCE_MATRIX or _normalise_key directly; docstring already updated in the first commit.
LESSONS: none
**Files:** none (verification only, no file changes)
**Commit:** bbfc222 (hockey)

### 2026-06-11 — Updated test docstrings/comments to describe the haversine-based approach instead of the old static matrix, and added a new test_all_pairs_are_symmetric covering all 9x9 club pairs symmetrically; existing magic-number assertions already used distance() computed values rather than hardcoded km figures.
**Rationale:** none
**Findings:** All 19 tests pass (added 1 new test). Comments referencing old approximate matrix values (e.g. 'Kongsberg -> Jar is ~80 km') were removed since the magic numbers no longer applied.
LESSONS: none
**Files:** tests/test_club_distances.py (+12/-2)
**Commit:** [pending — fill after commit]
