# Plan: Issue 41 iframe auto-sizing and year-wheel cleanup verification
**Goal:** Complete GitHub issue #41 by keeping the decorative Årshjul removed and adding robust, documented, schema-versioned iframe height messaging for the activity embed.
**Created:** 2026-07-29
**Intent:** The live WordPress embed should not keep nested scrollbars or oversized fixed empty space, and the secondary year-wheel should not return unless it encodes meaningful data.

## Tasks
- [x] Harden child iframe height messaging
  - Files: tournament_scheduler/pipeline/activity_viewer.py, tests/test_activity_viewer.py
  - Approach: Replace simple wildcard height postMessage with a namespaced/versioned message, known-origin target selection when embedded under GitHub Pages, clamped measured height, requestAnimationFrame debounce, ResizeObserver support with resize/orientation fallback, and calls after load/filter/view/details changes while preserving standalone behavior.
- [x] Document secure parent integration and wheel decision
  - Files: docs/rvv-miniputt-pipeline.md, tests/test_activity_viewer.py
  - Approach: Update the WordPress embed section with the schema-versioned child message contract, secure origin/namespace validation, per-iframe id matching, bounded height updates, no large permanent blank area, and explicitly state that Årshjul is removed rather than retained as a secondary view.
- [x] Verify issue 41 acceptance coverage
  - Files: .ps-next/VERIFY.md, tests/test_activity_viewer.py
  - Approach: Run focused activity viewer/export tests plus relevant grep/smoke checks for no Årshjul/yearWheel/wheelView, iframe message schema, ResizeObserver/debounce, details focus behavior, and docs snippets.

## Notes
- Source: GitHub issue #41, https://github.com/niclas-lindgren/hockey/issues/41
- GitHub issue #40 already removed the old decorative Årshjul view; this plan keeps that decision and does not reintroduce a wheel.
- Preserve relative assets for local timestamped exports and `latest/activities/`.
- Do not use `*` as postMessage target origin when the page can identify a specific parent origin.
- The unrelated untracked workbook `Årshjul for aktiviteter.xlsx` existed before this plan and must remain untouched.

## Acceptance Criteria
- [ ] `pytest tests/test_activity_viewer.py tests/test_activity_export.py` passes.
- [ ] Generated activity HTML contains no `yearWheel`, `wheelView`, or `Årshjul` view code.
- [ ] Generated activity HTML sends schema-versioned, namespaced height messages and avoids wildcard target origin when a known parent origin is available.
- [ ] Generated activity HTML uses ResizeObserver or a safe fallback, debounce/coalescing, and height clamping for resize updates.
- [ ] Details remain closed by default, open in an overlay/dialog, and restore focus on close without adding a permanent details column.
- [ ] Mobile defaults to the readable list view and does not expose a wheel selector.
- [ ] `docs/rvv-miniputt-pipeline.md` documents the Årshjul removal decision and copy/paste-ready secure WordPress parent listener with origin, namespace/schema, iframe-id, and height bounds validation.

## Log



### 2026-07-29 — Verify issue 41 acceptance coverage
**Done:** Ran focused tests and smoke/grep checks covering removed year-wheel code, schema-versioned iframe messaging, ResizeObserver/debounce/clamping, overlay focus behavior, and documentation snippets.
**Rationale:** This task verifies issue #41 acceptance now that implementation and docs were completed in prior tasks.
**Findings:** `pytest tests/test_activity_viewer.py tests/test_activity_export.py` → 25 passed. Smoke check confirmed no `yearWheel`/`wheelView`/`Årshjul` view code and required iframe/focus features are present.
**Files:** .ps-next/PLAN.md (task log only)
**Commit:** not committed
### 2026-07-29 — Document secure parent integration and wheel decision
**Done:** Updated the WordPress embed docs with the removed-Årshjul decision, schema-versioned child height message shape, lower initial iframe height, secure parent listener validating origin/namespace/schema/iframe id/event source/height bounds, and multi-iframe-safe behavior.
**Rationale:** Issue #41 allows removing the decorative wheel and requires robust automatic iframe sizing with a secure copy/paste parent integration.
**Findings:** `pytest tests/test_activity_viewer.py` passes (12 tests).
**Files:** docs/rvv-miniputt-pipeline.md, tests/test_activity_viewer.py
**Commit:** not committed
### 2026-07-29 — Harden child iframe height messaging
**Done:** Replaced the simple wildcard height postMessage with schema-versioned `rvv.activities` messages carrying iframe id, reason, source path, and clamped height. Added parent-origin targeting, RAF debounce with timeout fallback, duplicate-height suppression, ResizeObserver/font-ready observation, orientation handling, and updated viewer tests.
**Rationale:** The WordPress iframe needs content-driven sizing without nested scrollbars, resize feedback loops, or insecure wildcard messaging when a known parent origin is available.
**Findings:** Focused non-doc viewer tests pass: `pytest tests/test_activity_viewer.py -k 'not wordpress'` → 11 passed.
**Files:** tournament_scheduler/pipeline/activity_viewer.py, tests/test_activity_viewer.py
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
