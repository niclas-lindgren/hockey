# Plan: Fix double _invalidate_downstream calls in all pipeline stages

**Feature:** Fix double _invalidate_downstream calls in all pipeline stages: write_stage(status=DONE/FAILED) and mark_done/mark_failed both call _invalidate_downstream — remove the redundant mark_done/mark_failed calls from stage1–4 run functions and make write_stage the single place that sets final status.
**Goal:** write_stage is the single place that sets final status (DONE/FAILED) and triggers _invalidate_downstream; redundant mark_done/mark_failed calls after write_stage are removed; standalone mark_failed calls replaced by write_stage.
**Backlog-ref:** 125
**Constraints:** none
**Date:** 2026-06-19
**Intent:** Eliminate a double-invalidation bug where both write_stage and mark_done/mark_failed each call _invalidate_downstream, causing downstream stages to be invalidated twice per final status transition.

## Tasks

- [x] Removed the redundant mark_done(CONFIG) call on line 169 of stage1_config.py that immediately followed write_stage(CONFIG, config, statusDONE). The write_stage call already sets the final status, making mark_done unnecessary. — 2026-06-19
  - Files: `tournament_scheduler/pipeline/stage1_config.py`
  - Approach: Remove the mark_done(CONFIG) call on line 169 that immediately follows write_stage(CONFIG, config, status=DONE) on line 168; write_stage already calls _invalidate_downstream so the mark_done call is fully redundant.

- [ ] Remove redundant mark_done/mark_failed calls after write_stage in stage2_scraping.py
  - Files: `tournament_scheduler/pipeline/stage2_scraping.py`
  - Approach: Remove three redundant calls — mark_failed(SCRAPING) after write_stage(FAILED) at line 132, mark_done(SCRAPING) after write_stage(DONE) at line 142, and mark_done(SCRAPING) after write_stage(checkpoint, status=status) at line 244; all three follow an immediately preceding write_stage call that already handles status and invalidation.

- [ ] Replace standalone mark_failed with write_stage in stage3_planning.py
  - Files: `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: At line 112, the standalone mark_failed(PLANNING, error=reason) is not preceded by a write_stage(FAILED) call; replace it with write_stage(StageName.PLANNING, {}, status=StageStatus.FAILED) so that status is set and _invalidate_downstream is triggered consistently through write_stage.

- [ ] Remove redundant mark_done call after write_stage in stage3_planning.py
  - Files: `tournament_scheduler/pipeline/stage3_planning.py`
  - Approach: Remove the mark_done(PLANNING) call on line 128 that immediately follows write_stage(PLANNING, checkpoint, status=DONE) on line 127; write_stage already handles the final status transition.

- [ ] Replace standalone mark_failed with write_stage in stage4_export.py
  - Files: `tournament_scheduler/pipeline/stage4_export.py`
  - Approach: At line 91, the standalone mark_failed(EXPORT, error=reason) is not preceded by a write_stage(FAILED) call; replace it with write_stage(StageName.EXPORT, {}, status=StageStatus.FAILED) to route the failure through the single canonical status-setting path.

- [ ] Remove redundant mark_done/mark_failed calls after write_stage in stage4_export.py
  - Files: `tournament_scheduler/pipeline/stage4_export.py`
  - Approach: Remove mark_failed(EXPORT) on line 256 (follows write_stage(FAILED) on line 255) and mark_done(EXPORT) on line 262 (follows write_stage(checkpoint, status=status) on line 260); both are redundant given the preceding write_stage calls.

- [ ] Verify no remaining bare mark_done/mark_failed calls exist in run functions and tests pass
  - Files: `tournament_scheduler/pipeline/stage1_config.py`, `tournament_scheduler/pipeline/stage2_scraping.py`, `tournament_scheduler/pipeline/stage3_planning.py`, `tournament_scheduler/pipeline/stage4_export.py`, `tests/`
  - Approach: Run `grep -n "mark_done\|mark_failed" stage1_config.py stage2_scraping.py stage3_planning.py stage4_export.py` to confirm no redundant calls remain, then run `pytest` to verify no regressions.

## Log

- 2026-06-19 Plan created

## Acceptance Criteria

When the pipeline completes successfully, only one _invalidate_downstream call is made per stage and no redundant mark_done or mark_failed calls are executed after write_stage has been called.
When a pipeline stage fails, the write_stage method is the only location that sets the final status and calls _invalidate_downstream, eliminating any duplicate status updates.
All standalone mark_failed calls are replaced by write_stage which properly handles final status setting and downstream invalidation.
The pipeline produces consistent output when stages complete, with no duplicate invalidation events in the execution trace.
Pipeline tests pass with no regressions after redundant mark_done and mark_failed calls are removed.

### 2026-06-19 — Removed the redundant mark_done(CONFIG) call on line 169 of stage1_config.py that immediately followed write_stage(CONFIG, config, statusDONE). The write_stage call already sets the final status, making mark_done unnecessary.
**Rationale:** Straightforward single-line removal with no alternatives needed.
**Findings:** Removed mark_done call; write_stage is now the sole place setting final status in stage1_config.py.
LESSONS: none
**Files:** tournament_scheduler/pipeline/stage1_config.py (+0/-1)
**Commit:** [pending — fill after commit]
