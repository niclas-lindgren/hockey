# Plan: Blocked-source recovery UX
**Goal:** Blocked BookUp and other authenticated sources show actionable recovery instructions, support an explicit allow-missing-sources mode, and preserve partial scrape results for reruns.
**Created:** 2026-06-12
**Intent:** Reduce operator friction when a source is blocked by making the next step obvious in Norwegian and keeping useful partial data available.
**Backlog-ref:** 63

## Tasks
- [x] Add explicit allow-missing-sources handling and clearer recovery hints
  - Files: tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/cli/rvv_cli.py
  - Approach: Add an allow-missing-sources mode that keeps partial scraping results as a successful checkpoint, and print Norwegian recovery instructions with exact credential/env-var guidance plus rerun/skip instructions in the run and scrape flows.
- [x] Add regression coverage for blocked-source recovery messaging
  - Files: tests/test_stage2_scraping.py
  - Approach: Cover a BookUp source that blocks with missing credentials, asserting the recovery hint mentions the required env vars and that allow-missing-sources preserves partial results without raising.

## Notes
Stage 2 already persists partial blocked-source results. The new work should improve operator guidance and expose an explicit skip mode rather than changing the scraper discovery logic.

## Acceptance Criteria
- [ ] run: pytest tests/test_stage2_scraping.py
- [ ] run: pytest
- [ ] grep: tournament_scheduler/pipeline/stage2_scraping.py contains allow_missing_sources
- [ ] grep: tournament_scheduler/cli/rvv_cli.py contains --allow-missing-sources
- [ ] run: python3 - <<'PY'
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from tournament_scheduler.pipeline.stage2_scraping import SOURCE_OUTLOOK, run
from tournament_scheduler.pipeline.state import PipelineState, StageName

work = Path('.tmp-pi-next-recovery-hint')
if work.exists():
    import shutil
    shutil.rmtree(work)
state = PipelineState(work / 'pipeline')
cfg = {
    'start_date': '2025-09-01',
    'end_date': '2025-12-01',
    'teams': [],
    'sources': [{
        'name': 'Sandefjord Penguins',
        'type': SOURCE_OUTLOOK,
        'url': 'https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen___/view:item/id:4497/part:/place:3907:SANDEFJORD/q:sandefjord/r:31/mod:book',
    }],
}
with patch('tournament_scheduler.pipeline.stage2_scraping._run_bookup_scraper', return_value=([], '')):
    result = run(cfg, state, datetime(2025, 9, 1), datetime(2025, 12, 1), strict=True, allow_missing_sources=True)
assert state.is_done(StageName.SCRAPING)
assert 'BOOKUP_EMAIL' in result['sources'][0]['recovery_hint']
assert '--allow-missing-sources' in result['warning']
print('ok')
PY
- [ ] run: python3 - <<'PY'
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from tournament_scheduler.pipeline.stage2_scraping import SOURCE_OUTLOOK, run
from tournament_scheduler.pipeline.state import PipelineState, StageName

work = Path('.tmp-pi-next-recovery-hint')
if work.exists():
    import shutil
    shutil.rmtree(work)
state = PipelineState(work / 'pipeline')
cfg = {
    'start_date': '2025-09-01',
    'end_date': '2025-12-01',
    'teams': [],
    'sources': [{
        'name': 'Sandefjord Penguins',
        'type': SOURCE_OUTLOOK,
        'url': 'https://www.bookup.no/Utleie/#Bug%C3%A5rdshallen___/view:item/id:4497/part:/place:3907:SANDEFJORD/q:sandefjord/r:31/mod:book',
    }],
}
with patch('tournament_scheduler.pipeline.stage2_scraping._run_bookup_scraper', return_value=([], '')):
    result = run(cfg, state, datetime(2025, 9, 1), datetime(2025, 12, 1), strict=True, allow_missing_sources=True)
assert state.is_done(StageName.SCRAPING)
assert 'BOOKUP_EMAIL' in result['sources'][0]['recovery_hint']
assert '--allow-missing-sources' in result['warning']
print('ok')
PY

## Log


### 2026-06-12 — Add regression coverage for blocked-source recovery messaging
**Done:** Added stage2 regression coverage for a BookUp source with missing credentials, verifying the recovery hint names the required env vars and that allow-missing-sources preserves partial results without raising.
**Rationale:** The recovery UX needs a deterministic regression so the explicit skip mode and guidance stay intact.
**Findings:** tests/test_stage2_scraping.py now covers both the blocked-source message path and the allow-missing-sources success path.
**Files:** tests/test_stage2_scraping.py
**Commit:** not committed
### 2026-06-12 — Add explicit allow-missing-sources handling and clearer recovery hints
**Done:** Added an explicit allow-missing-sources mode to Stage 2 and the RVV CLI run/scrape flows, and now print Norwegian recovery hints with exact credential env vars plus rerun/skip guidance when a source blocks.
**Rationale:** Operators need a clear opt-in skip mode and a concrete next step when BookUp or other authenticated sources block, without losing partial scrape output.
**Findings:** Full pytest passed after the changes (345 passed, 1 skipped).
**Files:** tournament_scheduler/pipeline/stage2_scraping.py, tournament_scheduler/cli/rvv_cli.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
