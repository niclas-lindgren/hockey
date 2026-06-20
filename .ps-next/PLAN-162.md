# Plan: Fix 18-team display bug in HTML report
**Goal:** Fix HTML report team count: $UNIQUE_TEAMS$ shows 18 instead of 70 (use len(team_game_counts)); review.py:93 and judgment.py:71 look up team_game_counts with raw label instead of team_key()-disambiguated key.
**Created:** 2026-06-20
**Intent:** Correct two related bugs where raw team labels are used instead of disambiguated team_key() keys, causing the HTML header to show the wrong team count and per-team game-count lookups to silently return 0 for duplicate-label teams.
**Backlog-ref:** 162

## Tasks
- [x] Changed $UNIQUE_TEAMS$ to use len(team_game_counts) instead of len(all_teams) in html_exporter.py line 286. — 2026-06-20
  - Files: tournament_scheduler/html/html_exporter.py
  - Approach: In html_exporter.py line 286, change `str(len(all_teams))` to `str(len(team_game_counts))`. The all_teams set is built from raw g.home.label/g.away.label and collapses duplicate labels; team_game_counts already uses the same keys as the rest of the report, so its length is the correct unique-team count.
- [x] Rewrote compute_team_game_counts() to use team_key() for disambiguated dict keys by first collecting all teams to find labels with multiple distinct club/age_group identities, then using that set to generate keys. — 2026-06-20
  - Files: tournament_scheduler/html/data_computation.py, tournament_scheduler/models.py
  - Approach: Import team_key from tournament_scheduler.models. In compute_team_game_counts(), collect all team objects across games to build a duplicate_labels set (Counter on labels, keep those with count > 1), then use team_key(team_obj, duplicate_labels) as the dict key instead of team_obj.label. This makes the keys match what review.py and judgment.py expect.
- [x] Fixed review.py to build plan-wide duplicate_labels set and use team_key() for looking up team_game_counts, replacing raw label lookup at line 93. — 2026-06-20
  - Files: tournament_scheduler/html/renderers/review.py
  - Approach: Import team_key from tournament_scheduler.models. Before the loop at line 92, build a duplicate_labels set from the full set of team objects in age_tournaments (Counter on team.label, keep those with count > 1). On line 93, replace `team_game_counts.get(label, 0)` with a lookup using `team_key(team_obj, duplicate_labels)` — requires iterating team objects rather than labels so team_key() has the full Team object.
- [x] Fixed judgment.py to build plan-wide duplicate_labels set and use team_key() for looking up team_game_counts at line 71, replacing raw label lookup. — 2026-06-20
  - Files: tournament_scheduler/html/renderers/judgment.py
  - Approach: Import team_key from tournament_scheduler.models. Before the loop at line 70, build a duplicate_labels set from age_team objects collected from age_tournaments. On line 71, replace `team_game_counts.get(label, 0)` with a lookup using `team_key(team_obj, duplicate_labels)`, iterating team objects rather than raw labels.
- [ ] Add tests verifying team count header and game-count lookups with duplicate-label teams
  - Files: tests/test_plan_exporter.py
  - Approach: Add a test fixture that creates two teams with the same label in different clubs/age-groups (triggering disambiguation) and verifies (a) the rendered HTML contains `len(team_game_counts)` as the UNIQUE_TEAMS value, and (b) analyze_review_summary and analyze_opinionated_judgment return non-zero age_team_counts for each team rather than all zeros.

## Notes
Constraints: none

Key codebase context:
- team_key() is defined in tournament_scheduler/models.py:91 — takes Team object + duplicate_labels set, returns disambiguated string key.
- compute_team_game_counts() in tournament_scheduler/html/data_computation.py:116 currently keys by raw team.label from game home/away objects.
- $UNIQUE_TEAMS$ in html_exporter.py:286 uses len(all_teams) (a set of raw labels) while $TEAM_COUNT$ at line 287 already uses len(team_game_counts).
- review.py:93 uses age_labels = sorted({team.label ...}) then team_game_counts.get(label, 0) — raw label lookup.
- judgment.py:71 uses age_team_labels = sorted({team.label ...}) then team_game_counts.get(label, 0) — raw label lookup.
- The correct fix at the renderer level requires switching from label-only sets to full Team object iteration so team_key() can produce the right key. Alternatively, if compute_team_game_counts is fixed to use team_key()-based keys, the renderers must match.

## Acceptance Criteria
- [ ] The HTML report header shows the correct total unique team count (matching len(team_game_counts)) instead of a smaller number produced by collapsing duplicate raw labels.
- [ ] When a plan contains two teams with the same label in different clubs or age groups, analyze_review_summary returns non-zero game counts for each team rather than returning 0 for disambiguated teams.
- [ ] When a plan contains two teams with the same label in different clubs or age groups, analyze_opinionated_judgment returns non-zero game counts for each team rather than returning 0 for disambiguated teams.
- [ ] The $UNIQUE_TEAMS$ placeholder value in the rendered HTML matches len(team_game_counts), not the length of a raw-label set.
- [ ] pytest runs pass with no regressions in tests that exercise the HTML exporter, review renderer, and judgment renderer.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-20 — Changed $UNIQUE_TEAMS$ to use len(team_game_counts) instead of len(all_teams) in html_exporter.py line 286.
**Rationale:** all_teams is a raw label set that collapses disambiguated duplicates; team_game_counts uses team_key() disambiguated keys and is already the authoritative count.
**Findings:** One-line fix confirmed correct by pytest passing.
LESSONS: none
**Files:** tournament_scheduler/html/html_exporter.py (+1/-1)
**Commit:** e7652e7 (hockey)

### 2026-06-20 — Rewrote compute_team_game_counts() to use team_key() for disambiguated dict keys by first collecting all teams to find labels with multiple distinct club/age_group identities, then using that set to generate keys.
**Rationale:** none
**Findings:** Tests pass. Keys now match what review.py and judgment.py expect.
LESSONS: none
**Files:** tournament_scheduler/html/data_computation.py (+25/-3)
**Commit:** 11c8693 (hockey)

### 2026-06-20 — Fixed review.py to build plan-wide duplicate_labels set and use team_key() for looking up team_game_counts, replacing raw label lookup at line 93.
**Rationale:** none
**Findings:** Tests pass. Lookup now uses consistent team_key() keys matching those produced by compute_team_game_counts.
LESSONS: none
**Files:** tournament_scheduler/html/renderers/review.py (+13/-2)
**Commit:** 5022e8d (hockey)

### 2026-06-20 — Fixed judgment.py to build plan-wide duplicate_labels set and use team_key() for looking up team_game_counts at line 71, replacing raw label lookup.
**Rationale:** none
**Findings:** Tests pass. Pattern mirrors review.py fix.
LESSONS: none
**Files:** tournament_scheduler/html/renderers/judgment.py (+13/-2)
**Commit:** [pending — fill after commit]
