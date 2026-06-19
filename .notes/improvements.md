# RVV Miniputt — Improvements WIP

_Coordination doc. Updated by agents as findings land._

---

## Status

| Area | Agent | Status |
|---|---|---|
| Pipeline functions (stage1–4) | pipeline-review | ✅ done |
| Report quality / layout | report-review | ✅ done |
| Subjective weight in planning | planning-review | ✅ done |

---

## Findings

_(populated by agents below)_

### Pipeline functions

#### Stage 1 — config

- **`stage1_config.py: load_effective_config`** — silently returns `{}` when no Stage 1 checkpoint exists, but callers (e.g. Stage 4's `run`) ignore the empty return and call `.get()` on it without checking; any missing-checkpoint scenario produces silent wrong behaviour rather than a clear error.
- **`stage1_config.py: run`** — writes the checkpoint twice in the happy path (once as `RUNNING` with an empty dict, once as `DONE` with data) and also calls `mark_done` after `write_stage(..., status=DONE)`, which calls `_invalidate_downstream` twice and double-stamps `updated_at`; the second `write_stage` already sets status, so `mark_done` is redundant.
- **`stage1_config.py: run`** — the `__main__` block calls `_load_json` a second time after `run()` just to print `start_date`/`end_date`; those values are already available from `load_effective_config` and the double read is wasteful.
- **`stage1_helpers.py: _load_json`** — the function name is a lie: it loads an Excel workbook, not JSON; the misnamed function makes the code harder to read and the docstring admits the name is kept only for "compatibility", suggesting it should be renamed `_load_workbook_config` with an import alias to preserve callsites.
- **`stage1_helpers.py: validate_config`** — validates `teams` as a file path by checking `Path(teams_val).exists()` with no CWD anchor, meaning the check passes or fails based on wherever the process was launched from, not the location of `input.xlsx`; the path should be resolved relative to `input_path`.
- **`stage1_helpers.py: _parse_config`** — uses the bare name `Dict` (from typing) at line 49 of stage3_helpers.py (wrong file noted below), but in `_parse_config` itself the `participations` computation is actually in `_plan_to_dict` in stage3_helpers — no issue here; however, `_parse_config` silently drops unknown keys from `raw` with no warning, so user typos (e.g. `"targt_tournament_count"`) are swallowed.
- **`stage1_helpers.py: _validate_team_list`** — does not check for duplicate `label` values; two teams with the same label will cause silent collisions later in Stage 3's `_find_team` lookup.

#### Stage 2 — scraping

- **`stage2_scraping.py: run`** — uses a module-level global `_CALENDAR_CACHE` (line 38/135) that is reassigned inside `run` on each call; this is not thread-safe if `run` is ever called concurrently and is an anti-pattern — the cache should be passed as a parameter or constructed locally.
- **`stage2_scraping.py: run`** — writes `status=FAILED` + calls `mark_failed` for the no-sources strict path (lines 124–126), which calls `_invalidate_downstream` twice (same double-stamp bug as Stage 1).
- **`stage2_scraping.py: run`** — `checkpoint_path` (the string path to the checkpoint file) is stored inside the checkpoint data dict (line 227); this mixes pipeline metadata into the stage payload and will confuse consumers reading `state.read_stage(StageName.SCRAPING)`.
- **`stage2_scraping.py: _scrape_source`** — always calls `_try_credentialed_scrape` when zero events are returned even if the deterministic scrape threw an unrelated error (network timeout, parse crash); the credentialed path should only run when the deterministic path succeeded but returned 0 events, not when it raised.
- **`stage2_scraping.py: _scrape_source`** — hardcodes URL substring checks (`"baerumishall.no"`, `"bookup.no"`) directly in the dispatch block; this ad-hoc routing should be moved to `scraper_strategies.py` alongside the existing `get_strategy` / `needs_llm_agent` logic, otherwise adding a new special-case source requires editing the core scraping loop.
- **`stage2_helpers.py`** — this file is a pure re-export facade; `stage2_scraping.py` imports all helpers from it, but `stage2_helpers.py` just re-exports from the real sub-modules; the indirection adds no value and `stage2_scraping.py` should import from the sub-modules directly.

#### Stage 3 — planning

- **`stage3_planning.py: run`** — `scraping_result` is documented as "currently unused but stored in the checkpoint for traceability", yet it is immediately passed to `_build_events_by_club` and used; the docstring is stale and misleading.
- **`stage3_planning.py: run`** — re-reads `existing_checkpoint` before writing `RUNNING` status, which is correct for preserving manual adjustments, but if the existing checkpoint is `STALE` the manual adjustments are still blindly carried forward; there is no check that the stale checkpoint's adjustments still correspond to valid tournament IDs in the new plan.
- **`stage3_helpers.py: _plan_to_dict`** — uses the bare `Dict` annotation (line 49: `participations: Dict[str, int] = {}`) without importing it; this is a `NameError` at runtime on Python 3.9 unless `from __future__ import annotations` defers evaluation — and indeed the file has that import, but it is fragile and inconsistent with the `dict[str, Any]` style used everywhere else in the file.
- **`stage3_helpers.py: _tournament_from_dict`** — this function is imported in `stage3_planning.py`'s `__init__` import list but never called anywhere in `stage3_planning.py`; it appears to be dead code in the pipeline (possibly left over from an earlier approach to re-hydrating tournaments for patching).
- **`stage3_helpers.py: _build_club_arenas`** — ignores `config` entirely and reads only from the global `CLUB_REGISTRY`; the `config` parameter is unused, making the function signature misleading — either remove the parameter or fall back to config-provided arenas before the registry.
- **`stage3_helpers.py: _build_events_by_club`** — silently skips malformed event dicts with a bare `except (KeyError, ValueError): continue`; scraping errors that corrupt a single event field will cause that event to be dropped without any log or warning, making calendar conflicts invisible.

#### Stage 4 — export

- **`stage4_export.py: run`** — reads the scraping checkpoint directly from `state.read_stage(StageName.SCRAPING)` to compute `pipeline_meta`, then also reads the `ScrapedDataCache` separately for `meta`; both reads occur inside nested `try/except Exception: pass` blocks with no logging, so cache-read failures are silently swallowed.
- **`stage4_export.py: run`** — `updated_at` is read from `scraping_ckpt` (line 166) but `read_stage` returns only the `data` payload, not the envelope; `updated_at` is an envelope field and will never be present in `scraping_ckpt`, making `scrape_age` always empty — should use `state.read_envelope(StageName.SCRAPING)`.
- **`stage4_export.py: run`** — the `strict` parameter controls whether errors raise, but when `strict=True` the checkpoint is written with `FAILED` status and then `mark_failed` is also called (line 241–242), again double-calling `_invalidate_downstream`.
- **`stage4_export.py: run`** — constructs `html_report` path (line 197) by string manipulation of `html_path` rather than by asking the exporter what it produced; if `HtmlExporter.export` changes its output file naming, `html_report` will silently point to a non-existent file.
- **`stage4_helpers.py: _dict_to_plan`** — when a game references a team label not in the tournament's `team_by_label` dict, the game is silently dropped (lines 29–38); this means corrupted or manually edited checkpoints can produce a plan with fewer games than expected, with no warning.
- **`stage4_helpers.py: _dict_to_plan`** — falls back to `date.today()` when a tournament's `date` field is missing or empty (line 41–42); a missing date should be an error, not a silent default to today.

#### state.py — cross-cutting

- **`state.py: PipelineState.write_stage`** — calls `_invalidate_downstream` when status is `DONE` or `FAILED`; invalidating downstream on `DONE` means that successfully completing a stage always marks later stages as stale, which is correct for re-runs, but it also means the first time a stage completes it immediately stales downstream stages that haven't run yet — those stages will show `stale=True` before they've even been attempted, which may confuse status displays.
- **`state.py: PipelineState._set_status`** — used by both `mark_done` and `mark_failed`, and also calls `_invalidate_downstream` — so any caller that does `write_stage(..., status=DONE)` followed by `mark_done` triggers `_invalidate_downstream` twice; this pattern appears in every stage's `run` function and should be fixed by removing the redundant `mark_done`/`mark_failed` calls from callers, or by making `write_stage` the single place that sets final status.
- **`state.py: PipelineState.stages_to_run`** — raises `ValueError` if a stage before `resume_from` is not done, but `is_done` returns `False` for both `PENDING` and `FAILED` stages; when resuming after a previous failure the error message says "not done yet (status: failed)" which is confusing — it should distinguish "never ran" from "ran and failed".

### Report

#### Section inventory and order

The report (`report_overview.html` template) renders these sections in this order:

1. **Hero verdict block** — "Kan planen brukes?" with pass/warn/fail pill and status cards (tournaments, games, sources, blocked, date range, age groups, host clubs, missing hosts)
2. **"Hva må sjekkes eller endres?"** — action list
3. **"Hvorfor fikk planen denne vurderingen?"** — rule transparency
4. **"Hva skjer per aldersgruppe?"** — age group summary
5. **"Hva må hver klubb vurdere?"** — club summary
6. **"Hva sier den manuelle etterkontrollen?"** — advisory review (`review.py`)
7. Scores bar (`$SCORES$`)
8. Metrics bar (`$METRICS$`)
9. Fairness gate panel (`$FAIRNESS_ADJUSTMENTS$`)
10. Club dashboard (`$CLUB_DASHBOARD$`)
11. Team stats (`$TEAM_STATS$`)
12. Travel stats (`$TRAVEL_STATS$`)
13. Calendar heatmap (`$HEATMAP$`)
14. **Judgment section** (`judgment.py` renderer, `$JUDGMENT$`)
15. Timeline filter controls + tournament cards

This ordering has problems:
- The hero verdict and the separate judgment section (`$JUDGMENT$`) are both high-level summaries but are separated by 8 sections of detail. The reader gets a verdict, then drowns in data tables, then gets another layer of qualitative judgment at the bottom.
- Scores, metrics, and fairness adjustments appear after the per-club/per-age-group narrative sections, so the raw numbers are below the conclusions they support.
- Advisory review ("Hva sier den manuelle etterkontrollen?") and the judgment section both contain qualitative commentary — two separate "what do I think of this?" blocks is confusing.

#### Redundant sections

The `review.py` renderer's sections overlap with content shown elsewhere:

- **"Manglende klubber"** — already surfaced in the hero status cards (`len(missing_hosts)`)
- **"Hjemmeturneringer per aldersgruppe"** — repeats data from the age group summary (section 4)
- **"Kampbredde per aldersgruppe"** — repeats min/max game spread already shown in the judgment section's game load card
- **"Hoppet over"** — skipped age groups are already visible in the age group summary

In practice, advisory review and the judgment section both produce qualitative verdicts with overlapping inputs. Consider collapsing these into one section.

#### Why the conclusion always looks the same

The subjective conclusion is built from three fixed-string branches in `_report_overview_html` (Norwegian, no f-string variables):

**Pass branch:**
```
" Min egen vurdering: dette holder faktisk godt."
" Jeg ville primært brukt denne som bekreftelse, ikke som advarsel."
```

**Warn branch:**
```
" Min egen vurdering: dette er brukbart, men litt mer skjørt enn tallene alene sier."
" Jeg ville lest dette som et tegn på at den er nær, men ikke helt i mål."
```

**Fail branch:**
```
" Min egen vurdering: dette er ikke klart ennå."
" Her bør du stole mer på den kritiske lesningen enn på det positive toppsjiktet."
```

The branch is selected solely by `fairness_gate.status` (pass/warn/fail). No other per-run data is injected. Three runs with the same fairness status produce identical conclusion text regardless of how many tournaments were planned, how spread out the season is, or how many issues were found.

#### Per-run data that could make the conclusion dynamic

The following values are computed but not referenced in the conclusion text:

1. **`len(active_tournaments)`** — total non-cancelled tournaments. Reference it: "Planen inneholder N turneringer over M måneder." This is specific to every run.
2. **`pairwise_matchup_score` + `diversity_score` + `month_balance_score`** — three float scores from `judgment.py`. Naming the weakest one ("Månedsspredning er lav [0.62]") makes the warn text concrete rather than generic.
3. **`most_travel_km` / `most_travel_team`** — from `data_computation.py`. The farthest-travelling team name is unique per run: "Lag som reiser mest er X med ca. N km."
4. **`len(blocked)`** — number of blocked scrape sources. Zero blocked is a positive signal worth naming; one or more is a concrete warning: "N kildeblokkeringer kan gjøre noen turneringsdetaljer usikre."
5. **Fairness gate sub-score that triggered warn/fail** — `fairness_gate` contains per-metric status. Name the specific metric that caused the downgrade: "Utjevning feilet på Kampantall-balanse [score 0.44]" rather than a generic warning.

#### Layout and skimmability improvements

- **Merge judgment + hero verdict.** Move the qualitative judgment text from `$JUDGMENT$` up into the hero block (or directly below it) so all qualitative assessment is in one place.
- **Collapse the advisory review section by default.** The `<details>` collapsible pattern is already used for the timeline; apply it to "Hva sier den manuelle etterkontrollen?" since it duplicates content that is already surfaced as action items.
- **Group numeric detail sections under a single collapsible "Detaljer" accordion.** Scores, metrics, fairness adjustments, club dashboard, team stats, and travel stats are reference material — put them behind a single expand toggle so the main narrative fits above the fold.
- **Add a prominent "N issues to resolve" count in the hero block.** The action list exists but its count is not summarised in the verdict pill, forcing the reader to scroll to see if there is anything to do.
- **The heatmap** is useful but appears well below the fold. Consider moving it immediately after the hero block — it is the fastest way to see the season shape at a glance.


### Planning / subjective weight

#### How stage3 currently scores dates

Stage3 delegates date selection to `SeasonPlanner._pick_spread_dates` in
`tournament_scheduler/season_planner.py`. The scoring is **numeric, not binary**.
`_score_candidate_date` (lines ~382–403) computes a float from two penalty terms:

- **repeat_penalty** — average previous matchup count from `_opponent_history`; discourages
  teams from seeing the same opponents across tournaments.
- **month_penalty** — deviation of the month's load from the expected average; spreads
  tournaments evenly across the season.

`_pick_spread_dates` then does a **greedy argmin** over those scores subject to overlap
constraints — it picks the lowest-scoring (least-penalised) available date at each step.
There is no global optimisation or backtracking.

The Excel workbook (`input_workbook.py`) currently exposes per-team fields (`club`,
`label`, `age_group`, `region`, `skill_level`, `target_tournament_count`) and per-age-group
fields (`parallel_games`, `round_length_minutes`). There are **no priority or weight
fields** anywhere in the input schema today.

#### Where a subjective weight would plug in

The natural injection point is `_score_candidate_date`. It already returns a composite
float; a tournament- or date-level bias term can simply be added:

```
score = repeat_penalty + month_penalty + subjective_weight(tournament, date)
```

Because `_pick_spread_dates` takes the argmin of `score`, a **positive** weight
*penalises* a date (makes it less attractive) and a **negative** weight *rewards* it
(makes it more attractive). The sign convention should be documented clearly.

Two distinct weight axes are useful:

1. **Per-tournament preference** — e.g. "the club hosting this tournament prefers
   specific weekends" or "this tournament should be scheduled early in the season".
   Stored once per tournament row.

2. **Per-date/weekend bias** — e.g. "Easter weekend is undesirable for all
   tournaments". Stored as a list of (date-range, delta) rules in a global settings
   sheet.

#### UX / input schema sketch

Recommended approach: add one optional column to each relevant Excel sheet.

| Sheet | New column | Type | Meaning |
|---|---|---|---|
| `Aldersgrupper` (or a `Turneringer` sheet) | `preferanse_vekt` | float, default 0.0 | Per-tournament bias added to score. Negative = prefer, positive = avoid. |
| New sheet `Datopreferanser` | `fra`, `til`, `vekt` | date, date, float | Date-range rules applied to every tournament during that window. |

The `Innstillinger` sheet could also hold a global `vekt_skala` multiplier (default 1.0)
to let operators tune how strongly preferences override the spread/repeat logic without
editing every row.

#### Risks

1. **Crowding** — a strongly negative (preferred) tournament will monopolise the best
   dates, leaving poor options for the rest. Mitigation: cap the per-tournament weight
   magnitude (e.g. ±2× max organic penalty) and document the cap.

2. **Opacity** — when a surprising date is chosen, operators won't know if the weight
   caused it. Mitigation: include the raw weight term in the stage3 debug output / plan
   JSON alongside the existing `diversity_score`, `pairwise_matchup_score`, and
   `month_balance_score` fields.

3. **Interaction with overlap constraints** — weights are applied before overlap
   filtering. A very high-priority tournament that conflicts with another will simply
   lose its preferred dates to the filter; the weight won't help it. This needs to be
   explained in the user guide so operators don't expect weights to override hard
   constraints.

4. **Stale weights** — if a tournament is rescheduled manually in stage4, the weight
   has no effect and may confuse future re-runs. Stage4 should log a warning when
   manually adjusted tournaments have non-zero weights.

#### Recommended implementation steps

1. Add `preferanse_vekt: float = 0.0` to the `Tournament` dataclass.
2. Parse it from the `Turneringer`/`Aldersgrupper` sheet in `input_workbook.py`.
3. Pass the value into `_score_candidate_date` and add it to the return value.
4. Add a `Datopreferanser` sheet parser that produces a list of `(start, end, delta)`
   tuples; look up and sum any matching tuples inside `_score_candidate_date`.
5. Expose the weight components in the plan JSON and in the CLI summary table.
6. Add a magnitude cap (configurable via `Innstillinger`) with a warning when a weight
   exceeds it.


---

## Proposed changes

### High priority — bugs / silent failures (fix before next release)

1. **`state.py`: Remove redundant `mark_done`/`mark_failed` calls** from all four stage `run` functions. `write_stage(..., status=DONE)` already calls `_invalidate_downstream`; the follow-up `mark_done` call does it again. Fix in `state.py` by making `write_stage` the only place that sets final status, and remove the calls in every stage.

2. **`stage4_export.py`: Fix `scrape_age` to use `read_envelope`**, not `read_stage`. `updated_at` is an envelope field and is currently always empty. One-line fix.

3. **`stage4_helpers.py: _dict_to_plan`**: Raise on missing tournament date instead of silently defaulting to `date.today()`. Silent wrong date is worse than a clear error.

4. **`stage2_scraping.py: _scrape_source`**: Only fall through to credentialed scrape when deterministic scrape succeeded but returned 0 results — not when it raised an exception.

5. **`stage3_helpers.py: _build_events_by_club`**: Add logging when malformed events are dropped. Silent skips hide calendar conflicts.

### Medium priority — code quality

6. **Rename `_load_json` → `_load_workbook_config`** in `stage1_helpers.py`. The name is an acknowledged lie.

7. **Remove `stage2_helpers.py` re-export facade** — import directly from sub-modules.

8. **Remove dead `_tournament_from_dict`** import in `stage3_planning.py`.

9. **Move hardcoded URL substring checks** (`baerumishall.no`, `bookup.no`) from `stage2_scraping.py` dispatch block into `scraper_strategies.py`.

10. **`stage1_helpers.py: _validate_team_list`**: Add duplicate `label` detection.

### Report — layout + dynamic conclusion

11. **Move `$JUDGMENT$` up into the hero block** (or directly below it). Currently separated from the verdict by 8 sections.

12. **Collapse the advisory review section** (`review.py`) by default with a `<details>` toggle — it duplicates content already surfaced as action items.

13. **Make the conclusion dynamic**. The three static strings in `_report_overview_html` should interpolate:
    - Tournament count and month span
    - Name of the weakest score metric + its value
    - Most-travelling team and distance
    - Number of blocked sources
    - The specific fairness gate sub-metric that triggered warn/fail

14. **Add "N issues" count to the verdict pill** in the hero block.

15. **Move the heatmap** immediately after the hero block.

### Planning — subjective weight (new feature)

16. **Add `preferanse_vekt: float = 0.0`** to the `Tournament` dataclass and parse it from the Excel input sheet.

17. **Add `Datopreferanser` sheet** (`fra`, `til`, `vekt`) for global date-range penalties (e.g. Easter).

18. **Inject weight into `_score_candidate_date`** as an additive term. Positive = penalise, negative = reward.

19. **Cap weight magnitude** and expose weight components in plan JSON / CLI summary.
