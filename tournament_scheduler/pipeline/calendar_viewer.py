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


# Inline SVG icons (16x16 viewBox, currentColor stroke, 1.5px stroke-width)
_ICON_CALENDAR = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="12" height="11" rx="2"/><line x1="2" y1="7" x2="14" y2="7"/><line x1="5" y1="1" x2="5" y2="5"/><line x1="11" y1="1" x2="11" y2="5"/></svg>'
_ICON_CLIPBOARD = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 1.5h5a1 1 0 011 1v1h-7v-1a1 1 0 011-1z"/><rect x="3" y="3.5" width="10" height="11" rx="1.5"/><line x1="6" y1="7" x2="10" y2="7"/><line x1="6" y1="10" x2="10" y2="10"/></svg>'
_ICON_USERS = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="4" r="2.5"/><path d="M1.5 14v-1.5a4 4 0 014-4h1a4 4 0 014 4V14"/><circle cx="12" cy="5" r="1.5"/><path d="M12 11.5a3 3 0 012.5 2.5"/></svg>'
_ICON_ARROW_UP = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="14" x2="8" y2="2"/><polyline points="3 7 8 2 13 7"/></svg>'
_ICON_EXTERNAL = '<svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h10a1 1 0 001-1v-3"/><polyline points="10 2 14 2 14 6"/><line x1="7" y1="9" x2="14" y2="2"/></svg>'
_ICON_REFRESH = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 1 4 1"/><path d="M1 8a7 7 0 017-7 6.8 6.8 0 015.6 3"/><polyline points="15 12 15 15 12 15"/><path d="M15 8a7 7 0 01-7 7 6.8 6.8 0 01-5.6-3"/></svg>'
_ICON_SEARCH = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6.5" cy="6.5" r="4.5"/><line x1="10" y1="10" x2="14.5" y2="14.5"/></svg>'
_ICON_CLOCK = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><polyline points="8 4 8 8 11 10"/></svg>'
_ICON_TERMINAL = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 6 6.5 8.5 4 11"/><line x1="8" y1="11" x2="12" y2="11"/><rect x="1" y="2" width="14" height="12" rx="2"/></svg>'
_ICON_BAR_CHART = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="14" x2="2" y2="6"/><line x1="6" y1="14" x2="6" y2="10"/><line x1="10" y1="14" x2="10" y2="4"/><line x1="14" y1="14" x2="14" y2="8"/></svg>'

def _cache_status(entry: dict[str, Any], ttl_hours: float = 6.0) -> str:
    """Return a freshness badge label for a cache entry.

    Returns one of: Blokkert, Cachet, Fersk, Utdatert, Ukjent.
    """
    blocked = entry.get("blocked", False)
    note = entry.get("note", "")
    ts = entry.get("scrape_timestamp", "")

    if blocked:
        return "Blokkert"

    if note and ("tidligere cache" in note.lower() or "bruker" in note.lower()):
        return "Cachet"

    if not ts:
        return "Ukjent"

    try:
        scraped_at = datetime.fromisoformat(ts)
        age = datetime.now() - scraped_at
        if age.total_seconds() <= ttl_hours * 3600:
            return "Fersk"
        return "Utdatert"
    except (ValueError, TypeError):
        return "Ukjent"


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _month_name(m: int, locale: str = "nb") -> str:
    nb = ["", "Januar", "Februar", "Mars", "April", "Mai", "Juni",
          "Juli", "August", "September", "Oktober", "November", "Desember"]
    return nb[m] if 1 <= m <= 12 else f"Måned {m}"


