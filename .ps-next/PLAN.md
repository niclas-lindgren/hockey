# Plan: Light/bright theme toggle for HTML season-plan reports
**Goal:** Add a light/bright theme option to the HTML season-plan reports (calendars.html / season_plan.html) — currently only the dark/professional palette from backlog item #43 is available. Add a toggle (or alternate stylesheet) so organizers can switch between dark and light themes.
**Created:** 2026-06-10
**Intent:** Some organizers print or read these reports in bright environments where the dark palette from #43 is hard to read, so let them switch to a light theme without regenerating the report.
**Backlog-ref:** 50

## Tasks
- [x] Added a [data-theme"light"] override block in styles.css providing light, high-contrast equivalents for all 15 themeable color variables (--bg through --violet), leaving --radius* and --font* untouched. — 2026-06-10
  - Files: tournament_scheduler/html/templates/styles.css
  - Approach: Keep the existing `:root { ... }` block as the dark theme (default), and add a `[data-theme="light"]` (or `.theme-light`) selector that overrides every color variable currently defined in `:root` (`--bg`, `--bg-raised`, `--bg-surface`, `--border`, `--border-dim`, `--text`, `--text-secondary`, `--text-muted`, `--accent`, `--accent-dim`, `--accent-glow`, `--amber`, `--emerald`, `--rose`, `--violet`) with light, high-contrast equivalents; leave `--radius*` and `--font*` untouched since they are theme-independent.

- [x] Added a #themeToggle icon button with sun/moon inline-SVG icons near the .header-right stat badges in header.html, following the existing .stat-badge markup conventions. — 2026-06-10
  - Files: tournament_scheduler/html/templates/header.html
  - Approach: Add a small icon button (e.g. `<button id="themeToggle" class="theme-toggle" aria-label="Bytt tema" title="Bytt tema">`) near the existing `.header-right` stat badges, using the same inline-SVG icon style as the other badges (sun/moon icon), following the markup conventions already used for `.stat-badge` elements.

- [x] Added an IIFE near the end of script.js that reads the saved theme from localStorage (key rvv-theme), applies it via document.documentElement.dataset.theme, and wires a click handler on #themeToggle to flip the theme and persist the new value. — 2026-06-10
  - Files: tournament_scheduler/html/templates/script.js
  - Approach: In the existing DOMContentLoaded init function (~line 150), read a saved theme preference from `localStorage` (e.g. key `rvv-theme`) and apply it by setting `document.documentElement.dataset.theme` (or toggling a `theme-light` class on `<html>`/`<body>`) before first paint where possible; wire a click handler on `#themeToggle` that flips the theme, updates the `localStorage` value, and updates the toggle icon/aria-state, following the same event-handler registration style already used in script.js.

- [x] Added .theme-toggle button styles consistent with .stat-badge/.navbar a (same padding/radius/hover transitions using CSS vars), added a --hover-overlay variable (light overlay in dark theme, dark overlay in light theme) and replaced the hardcoded rgba(255,255,255,0.06) hover background in .navbar a:hover with it, and added CSS rules to swap the sun/moon icon visibility based on [data-themelight]. — 2026-06-10
  - Files: tournament_scheduler/html/templates/styles.css
  - Approach: Add `.theme-toggle` styles consistent with `.stat-badge`/`.navbar a` (same padding, radius, hover transition using CSS vars), and review/adjust any hardcoded colors in styles.css (e.g. `rgba(255,255,255,0.06)` hover states, `color: #fff` on `.logo-icon`) so they remain legible against the light palette — replace with CSS-variable-driven values or add light-theme-specific overrides where a hardcoded value would break contrast.

- [x] Mirrored the [data-themelight] variable overrides and --hover-overlay variable from styles.css into the inline <style> block, added the #themeToggle button with sun/moon icons to the navbar markup, added .theme-toggle styles, fixed the hardcoded rgba(255,255,255,0.06) navbar hover, and ported the localStorage-based toggle logic (rvv-theme key) into the inline <script> block. — 2026-06-10
  - Files: tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: calendars.html has its own inline `<style>` block (~lines 291-312, duplicating the dark `:root` variables) and inline `<script>` block (~lines 570-589), independent of the templates/ system; mirror the new `[data-theme="light"]` variable overrides from styles.css into this inline `<style>` block, add the same `#themeToggle` button markup to its inline header/navbar HTML, and port the localStorage-based toggle logic from script.js into its inline `<script>` block so both pages share identical theme behavior and the same `rvv-theme` localStorage key.

- [ ] Manually verify both reports render correctly in both themes
  - Files: tournament_scheduler/html/html_exporter.py, tournament_scheduler/pipeline/calendar_viewer.py
  - Approach: Generate a season_plan.html and calendars.html (e.g. via the existing pipeline/CLI export commands), open both in a browser, toggle the theme button on each page, and confirm the toggle persists across a page reload (localStorage) and that text/background contrast is acceptable in both themes for header, navbar, score bar, metrics, filters, heatmap, club dashboard, and travel-stats sections.

