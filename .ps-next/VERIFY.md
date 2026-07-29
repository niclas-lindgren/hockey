# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `pytest tests/test_activity_viewer.py tests/test_activity_export.py` passes. | PASS | Command passed: 25 tests passed. |
| Generated activity HTML contains no `yearWheel`, `wheelView`, or `Årshjul` view code. | PASS | Smoke check of generated HTML returned `no_yearWheel`, `no_wheelView`, and `no_Aarshjul_control` all true. |
| Generated activity HTML sends schema-versioned, namespaced height messages and avoids wildcard target origin when a known parent origin is available. | PASS | Viewer tests assert `HEIGHT_MESSAGE_NAMESPACE = 'rvv.activities'`, `HEIGHT_MESSAGE_SCHEMA_VERSION = 1`, `iframe_id: iframeId()`, `parentTargetOrigin()`, and absence of the old wildcard `postMessage(..., '*')` implementation. |
| Generated activity HTML uses ResizeObserver or a safe fallback, debounce/coalescing, and height clamping for resize updates. | PASS | Viewer tests assert `ResizeObserver`, fallback interval, `cancelAnimationFrame(heightRaf)`, `setTimeout(() => postHeight(...), 180)`, duplicate-height suppression, and 320/6000 clamp constants. |
| Details remain closed by default, open in an overlay/dialog, and restore focus on close without adding a permanent details column. | PASS | Viewer tests assert `<dialog id="detailsDialog">`, `showModal`, close handling, `detailsClose.focus`, and `lastActivator.focus`; the HTML contains no permanent details pane layout. |
| Mobile defaults to the readable list view and does not expose a wheel selector. | PASS | Viewer tests assert mobile `matchMedia('(max-width: 760px)')`, `mobile-default`, `view-list`, and that `renderWheel`/`wheelView` are absent. |
| `docs/rvv-miniputt-pipeline.md` documents the Årshjul removal decision and copy/paste-ready secure WordPress parent listener with origin, namespace/schema, iframe-id, and height bounds validation. | PASS | `rg` found the removal decision, `namespace: 'rvv.activities'`, `schema_version: 1`, iframe id validation, `frame.contentWindow !== event.source`, `MAX_HEIGHT = 6000`, and `rvv-activities-frame`. |

Additional gate: `pi_next_quality_gate(level="standard")` passed with `python3 -m pytest -q -m "not slow and not integration"` → 1173 passed, 1 skipped, 26 deselected.