def generate_html(work_dir: str = ".pipeline", export_dir: str = "export") -> str:
    """Generate the calendar viewer HTML and return its file path.

    Writes to ``<export_dir>/calendars.html`` by default.
    """
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
                        link = f'<a class="ev-ext-link" href="{_escape_html(src_url)}" target="_blank" title="Åpne {_escape_html(src)} sin kalender">{_ICON_EXTERNAL}</a>' if src_url else ""
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
        entry = sources.get(name, {})
        cnt = entry.get("event_count", 0)
        ts = entry.get("scrape_timestamp", "")
        age = _age_string(ts)
        freshness = _cache_status(entry)
        club_filter_lines.append(
            f'<label class="filter-item" style="--cbg:{color["bg"]};--cborder:{color["border"]}">'
            f'<input type="checkbox" class="club-filter" data-club="{_escape_html(name)}" checked>'
            f'<span class="club-label">{_escape_html(name)}</span> '
            f'<span class="club-stats">({cnt} hendelser, {age})</span> '
            f'<span class="club-freshness">{_escape_html(freshness)}</span>'
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
    season_plan_path = Path(export_dir) / "season_plan.html"
    has_season_plan = season_plan_path.exists()

    html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RVV Miniputt — Skrapede kalendere</title>
<style>
  :root {{
    --bg: #09090b;
    --bg-raised: #18181b;
    --bg-surface: #27272a;
    --border: #3f3f46;
    --border-dim: #27272a;
    --text: #fafafa;
    --text-secondary: #a1a1aa;
    --text-muted: #71717a;
    --accent: #0ea5e9;
    --accent-dim: #0369a1;
    --accent-glow: rgba(14, 165, 233, 0.12);
    --hover-overlay: rgba(255, 255, 255, 0.06);
    --radius: 8px;
    --radius-sm: 4px;
    --radius-pill: 999px;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    --font-mono: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
  }}
  [data-theme="light"] {{
    --bg: #f4f4f5;
    --bg-raised: #ffffff;
    --bg-surface: #e4e4e7;
    --border: #d4d4d8;
    --border-dim: #e4e4e7;
    --text: #18181b;
    --text-secondary: #52525b;
    --text-muted: #71717a;
    --accent: #0284c7;
    --accent-dim: #38bdf8;
    --accent-glow: rgba(2, 132, 199, 0.10);
    --hover-overlay: rgba(0, 0, 0, 0.05);
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ height: 100%; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }}
  body {{ font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; height: 100%; font-size: 15px; }}
  .layout {{ display: flex; height: 100vh; }}

  /* Navbar */
  .navbar {{
    display: flex; align-items: center; gap: 2px;
    background: var(--bg-raised); padding: 0 16px;
    border-bottom: 1px solid var(--border-dim);
    height: 44px; flex-shrink: 0;
  }}
  .navbar .brand {{
    font-weight: 700; font-size: 13px; margin-right: 20px;
    color: var(--text); letter-spacing: -.01em;
    display: flex; align-items: center; gap: 6px;
  }}
  .nav-icon {{ display: inline-flex; align-items: center; opacity: .55; }}
  .nav-icon svg {{ display: block; width: 14px; height: 14px; }}
  .navbar a {{
    color: var(--text-muted); text-decoration: none;
    padding: 4px 10px; border-radius: var(--radius-sm);
    font-size: 12px; font-weight: 500;
    transition: color .15s, background .15s;
    display: inline-flex; align-items: center; gap: 5px;
  }}
  .navbar a:hover {{ background: var(--hover-overlay); color: var(--text-secondary); }}
  .navbar a.active {{
    background: var(--accent-glow); color: var(--accent); font-weight: 600;
  }}
  .navbar a.active .nav-icon {{ opacity: .85; }}

  /* Theme toggle */
  .theme-toggle {{
    display: flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; padding: 0;
    background: var(--bg-raised); border: 1px solid var(--border-dim);
    border-radius: var(--radius-pill); color: var(--text-muted);
    cursor: pointer; transition: color .15s, background .15s, border-color .15s;
  }}
  .theme-toggle:hover {{ background: var(--hover-overlay); color: var(--text-secondary); border-color: var(--border); }}
  .theme-toggle svg {{ width: 15px; height: 15px; flex-shrink: 0; }}
  .theme-toggle .icon-moon {{ display: none; }}
  [data-theme="light"] .theme-toggle .icon-sun {{ display: none; }}
  [data-theme="light"] .theme-toggle .icon-moon {{ display: block; }}

  /* Sidebar */
  .sidebar {{
    width: 320px; min-width: 320px;
    background: var(--bg-raised);
    border-right: 1px solid var(--border-dim);
    padding: 16px 14px; overflow-y: auto;
    position: sticky; top: 0; height: calc(100vh - 44px);
  }}
  .sidebar h2 {{
    font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .1em;
    color: var(--text-muted);
    margin: 18px 0 8px;
    display: flex; align-items: center; gap: 5px;
  }}
  .sidebar h2:first-child {{ margin-top: 0; }}
  .sidebar-icon {{ display: inline-flex; align-items: center; opacity: .55; }}
  .sidebar-icon svg {{ display: block; width: 12px; height: 12px; }}

  .filter-item {{
    display: flex; align-items: flex-start; gap: 6px;
    padding: 5px 8px; border-radius: var(--radius-sm);
    background: var(--cbg); border: 1px solid var(--cborder);
    cursor: pointer; font-size: 12px;
    margin-bottom: 4px;
    transition: box-shadow .15s, opacity .15s;
  }}
  .filter-item:hover {{ box-shadow: 0 0 0 1px var(--cborder); }}
  .filter-item input[type="checkbox"] {{
    accent-color: var(--cborder); flex-shrink: 0;
    width: 14px; height: 14px; cursor: pointer;
  }}
  .club-label {{
    display: block;
    font-weight: 600; font-size: 12px;
    color: #111; flex: 1 1 auto; min-width: 0;
    white-space: normal; overflow: visible; text-overflow: clip;
    overflow-wrap: anywhere; line-height: 1.25;
  }}
  .club-stats {{ color: #444; font-size: 10px; flex-shrink: 0; white-space: nowrap; }}
  .club-freshness {{
    font-size: 9px; padding: 1px 5px;
    border-radius: var(--radius-pill);
    font-weight: 600; flex-shrink: 0; white-space: nowrap;
    text-transform: uppercase; letter-spacing: .04em;
    color: #555;
  }}

  .month-filter-item {{
    display: inline-flex; align-items: center; gap: 3px;
    padding: 3px 8px; margin: 2px 1px;
    border-radius: var(--radius-pill);
    cursor: pointer; font-size: 11px; font-weight: 500;
    background: var(--bg-surface); border: 1px solid var(--border);
    color: var(--text-secondary);
    transition: background .15s, border-color .15s;
  }}
  .month-filter-item:hover {{ border-color: var(--text-muted); }}
  .month-filter-item input[type="checkbox"] {{
    accent-color: var(--accent); width: 12px; height: 12px;
  }}

  .sidebar .refresh-btn {{
    display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 7px 12px; border-radius: var(--radius-sm);
    cursor: pointer; font-size: 12px; font-weight: 500;
    text-decoration: none; margin: 6px 0;
    border: 1px solid var(--border);
    background: var(--bg-surface);
    color: var(--text-secondary);
    transition: background .15s, border-color .15s, color .15s;
  }}
  .sidebar .refresh-btn:hover {{
    background: var(--accent-glow);
    border-color: var(--accent-dim);
    color: var(--accent);
  }}
  .sidebar .refresh-btn.green {{
    background: rgba(34,197,94,.08);
    border-color: rgba(34,197,94,.2);
  }}
  .sidebar .refresh-btn.green:hover {{
    background: rgba(34,197,94,.14);
    border-color: rgba(34,197,94,.4);
  }}
  .sidebar .cli-hint {{
    cursor: default; padding: 8px 10px;
    font-size: 11px; line-height: 1.5;
    display: flex; align-items: flex-start; gap: 6px;
    color: var(--text-muted);
  }}
  .sidebar .cli-hint code {{
    background: var(--hover-overlay);
    padding: 1px 5px; border-radius: var(--radius-sm);
    font-size: 11px; font-family: var(--font-mono);
    color: var(--text-secondary);
  }}
  .count-badge {{
    font-size: 11px; color: var(--text-muted);
    margin-top: 12px; padding: 8px 0;
    border-top: 1px solid var(--border-dim);
    line-height: 1.6;
  }}

  /* Main */
  .main {{ flex: 1; overflow-y: auto; padding: 24px 28px 48px; }}
  .main::-webkit-scrollbar {{ width: 6px; }}
  .main::-webkit-scrollbar-track {{ background: transparent; }}
  .main::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

  h1 {{
    font-size: 20px; font-weight: 700; letter-spacing: -.02em;
    margin-bottom: 4px;
    display: flex; align-items: center; gap: 8px;
    color: var(--text);
  }}
  .header-icon {{ display: inline-flex; align-items: center; opacity: .6; }}
  .header-icon svg {{ display: block; width: 18px; height: 18px; }}
  .meta {{
    font-size: 12px; color: var(--text-muted);
    margin-bottom: 24px;
    display: flex; flex-wrap: wrap; gap: 6px 16px;
  }}
  .meta span {{ display: inline-flex; align-items: center; gap: 4px; }}
  .meta-icon {{ display: inline-flex; align-items: center; opacity: .45; }}
  .meta-icon svg {{ display: block; width: 12px; height: 12px; }}

  .month {{ margin-bottom: 32px; }}
  .month-title {{
    font-size: 14px; font-weight: 600; margin-bottom: 8px;
    color: var(--text-secondary);
    letter-spacing: -.01em;
  }}
  table.cal {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  td, th {{
    border: 1px solid var(--border-dim);
    padding: 4px; vertical-align: top;
    height: 74px;
  }}
  th {{
    background: var(--bg-raised);
    font-size: 10px; font-weight: 600;
    text-align: center; height: auto;
    padding: 6px 4px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .08em;
  }}
  td.empty {{ background: transparent; }}
  td.today {{
    background: var(--accent-glow);
    border-color: rgba(14, 165, 233, 0.2);
  }}
  .day-num {{
    font-weight: 600; font-size: 11px;
    margin-bottom: 3px; color: var(--text-muted);
  }}
  td.today .day-num {{ color: var(--accent); font-weight: 700; }}
  .events {{ display: flex; flex-direction: column; gap: 2px; }}
  .event {{
    padding: 2px 5px; border-radius: 3px;
    font-size: 9px; line-height: 1.4;
    cursor: default; position: relative;
    transition: filter .12s;
  }}
  .event:hover {{ filter: brightness(1.08); }}
  .ev-time {{ font-weight: 600; margin-right: 2px; font-size: 9px; }}
  .ev-name {{
    display: block; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
    font-weight: 600;
  }}
  .ev-meta {{ font-size: 8px; opacity: .7; }}
  .ev-meta a {{ text-decoration: none; color: inherit; }}
  .ev-meta a:hover {{ text-decoration: underline; }}
  .ev-ext-link {{
    display: inline-flex; align-items: center;
    opacity: .5; margin-left: 1px;
  }}
  .ev-ext-link:hover {{ opacity: .8; }}
  .ev-ext-link svg {{ display: block; width: 8px; height: 8px; }}

  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  @media (max-width: 768px) {{
    .layout {{ flex-direction: column; }}
    .navbar {{ overflow-x: auto; height: auto; padding: 8px 12px; }}
    .sidebar {{
      width: 100%; min-width: auto;
      height: auto; position: static;
      padding: 12px;
    }}
    .main {{ padding: 16px; }}
    td {{ height: 52px; }}
    h1 {{ font-size: 17px; }}
  }}
</style>
</head>
<body>
<div class="navbar">
  <span class="brand">RVV Miniputt</span>
  <a href="calendars.html" class="active"><span class="nav-icon">{_ICON_CALENDAR}</span> Skrapede kalendere</a>
  <a href="season_plan.html" class="{'active' if not has_season_plan else ''}"><span class="nav-icon">{_ICON_CLIPBOARD}</span> Sesongplan</a>
  <a href="season_plan_report.html" class=""><span class="nav-icon">{_ICON_BAR_CHART}</span> Rapport</a>
  <a href="#" onclick="document.querySelector('.main').scrollTo(0,0);return false" style="margin-left:auto;color:var(--text-muted)"><span class="nav-icon">{_ICON_ARROW_UP}</span></a>
  <button id="themeToggle" class="theme-toggle" aria-label="Bytt tema" title="Bytt tema">
    <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
  </button>
</div>
<div class="layout">
  <div class="sidebar">
    <h2><span class="sidebar-icon">{_ICON_USERS}</span> Klubber</h2>
    <div id="club-filters">{club_filter_html}</div>
    <h2><span class="sidebar-icon">{_ICON_CALENDAR}</span> Måneder</h2>
    <div id="month-filters">{month_filter_html}</div>
    <h2><span class="sidebar-icon">{_ICON_REFRESH}</span> Handlinger</h2>
    <a class="refresh-btn" href="#" onclick="location.reload()">Oppdater side</a>
    <span class="refresh-btn green cli-hint" title="Kjør denne kommandoen i terminalen for å tvinge re-skraping av alle kalendere">
      <span class="sidebar-icon">{_ICON_TERMINAL}</span> Kjør <code>rvv-miniputt calendars --refresh</code>
    </span>
    <p class="count-badge">{source_count} kilder, {total_events} hendelser<br>Oppdatert: {age_all}</p>
  </div>
  <div class="main">
    <h1><span class="header-icon">{_ICON_CALENDAR}</span> Skrapede kalendere</h1>
    <div class="meta">
      <span><span class="meta-icon">{_ICON_CALENDAR}</span> {start_date_str} &mdash; {end_date_str}</span>
      <span><span class="meta-icon">{_ICON_USERS}</span> {source_count} kilder</span>
      <span><span class="meta-icon">{_ICON_SEARCH}</span> {total_events} hendelser</span>
      <span><span class="meta-icon">{_ICON_CLOCK}</span> {age_all}</span>
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

(function() {{
  const THEME_KEY = 'rvv-theme';
  const toggle = document.getElementById('themeToggle');
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light' || saved === 'dark') {{
    document.documentElement.dataset.theme = saved;
  }}
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

    out_path = Path(export_dir) / "calendars.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path.resolve())


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Generate calendar viewer HTML from cache")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    parser.add_argument("--export-dir", default="export", help="Export directory for HTML output")
    parser.add_argument("--refresh", action="store_true", help="Force re-scrape (marks cache stale)")
    args = parser.parse_args()

    if args.refresh:
        from .cache_manager import ScrapedDataCache
        c = ScrapedDataCache(work_dir=args.work_dir)
        c.force_refresh()
        print("Cache markert som utdatert — kjør rvv-miniputt run for å re-skrape.")
    else:
        path = generate_html(work_dir=args.work_dir, export_dir=args.export_dir)
        print(f"Kalendervisning generert: {path}")
