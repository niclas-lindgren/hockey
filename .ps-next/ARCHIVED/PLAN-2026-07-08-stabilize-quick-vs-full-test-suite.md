# Plan: Stabilize quick vs full test suite
**Goal:** The default Pi/pytest quality path runs quick tests only while canonical full-planner and pipeline integration tests remain available behind explicit markers.
**Created:** 2026-07-08
**Intent:** Keep autonomous quality gates responsive by separating slow real-workbook planning cases from fast unit coverage.
**Backlog-ref:** 209

## Tasks
- [x] Add pytest markers and default quick-test selection
  - Files: pytest.ini, pyproject.toml
  - Approach: Define slow/integration marker descriptions and configure pytest's default addopts to exclude slow and integration tests, while preserving existing verbosity and coverage settings. Keep pyproject timeout aligned with the quick suite.
- [x] Mark canonical planner and pipeline integration tests explicitly
  - Files: tests/conftest.py, tests/test_stage3_planning.py, tests/test_season_planner.py, tests/test_rules_report_doc.py, tests/test_claude_orchestration.py
  - Approach: Add module/test-level pytest marks for canonical full-planner and subprocess pipeline integration cases; keep fixture behavior unchanged and add comments explaining how to run the excluded tests with -m slow or -m integration.
- [x] Make Pi quality gate use quick tests by default and full tests explicitly
  - Files: .pi/extensions/pi-next.ts
  - Approach: Update the Python branch of pi_next_quality_gate so quick/standard execute pytest with the default quick marker filter, and full runs the full suite with slow/integration enabled plus compileall. Ensure the command strings make the marker behavior visible.
- [x] [Fix] Fix quick-suite regressions exposed after marker split
  - Files: tournament_scheduler/pipeline/stage4_export.py, tests/test_stage4_export.py, tests/test_verdict_cli.py, tests/test_review_packets.py, .ps-next/VERIFY.md
  - Approach: Restore timestamped Stage 4 exports as the default expected by existing regression tests, update verdict CLI tests to use serialized Stage 3 checkpoint data instead of raw SeasonPlan objects, and rerun the quick pytest command until it passes or only intentional slow/integration tests are deselected.

## Notes
Backlog item 209 targets test-suite stability, not scheduling behavior, so no RVV rules-report documentation update is needed. Existing canonical helpers load input.xlsx and may reuse .pipeline/stage3_planning.json, so they should be treated as slow planner coverage rather than default quick unit tests.

## Acceptance Criteria
- [ ] pytest.ini contains registered slow and integration markers and default addopts exclude them.
- [ ] Canonical full-planner tests in tests/test_stage3_planning.py, tests/test_season_planner.py, and tests/test_rules_report_doc.py are marked slow.
- [ ] Pipeline subprocess integration tests in tests/test_claude_orchestration.py are marked integration.
- [ ] .pi/extensions/pi-next.ts runs quick/standard Python quality gates without slow/integration tests and full quality gates with the full pytest suite.
- [ ] run: python3 -m pytest -q tests/test_stage3_planning.py tests/test_season_planner.py tests/test_rules_report_doc.py -m "not slow and not integration" --no-cov
- [ ] run: python3 -m pytest -q tests/test_pi_next_skill_boundary.py --no-cov

## Log




### 2026-07-08 — [Fix] Fix quick-suite regressions exposed after marker split
**Done:** Restored timestamped Stage 4 exports as the run() default, updated verdict CLI tests to use serialized Stage 3 checkpoint payloads and expect SystemExit on invalid checkpoints, and made the review-packet test opt into flat export output when it depends on that layout.
**Rationale:** After the slow/integration marker split, the default quick suite should pass rather than merely avoid canonical planner hangs.
**Findings:** Manual quick suite now passes: 703 passed, 1 skipped, 19 deselected in 44.20s with slow/integration excluded.
**Files:** tournament_scheduler/pipeline/stage4_export.py, tests/test_verdict_cli.py, tests/test_review_packets.py, .ps-next/VERIFY.md
**Commit:** not committed
### 2026-07-08 — Make Pi quality gate use quick tests by default and full tests explicitly
**Done:** Updated the Python pi_next_quality_gate command selection so quick/standard use the quick marker expression and full disables default addopts before running an all-tests marker expression plus compileall.
**Rationale:** The default Pi quality path should be bounded by quick tests; full validation must opt into slow/integration coverage explicitly.
**Findings:** The in-memory Pi tool still used the pre-edit command during this session, so I verified the updated extension source with a static assertion. A broader manual quick-suite run exposed unrelated existing failures in Stage 4 export and verdict CLI tests that need follow-up.
**Files:** .pi/extensions/pi-next.ts
**Commit:** not committed
### 2026-07-08 — Mark canonical planner and pipeline integration tests explicitly
**Done:** Marked canonical real-workbook/full-planner coverage as slow, marked Claude subprocess stage orchestration tests as integration, and documented explicit marker commands near the fixtures/modules.
**Rationale:** Slow canonical and pipeline tests remain available on demand while being excluded from the quick default test path.
**Findings:** A Stage 3 progress-output regression assertion was stale for the current message wording; updated it to assert the current optimization/fairness progress signals so the quick Stage 3 tests pass.
**Files:** tests/conftest.py, tests/test_stage3_planning.py, tests/test_season_planner.py, tests/test_rules_report_doc.py, tests/test_claude_orchestration.py
**Commit:** not committed
### 2026-07-08 — Add pytest markers and default quick-test selection
**Done:** Registered slow/integration pytest markers and made the default pytest addopts select only quick tests while preserving coverage settings; mirrored the settings in pyproject for tooling visibility.
**Rationale:** The quick suite should be the default path for local and Pi quality gates, with slow/full coverage opt-in by marker override.
**Findings:** pytest reports pytest.ini as authoritative and ignores pyproject pytest settings because both files exist; pyproject still documents the intended mirrored settings.
**Files:** pytest.ini, pyproject.toml
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