## Notes
- Backlog item #43 (referenced in the feature description) corresponds to the "redesign HTML season-plan reports with professional UX/UI" plan (ARCHIVED/PLAN-2026-06-10-redesign-html-season-plan-reports-with-professional-ux-ui.md), which introduced the current dark-only `:root` palette in styles.css and the duplicated inline palette in calendar_viewer.py.
- season_plan.html is generated via tournament_scheduler/html/html_exporter.py + tournament_scheduler/html/templates/ (styles.css, page_template.html, header.html, navbar.html, script.js — loaded as constants in templates/__init__.py and substituted via $PLACEHOLDER$ tokens).
- calendars.html is generated via tournament_scheduler/pipeline/calendar_viewer.py, which has its own inline `<style>` and `<script>` blocks that duplicate (rather than reuse) the templates/ palette — both must be updated in parallel to keep the two reports visually consistent.
- No backend/CLI changes are required; this is a pure HTML/CSS/JS (client-side) feature using a `data-theme` attribute + localStorage, so the same generated file supports both themes without regeneration.

## Acceptance Criteria
- [ ] tournament_scheduler/html/templates/styles.css contains a light-theme override block (e.g. `[data-theme="light"]` or `.theme-light`) that redefines all color variables (`--bg`, `--bg-raised`, `--bg-surface`, `--border`, `--border-dim`, `--text`, `--text-secondary`, `--text-muted`, `--accent`, `--accent-dim`, `--accent-glow`, `--amber`, `--emerald`, `--rose`, `--violet`) with values different from the dark `:root` defaults.
- [ ] tournament_scheduler/html/templates/header.html contains a theme-toggle button element (e.g. `id="themeToggle"`) that is not present in the current dark-only header.
- [ ] tournament_scheduler/html/templates/script.js contains code that reads and writes a theme preference via `localStorage` and updates `document.documentElement` (or `document.body`) based on the stored value.
- [ ] tournament_scheduler/pipeline/calendar_viewer.py's generated HTML contains a matching theme-toggle button and a light-theme CSS override block, so calendars.html supports the same toggle as season_plan.html.
- [ ] Generating season_plan.html and calendars.html (via the existing export pipeline) does not fail, and the produced HTML files each contain both the dark `:root` palette and the new light-theme override block.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-10 — Added a [data-theme"light"] override block in styles.css providing light, high-contrast equivalents for all 15 themeable color variables (--bg through --violet), leaving --radius* and --font* untouched.
**Rationale:** Implementation already present in repository matching the spec exactly; no further changes needed.
**Findings:** Light theme palette confirmed present in styles.css at lines 23-39, single well-formed block, no duplicates.
LESSONS: none
**Files:** tournament_scheduler/html/templates/styles.css (already committed, no new changes)
**Commit:** 16294492

### 2026-06-10 — Added a #themeToggle icon button with sun/moon inline-SVG icons near the .header-right stat badges in header.html, following the existing .stat-badge markup conventions.
**Rationale:** Implementation already present in repository matching the spec; confirmed button markup exists with aria-label and title attributes.
**Findings:** Theme toggle button with sun/moon icons confirmed present in header.html within .header-right.
LESSONS: none
**Files:** tournament_scheduler/html/templates/header.html (already committed, no new changes)
**Commit:** 16294492

### 2026-06-10 — Added an IIFE near the end of script.js that reads the saved theme from localStorage (key rvv-theme), applies it via document.documentElement.dataset.theme, and wires a click handler on #themeToggle to flip the theme and persist the new value.
**Rationale:** Used dataset.theme to match the [data-themelight] CSS selector added in styles.css; followed existing addEventListener conventions in script.js.
**Findings:** Theme toggle logic added and verified with node --check (no syntax errors).
LESSONS: none
**Files:** tournament_scheduler/html/templates/script.js (+17/-0)
**Commit:** c87a12f (hockey)

### 2026-06-10 — Added .theme-toggle button styles consistent with .stat-badge/.navbar a (same padding/radius/hover transitions using CSS vars), added a --hover-overlay variable (light overlay in dark theme, dark overlay in light theme) and replaced the hardcoded rgba(255,255,255,0.06) hover background in .navbar a:hover with it, and added CSS rules to swap the sun/moon icon visibility based on [data-themelight].
**Rationale:** Introduced --hover-overlay instead of separately overriding .navbar a:hover and .theme-toggle:hover per theme, keeping the override surface small and consistent.
**Findings:** Hardcoded hover overlay color replaced with theme-aware variable; toggle button styling added; sun/moon icon swap wired via CSS attribute selector.
LESSONS: none
**Files:** tournament_scheduler/html/templates/styles.css (+11/-1)
**Commit:** 8e5a768 (hockey)

### 2026-06-10 — Mirrored the [data-themelight] variable overrides and --hover-overlay variable from styles.css into the inline <style> block, added the #themeToggle button with sun/moon icons to the navbar markup, added .theme-toggle styles, fixed the hardcoded rgba(255,255,255,0.06) navbar hover, and ported the localStorage-based toggle logic (rvv-theme key) into the inline <script> block.
**Rationale:** Kept the inline duplication pattern already used by calendar_viewer.py rather than extracting a shared template, since calendars.html is independent of the templates/ system as noted in the task.
**Findings:** Verified with python3 -m py_compile that the f-string template still compiles cleanly after doubling braces in the new CSS/JS blocks.
LESSONS: none
**Files:** tournament_scheduler/pipeline/calendar_viewer.py (+51/-1)
**Commit:** [pending — fill after commit]
