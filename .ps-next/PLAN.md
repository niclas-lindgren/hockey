# PLAN

**Feature:** Improve light theme UI colors — heatmap background is too dark and there's too little differentiation between colors (all bright, hard to distinguish)
**Goal:** Improve light theme UI colors — heatmap background is too dark and there's too little differentiation between colors (all bright, hard to distinguish)
**Backlog-ref:** 53
**Constraints:** none
**Date:** 2026-06-11

## Intent

The season-plan HTML report's light theme currently reuses dark-theme-only color choices for the heatmap (a hardcoded dark club-color palette and a near-black empty-cell background), making the heatmap look too dark and the club colors too similar/low-contrast against the light background — this plan introduces a dedicated, well-differentiated light-theme color set for the heatmap and related UI elements.

## Tasks

- [x] Added a separate _club_colors_light pastel palette (9 hues: blue, green, amber, purple, rose, cyan, yellow, lime, orange) with darker high-contrast text alongside the renamed _club_colors_dark, serialized both as a nested {dark, light} map via HEATMAP_CLUB_COLORS_JSON, and updated script.js to pick the palette based on document.documentElement.dataset.theme (with theme-aware fallback colors and earlier theme restoration so it applies on first paint). — 2026-06-11
  - Files: `tournament_scheduler/html/html_exporter.py`
  - Acceptance: A new `_club_colors_light` list of 9 `{"bg": ..., "text": ...}` pairs is added alongside the existing `_club_colors` (renamed/commented as the dark-theme palette), using light, distinctly-hued backgrounds (e.g. pastel tints of blue, green, amber, purple, rose, cyan, yellow, lime, orange) with darker, high-contrast text colors suitable for a `--bg: #f4f4f5` page background. Both palettes are serialized to JSON (`heatmap_club_colors_dark_json` / `heatmap_club_colors_light_json`, or a single nested `{dark: {...}, light: {...}}` map) and injected into the template via existing placeholder mechanism (`$HEATMAP_CLUB_COLORS_JSON$` or a new placeholder).

- [x] Already implemented as part of the previous task: HEATMAP_CLUB_COLORS_BY_THEME holds {dark, light} maps, and the renderHeatmap IIFE derives currentTheme from document.documentElement.dataset.theme (defaulting to 'dark'), then uses HEATMAP_CLUB_COLORS_BY_THEME[currentTheme] for both the legend and table cell rendering. — 2026-06-11
  - Files: `tournament_scheduler/html/templates/script.js`, `tournament_scheduler/html/html_exporter.py`
  - Acceptance: `script.js` defines `HEATMAP_CLUB_COLORS` as an object keyed by theme (`{dark: {...}, light: {...}}`) populated from the new placeholder(s). The `renderHeatmap` IIFE (around line 137-200) reads `document.documentElement.dataset.theme` (defaulting to `'dark'`) and selects `HEATMAP_CLUB_COLORS[currentTheme]` when building the legend (line ~149-155) and table cells (line ~180-189), so club colors differ between dark and light themes.

- [x] Replaced the hardcoded empty-cell background rgba(30,41,59,.4) in the heatmap renderer with var(--heatmap-empty-bg), so the value can be themed via CSS in :root and [data-theme"light"]. — 2026-06-11
  - Files: `tournament_scheduler/html/templates/script.js`
  - Acceptance: The hardcoded `background:rgba(30,41,59,.4)` for empty cells (line ~191) is replaced with a CSS variable reference (e.g. `var(--bg-surface)` or a new `--heatmap-empty-bg` variable) so empty cells render as a subtle light-grey in light theme and the existing dark slate in dark theme — no literal dark rgba value remains in the empty-cell branch.

- [ ] Add a `--heatmap-empty-bg` CSS variable for both themes
  - Files: `tournament_scheduler/html/templates/styles.css`
  - Acceptance: `:root` defines `--heatmap-empty-bg: rgba(30,41,59,.4)` (preserving current dark-theme appearance) and `[data-theme="light"]` overrides it with a light, low-contrast neutral (e.g. `rgba(228,228,231,.6)` or similar derived from `--bg-surface`), referenced by `script.js` from the previous task.

