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

- [x] Defined --heatmap-empty-bg in :root as rgba(30,41,59,.4) (preserving the prior dark-theme empty-cell appearance) and overrode it in [data-theme"light"] with rgba(228,228,231,.6), a light low-contrast neutral derived from --bg-surface (#e4e4e7). — 2026-06-11
  - Files: `tournament_scheduler/html/templates/styles.css`
  - Acceptance: `:root` defines `--heatmap-empty-bg: rgba(30,41,59,.4)` (preserving current dark-theme appearance) and `[data-theme="light"]` overrides it with a light, low-contrast neutral (e.g. `rgba(228,228,231,.6)` or similar derived from `--bg-surface`), referenced by `script.js` from the previous task.

- [x] Changed [data-theme"light"] --accent-dim from #38bdf8 (lighter than --accent) to #0369a1 (darker than --accent #0284c7), matching the dark theme's accent/accent-dim relationship and fixing the inverted gradient on .logo-icon and .timeline::before. Added theme-scoped overrides for .tag--age, .tag--arena, .tag--teams, .tag--travel raising background opacity from .08 to .16 and border opacity from .15 to .3 in light theme only. — 2026-06-11
  - Files: `tournament_scheduler/html/templates/styles.css`
  - Acceptance: In `[data-theme="light"]` (lines 24-41), `--accent-dim` is corrected so it is darker than `--accent` (matching the dark theme's relationship, e.g. swap to a deeper blue such as `#0369a1`) to fix the inverted gradient on `.logo-icon` and `.timeline::before`. The `.tag--age`, `.tag--arena`, `.tag--teams`, `.tag--travel` background opacities (currently `rgba(...,.08)`) are increased (e.g. to `.14`-`.18`) within `[data-theme="light"]` via theme-scoped overrides so tags remain visually distinct against `--bg: #f4f4f5` without affecting dark theme.

- [x] Wrote a temporary standalone script that builds a minimal SeasonPlan with two host clubs and calls HtmlExporter().export() to a temp file, then asserted the rendered HTML's HEATMAP_CLUB_COLORS_BY_THEME JSON contains both 'dark' and 'light' keys with bg/text entries for each club, and that no literal 'rgba(30,41,59,.4)' remains while '--heatmap-empty-bg' is present in the output. — 2026-06-11
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
**Commit:** 2501b58 (hockey)

### 2026-06-11 — Defined --heatmap-empty-bg in :root as rgba(30,41,59,.4) (preserving the prior dark-theme empty-cell appearance) and overrode it in [data-theme"light"] with rgba(228,228,231,.6), a light low-contrast neutral derived from --bg-surface (#e4e4e7).
**Rationale:** Chose rgba over a flat color to keep partial transparency consistent with the original dark-theme value and allow the underlying --bg to show through subtly in both themes.
**Findings:** Variable now consumed by script.js (added in the previous task) for empty heatmap cells; dark theme appearance unchanged, light theme empty cells render as a subtle light-grey.
LESSONS: none
**Files:** tournament_scheduler/html/templates/styles.css (+2/-0)
**Commit:** fc7039e (hockey)

### 2026-06-11 — Changed [data-theme"light"] --accent-dim from #38bdf8 (lighter than --accent) to #0369a1 (darker than --accent #0284c7), matching the dark theme's accent/accent-dim relationship and fixing the inverted gradient on .logo-icon and .timeline::before. Added theme-scoped overrides for .tag--age, .tag--arena, .tag--teams, .tag--travel raising background opacity from .08 to .16 and border opacity from .15 to .3 in light theme only.
**Rationale:** Used attribute-selector overrides ([data-theme"light"] .tag--X) rather than duplicating the full rule, keeping dark-theme rules untouched and minimizing diff.
**Findings:** Light theme tags now have visible background tint and border against --bg: #f4f4f5; dark theme rules and values are unaffected.
LESSONS: none
**Files:** tournament_scheduler/html/templates/styles.css (+5/-1)
**Commit:** 728039f (hockey)

### 2026-06-11 — Wrote a temporary standalone script that builds a minimal SeasonPlan with two host clubs and calls HtmlExporter().export() to a temp file, then asserted the rendered HTML's HEATMAP_CLUB_COLORS_BY_THEME JSON contains both 'dark' and 'light' keys with bg/text entries for each club, and that no literal 'rgba(30,41,59,.4)' remains while '--heatmap-empty-bg' is present in the output.
**Rationale:** Used a throwaway script + temp dir rather than the full pipeline to avoid touching tracked export/ artifacts; deleted the script after verification since it was only for this check.
**Findings:** All assertions passed: dark/light keys present with correct club colors (e.g. Kongsberg dark #1a3a5c/#64b5f6, light #dbeafe/#1d4ed8); python3 -m py_compile and node --check both succeed; full html/export/heatmap pytest subset (20 tests) passes.
LESSONS: none
**Files:** none (verification only, no source changes)
**Commit:** [pending — fill after commit]
