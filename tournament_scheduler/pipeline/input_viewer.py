"""Input viewer — public, read-only overview of registered clubs/teams.

Reads only the whitelisted ``Lag`` worksheet of the input workbook (see
``input_workbook.PUBLIC_SHEET_WHITELIST``) and generates a standalone
``input.html`` page: teams grouped by age group, with club/age-group filters,
free-text search, and club/team totals. Internal configuration sheets
(``Aldersgrupper``, ``Innstillinger``, ``Kilder``, ``Datopreferanser``) and
the workbook file itself are never read or referenced by this module.
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from .input_workbook import read_public_teams

# Inline SVG icons (14x14 viewBox, currentColor stroke, 1.5px stroke-width) —
# kept consistent with calendar_viewer.py's icon set.
_ICON_CALENDAR = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="12" height="11" rx="2"/><line x1="2" y1="7" x2="14" y2="7"/><line x1="5" y1="1" x2="5" y2="5"/><line x1="11" y1="1" x2="11" y2="5"/></svg>'
_ICON_CLIPBOARD = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 1.5h5a1 1 0 011 1v1h-7v-1a1 1 0 011-1z"/><rect x="3" y="3.5" width="10" height="11" rx="1.5"/><line x1="6" y1="7" x2="10" y2="7"/><line x1="6" y1="10" x2="10" y2="10"/></svg>'
_ICON_USERS = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="4" r="2.5"/><path d="M1.5 14v-1.5a4 4 0 014-4h1a4 4 0 014 4V14"/><circle cx="12" cy="5" r="1.5"/><path d="M12 11.5a3 3 0 012.5 2.5"/></svg>'
_ICON_BAR_CHART = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="14" x2="2" y2="6"/><line x1="6" y1="14" x2="6" y2="10"/><line x1="10" y1="14" x2="10" y2="4"/><line x1="14" y1="14" x2="14" y2="8"/></svg>'


def _age_group_sort_key(age_group: str) -> tuple[int, str]:
    """Sort U-groups numerically (U7, U8, U10, U12, ...) before anything else."""
    digits = "".join(ch for ch in age_group if ch.isdigit())
    return (int(digits) if digits else 999, age_group)


def generate_html(
    *,
    input_path: str,
    export_dir: str = "export",
    calendars_path: str | None = None,
    season_label: str = "",
) -> str:
    """Generate ``input.html`` and return its path.

    Reads only the whitelisted ``Lag`` worksheet via
    :func:`input_workbook.read_public_teams`. Returns the path even when the
    sheet has no rows (an empty, valid page is written rather than nothing).
    """
    teams = read_public_teams(input_path)

    # Deduplicate identical (club, label, age_group) rows and sort for display.
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict[str, Any]] = []
    for team in teams:
        club = str(team.get("club") or "").strip()
        label = str(team.get("label") or "").strip()
        age_group = str(team.get("age_group") or "").strip()
        if not club or not label:
            continue
        key = (club, label, age_group)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"club": club, "label": label, "age_group": age_group})
    rows.sort(key=lambda r: (_age_group_sort_key(r["age_group"]), r["club"], r["label"]))

    all_clubs = sorted({r["club"] for r in rows})
    all_age_groups = sorted({r["age_group"] for r in rows}, key=_age_group_sort_key)
    total_teams = len(rows)
    total_clubs = len(all_clubs)

    club_options = "".join(
        f'<option value="{_html.escape(club)}">{_html.escape(club)}</option>' for club in all_clubs
    )
    age_options = "".join(
        f'<option value="{_html.escape(ag)}">{_html.escape(ag)}</option>' for ag in all_age_groups
    )

    groups_html: list[str] = []
    for age_group in all_age_groups:
        group_rows = [r for r in rows if r["age_group"] == age_group]
        group_clubs = len({r["club"] for r in group_rows})
        row_html = "".join(
            '<tr class="team-row" '
            f'data-club="{_html.escape(r["club"])}" '
            f'data-age="{_html.escape(age_group)}" '
            f'data-search="{_html.escape((r["club"] + " " + r["label"]).lower())}">'
            f'<td class="club-summary-name">{_html.escape(r["club"])}</td>'
            f'<td>{_html.escape(r["label"])}</td>'
            "</tr>"
            for r in group_rows
        )
        groups_html.append(
            '<section class="age-group-section">'
            f'<h2>{_html.escape(age_group)} '
            f'<span class="age-group-count">{len(group_rows)} lag &middot; {group_clubs} klubber</span></h2>'
            '<div class="table-wrap"><table class="club-summary-table">'
            '<thead><tr><th>Klubb</th><th>Lag</th></tr></thead>'
            f'<tbody>{row_html}</tbody></table></div>'
            "</section>"
        )
    if not groups_html:
        groups_html.append(
            '<div class="no-results" id="emptyState"><p>Ingen lag er registrert i input-arket ennå.</p></div>'
        )
    groups_section_html = "".join(groups_html)

    calendars_href = "calendars.html" if calendars_path and Path(calendars_path).exists() else ""
    calendars_nav = (
        f'<a href="{calendars_href}"><span class="nav-icon">{_ICON_CALENDAR}</span> Skrapede kalendere</a>'
        if calendars_href
        else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Påmeldte lag {_html.escape(season_label)} — RVV Hockey</title>
<style>
  :root {{
    --bg: #09090b; --bg-raised: #18181b; --bg-surface: #27272a;
    --border: #3f3f46; --border-dim: #27272a;
    --text: #fafafa; --text-secondary: #a1a1aa; --text-muted: #71717a;
    --accent: #0ea5e9; --accent-dim: #0369a1; --accent-glow: rgba(14, 165, 233, 0.12);
    --hover-overlay: rgba(255, 255, 255, 0.06);
    --radius: 8px; --radius-sm: 4px; --radius-pill: 999px;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
  }}
  [data-theme="light"] {{
    --bg: #f4f4f5; --bg-raised: #ffffff; --bg-surface: #e4e4e7;
    --border: #d4d4d8; --border-dim: #e4e4e7;
    --text: #18181b; --text-secondary: #52525b; --text-muted: #71717a;
    --accent: #0284c7; --accent-dim: #38bdf8; --accent-glow: rgba(2, 132, 199, 0.10);
    --hover-overlay: rgba(0, 0, 0, 0.05);
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ height: 100%; -webkit-font-smoothing: antialiased; }}
  body {{ font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; font-size: 15px; }}

  .navbar {{ display: flex; align-items: center; gap: 2px; background: var(--bg-raised); padding: 0 16px; border-bottom: 1px solid var(--border-dim); height: 44px; flex-shrink: 0; }}
  /* Hidden automatically when loaded inside an iframe (e.g. embedded on WordPress). */
  .rvv-embedded .navbar {{ display: none; }}
  .navbar .brand {{ font-weight: 700; font-size: 13px; margin-right: 20px; color: var(--text); letter-spacing: -.01em; }}
  .nav-icon {{ display: inline-flex; align-items: center; opacity: .55; }}
  .nav-icon svg {{ display: block; width: 14px; height: 14px; }}
  .navbar a {{ color: var(--text-muted); text-decoration: none; padding: 4px 10px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 500; transition: color .15s, background .15s; display: inline-flex; align-items: center; gap: 5px; }}
  .navbar a:hover {{ background: var(--hover-overlay); color: var(--text-secondary); }}
  .navbar a.active {{ background: var(--accent-glow); color: var(--accent); font-weight: 600; }}
  .navbar a.active .nav-icon {{ opacity: .85; }}
  .theme-toggle {{ margin-left: auto; background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 6px; border-radius: var(--radius-sm); display: flex; }}
  .theme-toggle:hover {{ background: var(--hover-overlay); color: var(--text-secondary); }}
  .theme-toggle svg {{ width: 16px; height: 16px; }}
  .icon-moon {{ display: none; }}
  [data-theme="light"] .icon-sun {{ display: none; }}
  [data-theme="light"] .icon-moon {{ display: block; }}

  .main {{ max-width: 1000px; margin: 0 auto; padding: 32px 24px 64px; }}
  h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: var(--text-muted); font-size: 13px; margin-bottom: 20px; }}

  .stat-badges {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 24px; }}
  .stat-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: var(--bg-raised); border: 1px solid var(--border-dim); border-radius: var(--radius-pill); font-size: 13px; color: var(--text-secondary); }}
  .stat-badge strong {{ color: var(--text); }}

  .filters {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid var(--border-dim); }}
  .filter-select, .filter-input {{ padding: 7px 12px; background: var(--bg-raised); border: 1px solid var(--border-dim); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 13px; font-family: var(--font); outline: none; min-width: 140px; }}
  .filter-select:focus, .filter-input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }}
  .filter-input {{ min-width: 200px; }}
  .filter-clear {{ padding: 7px 14px; background: transparent; border: 1px solid var(--border-dim); border-radius: var(--radius-sm); color: var(--text-muted); font-size: 12px; font-family: var(--font); cursor: pointer; }}
  .filter-clear:hover {{ background: var(--bg-surface); color: var(--text-secondary); }}

  .count-bar {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 10px 14px; background: var(--bg-raised); border: 1px solid var(--border-dim); border-radius: var(--radius); margin-bottom: 24px; font-size: 13px; color: var(--text-muted); }}
  .count-bar strong {{ color: var(--text-secondary); }}

  .age-group-section {{ margin-bottom: 28px; }}
  .age-group-section h2 {{ font-size: 15px; font-weight: 700; margin-bottom: 10px; display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }}
  .age-group-count {{ font-size: 12px; font-weight: 500; color: var(--text-muted); }}
  .table-wrap {{ overflow-x: auto; border: 1px solid var(--border-dim); border-radius: var(--radius-sm); }}
  .club-summary-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .club-summary-table th {{ padding: 9px 12px; background: var(--bg); color: var(--text-muted); font-weight: 700; text-align: left; border-bottom: 1px solid var(--border-dim); }}
  .club-summary-table td {{ padding: 8px 12px; color: var(--text-secondary); border-bottom: 1px solid var(--border-dim); }}
  .club-summary-table tr:last-child td {{ border-bottom: 0; }}
  .club-summary-name {{ color: var(--text); font-weight: 600; }}

  .no-results {{ text-align: center; padding: 48px 24px; color: var(--text-muted); }}

  @media (max-width: 768px) {{
    .main {{ padding: 20px 12px 48px; }}
    .navbar {{ overflow-x: auto; height: auto; padding: 8px 12px; }}
    .filters {{ flex-direction: column; }}
    .filter-select, .filter-input {{ min-width: 100%; }}
  }}
</style>
</head>
<body>
<script>if (window.self !== window.top) {{ document.documentElement.classList.add('rvv-embedded'); }}</script>
<div class="navbar">
  <span class="brand">RVV Miniputt</span>
  {calendars_nav}
  <a href="season_plan.html"><span class="nav-icon">{_ICON_CLIPBOARD}</span> Sesongplan</a>
  <a href="season_plan_report.html"><span class="nav-icon">{_ICON_BAR_CHART}</span> Rapport</a>
  <a href="input.html" class="active"><span class="nav-icon">{_ICON_USERS}</span> Påmeldte lag</a>
  <button id="themeToggle" class="theme-toggle" aria-label="Bytt tema" title="Bytt tema">
    <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
  </button>
</div>
<div class="main">
  <h1>Påmeldte lag</h1>
  <div class="subtitle">Oversikt over klubber og lag registrert for sesongen{(' &mdash; ' + _html.escape(season_label)) if season_label else ''}</div>
  <div class="stat-badges">
    <span class="stat-badge"><strong>{total_clubs}</strong>&nbsp;klubber</span>
    <span class="stat-badge"><strong>{total_teams}</strong>&nbsp;lag</span>
    <span class="stat-badge"><strong>{len(all_age_groups)}</strong>&nbsp;aldersgrupper</span>
  </div>
  <div class="filters">
    <select id="filterAge" class="filter-select">
      <option value="">Alle aldersgrupper</option>
      {age_options}
    </select>
    <select id="filterClub" class="filter-select">
      <option value="">Alle klubber</option>
      {club_options}
    </select>
    <input type="text" id="filterSearch" class="filter-input" placeholder="Søk etter klubb eller lag…">
    <button type="button" id="filterClear" class="filter-clear">Nullstill filtre</button>
  </div>
  <div class="count-bar">
    <span>Viser <strong id="visibleCount">{total_teams}</strong> av <strong>{total_teams}</strong> lag</span>
    <span>{total_clubs} klubber totalt</span>
  </div>
  {groups_section_html}
  <div class="no-results" id="noResults" style="display:none"><p>Ingen lag samsvarer med filtrene.</p></div>
</div>
<script>
(function() {{
  const ageSelect = document.getElementById('filterAge');
  const clubSelect = document.getElementById('filterClub');
  const searchInput = document.getElementById('filterSearch');
  const clearBtn = document.getElementById('filterClear');
  const groups = Array.from(document.querySelectorAll('.age-group-section'));
  const visibleCountEl = document.getElementById('visibleCount');
  const noResults = document.getElementById('noResults');
  if (!ageSelect || !clubSelect || !searchInput) return;

  function applyFilters() {{
    const age = ageSelect.value;
    const club = clubSelect.value;
    const q = searchInput.value.trim().toLowerCase();
    let visible = 0;
    groups.forEach((section) => {{
      let groupVisible = 0;
      section.querySelectorAll('.team-row').forEach((row) => {{
        const matchesAge = !age || row.dataset.age === age;
        const matchesClub = !club || row.dataset.club === club;
        const matchesSearch = !q || row.dataset.search.indexOf(q) !== -1;
        const show = matchesAge && matchesClub && matchesSearch;
        row.style.display = show ? '' : 'none';
        if (show) {{ groupVisible += 1; visible += 1; }}
      }});
      section.style.display = groupVisible ? '' : 'none';
    }});
    if (visibleCountEl) visibleCountEl.textContent = String(visible);
    if (noResults) noResults.style.display = visible ? 'none' : '';
  }}

  ageSelect.addEventListener('change', applyFilters);
  clubSelect.addEventListener('change', applyFilters);
  searchInput.addEventListener('input', applyFilters);
  if (clearBtn) {{
    clearBtn.addEventListener('click', () => {{
      ageSelect.value = '';
      clubSelect.value = '';
      searchInput.value = '';
      applyFilters();
    }});
  }}
  applyFilters();
}})();

(function() {{
  const THEME_KEY = 'rvv-theme';
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light' || saved === 'dark') {{
    document.documentElement.dataset.theme = saved;
  }}
  const toggle = document.getElementById('themeToggle');
  if (toggle) {{
    toggle.addEventListener('click', function() {{
      const current = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
      const next = current === 'light' ? 'dark' : 'light';
      document.documentElement.dataset.theme = next;
      localStorage.setItem(THEME_KEY, next);
    }});
  }}
}})();
</script>
</body>
</html>"""

    out_path = Path(export_dir) / "input.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path.resolve())


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Generer input.html fra input-arbeidsboken (Lag-arket)")
    parser.add_argument("--input-path", default="input.xlsx", help="Sti til input.xlsx")
    parser.add_argument("--export-dir", default="export", help="Eksportmappe for HTML-output")
    args = parser.parse_args()

    path = generate_html(input_path=args.input_path, export_dir=args.export_dir)
    print(f"Input-visning generert: {path}")