- [ ] Update light-theme accent and tag color values for better differentiation
  - Files: `tournament_scheduler/html/templates/styles.css`
  - Acceptance: In `[data-theme="light"]` (lines 24-41), `--accent-dim` is corrected so it is darker than `--accent` (matching the dark theme's relationship, e.g. swap to a deeper blue such as `#0369a1`) to fix the inverted gradient on `.logo-icon` and `.timeline::before`. The `.tag--age`, `.tag--arena`, `.tag--teams`, `.tag--travel` background opacities (currently `rgba(...,.08)`) are increased (e.g. to `.14`-`.18`) within `[data-theme="light"]` via theme-scoped overrides so tags remain visually distinct against `--bg: #f4f4f5` without affecting dark theme.

- [ ] Verify generated HTML reports render correctly with both palettes
  - Files: `tournament_scheduler/html/html_exporter.py`, `tests/` (existing test for html_exporter, if present)
  - Acceptance: Run the project's HTML export (or its existing pytest coverage for `html_exporter.py`) and confirm the generated `season_plan.html` contains both `dark` and `light` keys in the serialized `HEATMAP_CLUB_COLORS` JSON, that `script.js` has no remaining literal `rgba(30,41,59,.4)` outside of the `:root` CSS variable definition, and that `python3 -m py_compile tournament_scheduler/html/html_exporter.py` and `node --check tournament_scheduler/html/templates/script.js` (if `node` is available) both succeed.

## Acceptance Criteria

Generated `season_plan.html` and `script.js` contain a `HEATMAP_CLUB_COLORS` object with separate `dark` and `light` color sets, and `script.js` selects the set matching `document.documentElement.dataset.theme` when rendering heatmap cells.
The `[data-theme="light"]` block in `tournament_scheduler/html/templates/styles.css` defines a `--heatmap-empty-bg` variable whose value is not a near-black rgba, and `script.js` no longer outputs the literal `rgba(30,41,59,.4)` in the empty-heatmap-cell branch.
The `[data-theme="light"]` block has `--accent-dim` darker than `--accent` (matching the dark theme's relative ordering), so the logo and timeline gradients are not inverted in light mode.
`.tag--age`, `.tag--arena`, `.tag--teams`, and `.tag--travel` have light-theme-specific background opacity overrides that are visibly higher than the dark-theme `.08` value, producing better contrast against `--bg: #f4f4f5`.
Running `python3 -m py_compile tournament_scheduler/html/html_exporter.py` exits with code 0 and the existing pytest suite (`pytest`) passes with no new failures introduced by these changes.

## Log

- [2026-06-11] Plan created for backlog item 53 (light theme heatmap colors).

### 2026-06-11 — Added a separate _club_colors_light pastel palette (9 hues: blue, green, amber, purple, rose, cyan, yellow, lime, orange) with darker high-contrast text alongside the renamed _club_colors_dark, serialized both as a nested {dark, light} map via HEATMAP_CLUB_COLORS_JSON, and updated script.js to pick the palette based on document.documentElement.dataset.theme (with theme-aware fallback colors and earlier theme restoration so it applies on first paint).
**Rationale:** Used a single nested {dark, light} JSON map (per the plan's alternative) rather than two separate placeholders, since it required only one template substitution and let the JS pick the active palette client-side based on the existing theme attribute.
**Findings:** Both palettes are generated for all heatmap_clubs; JS selects HEATMAP_CLUB_COLORS_BY_THEME[currentTheme]. Moved theme restoration from localStorage to the top of script.js so the heatmap renders with the correct palette on first paint instead of always defaulting to dark.
LESSONS: none
**Files:** tournament_scheduler/html/html_exporter.py (+28/-4), tournament_scheduler/html/templates/script.js (+25/-7)
**Commit:** 2877215 (hockey)

### 2026-06-11 — Already implemented as part of the previous task: HEATMAP_CLUB_COLORS_BY_THEME holds {dark, light} maps, and the renderHeatmap IIFE derives currentTheme from document.documentElement.dataset.theme (defaulting to 'dark'), then uses HEATMAP_CLUB_COLORS_BY_THEME[currentTheme] for both the legend and table cell rendering.
**Rationale:** No code changes needed — verified the prior commit (2877215) already satisfies this task's acceptance criteria exactly (variable name HEATMAP_CLUB_COLORS, theme detection with dark default, used in both legend ~line 165 and body ~line 196).
**Findings:** Confirmed script.js lines 1-20 and 144-205 already match the acceptance criteria; no further edits required.
LESSONS: none
**Files:** none
**Commit:** 0fc46e4 (hockey)

### 2026-06-11 — Replaced the hardcoded empty-cell background rgba(30,41,59,.4) in the heatmap renderer with var(--heatmap-empty-bg), so the value can be themed via CSS in :root and [data-theme"light"].
**Rationale:** Simple substitution; the corresponding CSS variable definition is added in the next task.
**Findings:** No literal dark rgba value remains in the empty-cell branch of script.js; depends on the next task to define --heatmap-empty-bg or the cell will render with no background until then.
LESSONS: none
**Files:** tournament_scheduler/html/templates/script.js (+1/-1)
**Commit:** [pending — fill after commit]
