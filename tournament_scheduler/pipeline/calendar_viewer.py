"""
Calendar viewer — self-contained HTML with month-grid, club filters, source links.

Reads from the unified scraped data cache (``.pipeline/cache/scraped_data.json``)
and generates ``.pipeline/calendars.html`` — a standalone HTML file that renders
a month-by-month calendar grid with:

  - Colour-coded events per club
  - Checkbox filters to toggle clubs on/off
  - Source links on each event
  - Scrape timestamp and data-age indicator
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .cache_manager import ScrapedDataCache


# Colour palette for clubs (distinct, accessible)
CLUB_COLORS: list[dict[str, str]] = [
    {"bg": "#E3F2FD", "border": "#1E88E5", "text": "#0D47A1"},  # blue
    {"bg": "#E8F5E9", "border": "#43A047", "text": "#1B5E20"},  # green
    {"bg": "#FFF3E0", "border": "#FB8C00", "text": "#E65100"},  # orange
    {"bg": "#F3E5F5", "border": "#8E24AA", "text": "#4A148C"},  # purple
    {"bg": "#FFEBEE", "border": "#E53935", "text": "#B71C1C"},  # red
    {"bg": "#E0F7FA", "border": "#00ACC1", "text": "#006064"},  # cyan
    {"bg": "#FFF8E1", "border": "#FDD835", "text": "#F57F17"},  # yellow
    {"bg": "#F1F8E9", "border": "#7CB342", "text": "#33691E"},  # lime
    {"bg": "#FBE9E7", "border": "#D84315", "text": "#BF360C"},  # deep orange
]


def _age_string(iso_str: str) -> str:
    """Return human-readable age from ISO timestamp."""
    if not iso_str:
        return "aldri"
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s siden"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() // 60)}m siden"
        if delta.days < 1:
            return f"{int(delta.total_seconds() // 3600)}t siden"
        return f"{delta.days}d siden"
    except (ValueError, TypeError):
        return "ukjent"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _month_name(m: int, locale: str = "nb") -> str:
    nb = ["", "Januar", "Februar", "Mars", "April", "Mai", "Juni",
          "Juli", "August", "September", "Oktober", "November", "Desember"]
    return nb[m] if 1 <= m <= 12 else f"Måned {m}"


def generate_html(work_dir: str = ".pipeline") -> str:
    """Generate the calendar viewer HTML and return its file path."""
    cache = ScrapedDataCache(work_dir)
    data = cache.read()
    sources: dict[str, Any] = data.get("sources", {})
    meta: dict[str, Any] = data.get("_meta", {})
    all_events = cache.get_all_events()

    # Assign colours per source
    source_names = sorted(sources.keys())
    color_map: dict[str, dict[str, str]] = {}
    for i, name in enumerate(source_names):
        color_map[name] = CLUB_COLORS[i % len(CLUB_COLORS)]

    # Build event lookup: date -> [events]
    from collections import defaultdict
    events_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    min_date: datetime | None = None
    max_date: datetime | None = None
    for ev in all_events:
        date_str = ev.get("date", "")
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            continue
        events_by_date[date_str].append(ev)
        if min_date is None or dt < min_date:
            min_date = dt
        if max_date is None or dt > max_date:
            max_date = dt

    if min_date is None or max_date is None:
        min_date = datetime.now()
        max_date = datetime.now()

    updated_at = meta.get("updated_at", "")
    start_date_str = meta.get("start_date", "")
    end_date_str = meta.get("end_date", "")

    # Collect all months in range for month filter
    all_months: list[tuple[int, int]] = []
    y, m = min_date.year, min_date.month
    end_y, end_m = max_date.year, max_date.month
    while (y < end_y) or (y == end_y and m <= end_m):
        all_months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    def _format_time(ev: dict[str, Any]) -> str:
        """Extract start and end time string from event."""
        dt_str = ev.get("datetime", "")
        dur = ev.get("duration_hours", 0)
        if not dt_str:
            return ""
        try:
            dt = datetime.fromisoformat(dt_str)
            start = dt.strftime("%H:%M")
            if dur and dur > 0:
                from datetime import timedelta
                end_dt = dt + timedelta(hours=dur)
                end = end_dt.strftime("%H:%M")
                return f"{start}-{end}"
            return start
        except (ValueError, TypeError):
            return ""

    # Generate month-by-month calendar
    def _month_html(year: int, month: int) -> str:
        import calendar
        cal = calendar.Calendar()
        month_days = cal.monthdayscalendar(year, month)
        month_name = _month_name(month)
        now = datetime.now()

        lines = [
            f'<div class="month" id="m{year}{month:02d}" data-year="{year}" data-month="{month:02d}">',
            f'  <h3 class="month-title">{month_name} {year}</h3>',
            '  <table class="cal">',
            '    <thead><tr class="day-names">',
            '      <th>Man</th><th>Tir</th><th>Ons</th><th>Tor</th><th>Fre</th><th>Lør</th><th>Søn</th>',
            '    </tr></thead>',
            '    <tbody>',
        ]

        for week in month_days:
            lines.append('      <tr>')
            for day_num in week:
                if day_num == 0:
                    lines.append('        <td class="empty"></td>')
                    continue
                date_str = f"{day_num:02d}.{month:02d}.{year}"
                day_events = events_by_date.get(date_str, [])
                is_today = (year == now.year and month == now.month and day_num == now.day)
                has_events = len(day_events) > 0

                cls = "day"
                if is_today:
                    cls += " today"
                if has_events:
                    cls += " has-events"

                lines.append(f'        <td class="{cls}">')
                lines.append(f'          <div class="day-num">{day_num}</div>')

                if day_events:
                    lines.append('          <div class="events">')
                    for ev in day_events:
                        src = ev.get("_source", "?")
                        src_url = ev.get("_source_url", "")
                        color = color_map.get(src, CLUB_COLORS[-1])
                        name = _escape_html(ev.get("name", "?"))
                        time_str = _format_time(ev)
                        link = f'<a href="{_escape_html(src_url)}" target="_blank" title="Åpne {_escape_html(src)} sin kalender">🔗</a>' if src_url else ""
                        lines.append(
                            f'<div class="event" data-source="{_escape_html(src)}" style="background:{color["bg"]};border-left:3px solid {color["border"]};color:{color["text"]}" title="{_escape_html(src)} — {name}">'
                            + (f'<span class="ev-time">{time_str}</span> ' if time_str else '')
                            + f'<span class="ev-name">{name}</span> '
                            + f'<span class="ev-meta">{_escape_html(src)} {link}</span>'
                            + f'</div>'
                        )
                    lines.append('          </div>')

                lines.append('        </td>')
            lines.append('      </tr>')

        lines.extend(['    </tbody>', '  </table>', '</div>'])
        return "\n".join(lines)

    # Build month list
    months_html: list[str] = []
    for y, m in all_months:
        months_html.append(_month_html(y, m))

    # Build club filter controls
    club_filter_lines: list[str] = []
    for name in source_names:
        color = color_map[name]
        cnt = sources.get(name, {}).get("event_count", 0)
        ts = sources.get(name, {}).get("scrape_timestamp", "")
        age = _age_string(ts)
        blocked = sources.get(name, {}).get("blocked", False)
        status = "🔴" if blocked else "🟢"
        club_filter_lines.append(
            f'<label class="filter-item" style="--cbg:{color["bg"]};--cborder:{color["border"]}">'
            f'<input type="checkbox" class="club-filter" data-club="{_escape_html(name)}" checked>'
            f'<span class="club-label">{_escape_html(name)}</span> '
            f'<span class="club-stats">({cnt} hendelser, {age}) {status}</span>'
            f'</label>'
        )
    club_filter_html = "\n".join(club_filter_lines)

    # Build month filter controls
    month_filter_lines: list[str] = []
    for y, m in all_months:
        mn = _month_name(m)
        mid = f"m{y}{m:02d}"
        month_filter_lines.append(
            f'<label class="month-filter-item">'
            f'<input type="checkbox" class="month-filter" data-month="{mid}" checked>'
            f'<span>{mn} {y}</span>'
            f'</label>'
        )
    month_filter_html = "\n".join(month_filter_lines)

    total_events = data.get("total_events", 0)
    source_count = data.get("source_count", 0)
    age_all = _age_string(updated_at)

    # Check if season plan exists alongside
    season_plan_path = Path(work_dir) / "season_plan.html"
    has_season_plan = season_plan_path.exists()

    html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RVV Miniputt — Skrapede kalendere</title>
<style>
  :root {{
    --ice: #0f172a;
    --ice-light: #1e293b;
    --ice-surface: #334155;
    --ice-border: #475569;
    --text: #f1f5f9;
    --text-dim: #94a3b8;
    --accent: #38bdf8;
    --accent-dim: #0284c7;
    --radius: 8px;
    --radius-sm: 4px;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ height: 100%; }}
  body {{ font-family: var(--font); background: var(--ice); color: var(--text); line-height: 1.5; }}
  .layout {{ display: flex; height: 100vh; }}
  
  /* Navbar — matches season_plan */
  .navbar {{ display: flex; align-items: center; gap: 4px;
             background: #1a1a2e; color: #fff; padding: 8px 16px;
             border-bottom: 1px solid #333; flex-shrink: 0; }}
  .navbar .brand {{ font-weight: 700; font-size: 0.9em; margin-right: 20px; color: var(--accent); }}
  .navbar a {{ color: #94a3b8; text-decoration: none; padding: 4px 12px;
               border-radius: 4px; font-size: 0.8em; }}
  .navbar a:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
  .navbar a.active {{ background: var(--accent); color: #0f172a; font-weight: 600; }}
  
  /* Sidebar — dark theme */
  .sidebar {{ width: 270px; min-width: 270px; background: var(--ice-light);
              border-right: 1px solid var(--ice-surface);
              padding: 14px; overflow-y: auto; position: sticky; top: 0; height: calc(100vh - 40px); }}
  .sidebar h2 {{ font-size: 0.85em; margin: 14px 0 6px; color: var(--text-dim);
                  text-transform: uppercase; letter-spacing: .08em; }}
  .sidebar h2:first-child {{ margin-top: 0; }}
  .filter-item {{ display: flex; align-items: center; gap: 3px;
                  padding: 3px 8px; border-radius: var(--radius-sm);
                  background: var(--cbg); border: 1px solid var(--cborder);
                  cursor: pointer; font-size: 0.78em; margin-bottom: 3px; }}
  .filter-item input {{ accent-color: var(--cborder); flex-shrink: 0; }}
  .club-label {{ font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #111; }}
  .club-stats {{ color: #444; font-size: 0.85em; flex-shrink: 0; }}
  .month-filter-item {{ display: inline-flex; align-items: center; gap: 2px;
                        padding: 2px 6px; margin: 1px; border-radius: var(--radius-sm);
                        cursor: pointer; font-size: 0.75em;
                        background: var(--ice-surface); border: 1px solid var(--ice-border);
                        color: var(--text); }}
  .month-filter-item input {{ accent-color: var(--accent); }}
  .sidebar .refresh-btn {{ display: block; padding: 6px 12px; background: var(--accent-dim);
                          color: #fff; border: none; border-radius: var(--radius-sm); cursor: pointer;
                          font-size: 0.78em; text-decoration: none; margin: 4px 0; text-align: center; }}
  .sidebar .refresh-btn:hover {{ background: var(--accent); }}
  .sidebar .refresh-btn.green {{ background: #2E7D32; }}
  .sidebar .refresh-btn.green:hover {{ background: #388E3C; }}
  .count-badge {{ font-size: 0.7em; color: var(--text-dim); margin-top: 8px; }}
  
  /* Main content — dark theme */
  .main {{ flex: 1; overflow-y: auto; padding: 20px; }}
  h1 {{ font-size: 1.2em; margin-bottom: 4px; font-weight: 700; letter-spacing: -.02em; }}
  h1 span {{ color: var(--accent); }}
  .meta {{ font-size: 0.8em; color: var(--text-dim); margin-bottom: 16px; }}
  .meta span {{ margin-right: 14px; }}
  .month {{ margin-bottom: 28px; }}
  .month-title {{ font-size: 1.05em; margin-bottom: 6px; color: var(--accent); font-weight: 600; }}
  table.cal {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  td, th {{ border: 1px solid var(--ice-border); padding: 3px; vertical-align: top; height: 70px; }}
  th {{ background: var(--ice-light); font-size: 0.72em; font-weight: 600; text-align: center;
        height: auto; padding: 5px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .05em; }}
  td.empty {{ background: var(--ice); }}
  td.today {{ background: rgba(56, 189, 248, .1); border-color: var(--accent-dim); }}
  .day-num {{ font-weight: 600; font-size: 0.8em; margin-bottom: 2px; color: var(--text-dim); }}
  td.today .day-num {{ color: var(--accent); }}
  .events {{ display: flex; flex-direction: column; gap: 1px; }}
  .event {{ padding: 2px 4px; border-radius: var(--radius-sm); font-size: 0.65em; line-height: 1.3;
            cursor: default; position: relative; }}
  .event:hover {{ filter: brightness(1.1); }}
  .ev-time {{ font-weight: 600; margin-right: 2px; font-size: 0.95em; }}
  .ev-name {{ display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }}
  .ev-meta {{ font-size: 0.85em; opacity: 0.8; }}
  .ev-meta a {{ text-decoration: none; color: inherit; }}
  .ev-meta a:hover {{ text-decoration: underline; }}
  a {{ color: var(--accent); }}
  a:hover {{ text-decoration: underline; }}
  @media (max-width: 768px) {{ .layout {{ flex-direction: column; }} .navbar {{ overflow-x: auto; }} .sidebar {{ width: 100%; min-width: auto; height: auto; position: static; }} .main {{ padding: 10px; }} td {{ height: 50px; }} }}
</style>
</head>
<body>
<div class="navbar">
  <span class="brand">🏒 RVV Miniputt</span>
  <a href="calendars.html" class="active">🗓️ Skrapede kalendere</a>
  <a href="season_plan.html" class="{'active' if not has_season_plan else ''}">📋 Sesongplan</a>
  <a href="#" onclick="document.querySelector('.main').scrollTo(0,0);return false" style="margin-left:auto;color:#666">⬆️ Topp</a>
</div>
<div class="layout">
  <div class="sidebar">
    <h2>🏒 Klubber</h2>
    <div id="club-filters">{club_filter_html}</div>
    <h2>📅 Måneder</h2>
    <div id="month-filters">{month_filter_html}</div>
    <h2>🔄</h2>
    <a class="refresh-btn" href="#" onclick="location.reload()">Oppdater side</a>
    <a class="refresh-btn green" href="/rvv-miniputt calendars --refresh">Tving re-skraping</a>
    <p class="count-badge">{source_count} kilder, {total_events} hendelser<br>Oppdatert: {age_all}</p>
  </div>
  <div class="main">
    <h1>🗓️ Skrapede kalendere</h1>
    <div class="meta">
      <span>📅 {start_date_str} — {end_date_str}</span>
      <span>🏒 {source_count} kilder</span>
      <span>📊 {total_events} hendelser</span>
      <span>⏱️ {age_all}</span>
    </div>
    <div id="calendars">{''.join(months_html)}</div>
  </div>
</div>
<script>
document.querySelectorAll('.club-filter').forEach(cb => cb.addEventListener('change', applyFilters));
document.querySelectorAll('.month-filter').forEach(cb => cb.addEventListener('change', applyFilters));

function applyFilters() {{
  const activeClubs = new Set();
  document.querySelectorAll('.club-filter:checked').forEach(c => activeClubs.add(c.dataset.club));
  document.querySelectorAll('.event').forEach(el => {{
    const src = el.dataset.source;
    el.style.display = (src && activeClubs.has(src)) ? '' : 'none';
  }});

  const activeMonths = new Set();
  document.querySelectorAll('.month-filter:checked').forEach(c => activeMonths.add(c.dataset.month));
  document.querySelectorAll('.month').forEach(el => {{
    el.style.display = activeMonths.has(el.id) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    out_path = Path(work_dir) / "calendars.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path.resolve())


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Generate calendar viewer HTML from cache")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    parser.add_argument("--refresh", action="store_true", help="Force re-scrape (marks cache stale)")
    args = parser.parse_args()

    if args.refresh:
        from .cache_manager import ScrapedDataCache
        c = ScrapedDataCache(work_dir=args.work_dir)
        c.force_refresh()
        print("Cache markert som utdatert — kjør /rvv-miniputt run for å re-skrape.")
    else:
        path = generate_html(work_dir=args.work_dir)
        print(f"Kalendervisning generert: {path}")
