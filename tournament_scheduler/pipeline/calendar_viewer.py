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

    # Generate month-by-month calendar
    def _month_html(year: int, month: int) -> str:
        import calendar
        cal = calendar.Calendar()
        month_days = cal.monthdayscalendar(year, month)
        month_name = _month_name(month)
        now = datetime.now()

        lines = [
            f'<div class="month" id="m{year}{month:02d}">',
            f'  <h3 class="month-title">{month_name} {year}</h3>',
            '  <table class="cal">',
            '    <thead><tr class="day-names">',
            '      <th>Man</th><th>Tir</th><th>Ons</th><th>Tor</th><th>Fre</th><th>Lør</th><th>Søn</th>',
            '    </tr></thead>',
            '    <tbody>',
        ]

        week_num = 0
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
                        dur = ev.get("duration_hours", 0)
                        dur_str = f"{dur:.1f}t" if dur > 0 else ""
                        link = f'<a href="{_escape_html(src_url)}" target="_blank" title="Åpne {_escape_html(src)} sin kalender">🔗</a>' if src_url else ""
                        lines.append(
                            f'<div class="event" style="background:{color["bg"]};border-left:3px solid {color["border"]}">'
                            f'<span class="ev-name">{name}</span> '
                            f'<span class="ev-meta">{_escape_html(src)}{" " + dur_str if dur_str else ""} {link}</span>'
                            f'</div>'
                        )
                    lines.append('          </div>')

                lines.append('        </td>')
            lines.append('      </tr>')
            week_num += 1

        lines.extend(['    </tbody>', '  </table>', '</div>'])
        return "\n".join(lines)

    # Build month list
    months_html: list[str] = []
    y, m = min_date.year, min_date.month
    end_y, end_m = max_date.year, max_date.month
    while (y < end_y) or (y == end_y and m <= end_m):
        months_html.append(_month_html(y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    # Build filter controls
    filter_lines: list[str] = []
    for name in source_names:
        color = color_map[name]
        cnt = sources.get(name, {}).get("event_count", 0)
        ts = sources.get(name, {}).get("scrape_timestamp", "")
        age = _age_string(ts)
        blocked = sources.get(name, {}).get("blocked", False)
        status = "🔴" if blocked else "🟢"
        filter_lines.append(
            f'<label class="filter-item" style="--cbg:{color["bg"]};--cborder:{color["border"]}">'
            f'<input type="checkbox" class="club-filter" data-club="{_escape_html(name)}" checked>'
            f'<span class="club-label">{_escape_html(name)}</span> '
            f'<span class="club-stats">({cnt} hendelser, {age}) {status}</span>'
            f'</label>'
        )
    filter_html = "\n".join(filter_lines)

    total_events = data.get("total_events", 0)
    source_count = data.get("source_count", 0)
    age_all = _age_string(updated_at)

    html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RVV Miniputt — Skrapede kalendere</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f5f5; color: #333; padding: 20px; }}
  h1 {{ font-size: 1.5em; margin-bottom: 4px; }}
  .meta {{ font-size: 0.85em; color: #666; margin-bottom: 16px; }}
  .meta span {{ margin-right: 16px; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }}
  .filter-item {{ display: inline-flex; align-items: center; gap: 4px;
                  padding: 4px 10px; border-radius: 6px;
                  background: var(--cbg); border: 1px solid var(--cborder);
                  cursor: pointer; font-size: 0.85em; }}
  .filter-item input {{ accent-color: var(--cborder); }}
  .club-label {{ font-weight: 600; }}
  .club-stats {{ color: #555; font-size: 0.9em; }}
  .month {{ margin-bottom: 32px; }}
  .month-title {{ font-size: 1.2em; margin-bottom: 8px; color: #444; }}
  table.cal {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  td, th {{ border: 1px solid #ddd; padding: 4px; vertical-align: top; height: 80px; }}
  th {{ background: #eee; font-size: 0.8em; font-weight: 600; text-align: center; height: auto; padding: 6px; }}
  td.empty {{ background: #fafafa; }}
  td.today {{ background: #fffde7; }}
  .day-num {{ font-weight: 600; font-size: 0.85em; margin-bottom: 2px; }}
  .events {{ display: flex; flex-direction: column; gap: 2px; }}
  .event {{ padding: 2px 4px; border-radius: 3px; font-size: 0.7em; line-height: 1.3; }}
  .ev-name {{ display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .ev-meta {{ font-size: 0.85em; color: #555; }}
  .ev-meta a {{ text-decoration: none; }}
  .hidden {{ display: none !important; }}
  a {{ color: #1E88E5; }}
  a:hover {{ text-decoration: underline; }}
  .refresh-btn {{ display: inline-block; padding: 6px 16px; background: #1E88E5;
                 color: #fff; border: none; border-radius: 6px; cursor: pointer;
                 font-size: 0.85em; text-decoration: none; margin-bottom: 16px; }}
  .refresh-btn:hover {{ background: #1565C0; }}
  @media (max-width: 768px) {{ td {{ height: 60px; font-size: 0.9em; }} }}
</style>
</head>
<body>
<h1>🗓️ RVV Miniputt — Skrapede kalendere</h1>
<div class="meta">
  <span>📅 {start_date_str} — {end_date_str}</span>
  <span>🏒 {source_count} kilder</span>
  <span>📊 {total_events} hendelser</span>
  <span>⏱️ Oppdatert: {age_all}</span>
</div>
<div class="filters">{filter_html}</div>
<p><a class="refresh-btn" href="#" onclick="location.reload()">🔄 Oppdater side</a>
<a class="refresh-btn" href="/rvv-miniputt calendars --refresh" style="background:#43A047">🔄 Tving re-skraping</a></p>
<div id="calendars">{''.join(months_html)}</div>
<script>
document.querySelectorAll('.club-filter').forEach(cb => {{
  cb.addEventListener('change', () => {{
    const active = new Set();
    document.querySelectorAll('.club-filter:checked').forEach(c => active.add(c.dataset.club));
    document.querySelectorAll('.event').forEach(el => {{
      const src = el.querySelector('.ev-meta')?.textContent?.trim().split(' ')[0];
      el.style.display = (src && active.has(src)) ? '' : 'none';
    }});
  }});
}});
</script>
</body>
</html>"""

    out_path = Path(work_dir) / "calendars.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path.resolve())
