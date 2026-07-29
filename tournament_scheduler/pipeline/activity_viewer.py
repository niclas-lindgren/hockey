"""Standalone public activity calendar page generation (issue #33)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .activity_export import build_activities_payload


def generate_activity_artifacts(
    *,
    input_path: str,
    export_dir: str = "export",
    default_year: int | None = None,
    generated_at: str | None = None,
) -> dict[str, str] | None:
    """Write ``activities.json`` and ``activities/index.html`` for *input_path*.

    Returns ``None`` when the workbook has no supported activity table.
    """
    payload = build_activities_payload(input_path, default_year=default_year, generated_at=generated_at)
    if payload is None:
        return None

    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    json_path = export_path / "activities.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    html_path = Path(generate_html(export_dir=str(export_path)))
    return {"activities_json": str(json_path), "activities_html": str(html_path)}


def generate_html(*, export_dir: str = "export") -> str:
    """Write the standalone ``activities/index.html`` shell and return its path."""
    activities_dir = Path(export_dir) / "activities"
    activities_dir.mkdir(parents=True, exist_ok=True)
    html_path = activities_dir / "index.html"
    html_path.write_text(_HTML, encoding="utf-8")
    return str(html_path)


_HTML = r"""<!doctype html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aktivitetskalender for Region Viken Vest</title>
<style>
  :root {
    --bg: #f8fafc; --surface: #ffffff; --surface-soft: #eef2f7; --border: #d8e1ec;
    --text: #102033; --muted: #5c6f85; --accent: #0d6efd; --accent-dark: #074fa7;
    --today: #ef4444; --next: #f59e0b; --shadow: 0 18px 45px rgba(15, 23, 42, .10);
    --radius: 18px; --font: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html { min-width: 0; overflow-x: hidden; }
  body { margin: 0; min-width: 0; overflow-x: hidden; background: radial-gradient(circle at top left, #e0f2fe, transparent 28rem), var(--bg); color: var(--text); font-family: var(--font); line-height: 1.5; }
  .wrap { width: min(1180px, 100%); margin: 0 auto; padding: clamp(16px, 3vw, 32px); }
  header { display: grid; gap: 10px; margin-bottom: 20px; }
  .eyebrow { color: var(--accent-dark); font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: 0; font-size: clamp(28px, 5vw, 48px); letter-spacing: -.04em; line-height: 1.04; }
  .lead { max-width: 760px; margin: 0; color: var(--muted); font-size: clamp(15px, 2vw, 18px); }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 12px; margin: 22px 0; background: rgba(255,255,255,.78); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); backdrop-filter: blur(12px); }
  .segmented { display: inline-flex; padding: 4px; background: var(--surface-soft); border-radius: 999px; }
  .segmented button, .filter { min-height: 40px; border: 0; border-radius: 999px; font: inherit; }
  .segmented button { padding: 0 16px; color: var(--muted); background: transparent; cursor: pointer; font-weight: 700; }
  .segmented button[aria-pressed="true"] { background: var(--surface); color: var(--accent-dark); box-shadow: 0 6px 16px rgba(15,23,42,.10); }
  label { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); font-size: 14px; font-weight: 700; }
  .filter { padding: 0 14px; border: 1px solid var(--border); background: var(--surface); color: var(--text); min-width: 180px; }
  .status { margin-left: auto; color: var(--muted); font-size: 14px; }
  .panel { background: rgba(255,255,255,.86); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); }
  .year-layout { display: grid; grid-template-columns: minmax(320px, 1fr) minmax(280px, 380px); gap: 18px; padding: clamp(12px, 2vw, 22px); }
  .wheel-shell { min-width: 0; overflow: hidden; border-radius: calc(var(--radius) - 6px); background: linear-gradient(180deg, #fff, #f6f9fd); }
  .wheel { display: block; width: 100%; height: auto; max-height: 680px; }
  .month-label { fill: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
  .month-ring { fill: none; stroke: #d8e1ec; stroke-width: 1; }
  .today-line { stroke: var(--today); stroke-width: 2; stroke-linecap: round; }
  .activity-marker { cursor: pointer; outline: none; }
  .activity-marker circle { stroke: #fff; stroke-width: 2; filter: drop-shadow(0 3px 5px rgba(15,23,42,.22)); }
  .activity-marker:focus-visible circle { stroke: #111827; stroke-width: 4; }
  .activity-marker.next circle { stroke: var(--next); stroke-width: 4; }
  .details { padding: 18px; align-self: start; position: sticky; top: 12px; }
  .details h2 { margin: 0 0 8px; font-size: 20px; }
  .details dl { display: grid; grid-template-columns: auto 1fr; gap: 8px 12px; margin: 14px 0 0; }
  .details dt { color: var(--muted); font-weight: 800; }
  .details dd { margin: 0; }
  .details a { color: var(--accent-dark); font-weight: 800; }
  .badge-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .badge { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 9px; border-radius: 999px; color: #fff; font-size: 12px; font-weight: 800; }
  .list-view { display: none; padding: clamp(12px, 2vw, 22px); }
  .month-group { margin-bottom: 20px; }
  .month-group h2 { margin: 0 0 10px; font-size: 18px; }
  .activity-list { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
  .activity-card { width: 100%; text-align: left; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); padding: 14px; cursor: pointer; font: inherit; color: var(--text); }
  .activity-card:focus-visible { outline: 3px solid rgba(13,110,253,.35); outline-offset: 2px; }
  .activity-card.next { border-color: var(--next); box-shadow: 0 0 0 3px rgba(245,158,11,.20); }
  .activity-card time { display: block; color: var(--muted); font-size: 13px; font-weight: 800; }
  .activity-card strong { display: block; margin-top: 2px; }
  .empty { padding: 40px 18px; color: var(--muted); text-align: center; }
  .view-list .year-layout { display: none; }
  .view-list .list-view { display: block; }
  .view-wheel .year-layout { display: grid; }
  .view-wheel .list-view { display: none; }
  @media (max-width: 760px) {
    .wrap { padding: 14px; }
    .toolbar { align-items: stretch; }
    .status { width: 100%; margin-left: 0; }
    label, .filter, .segmented { width: 100%; }
    .segmented button { flex: 1; }
    .year-layout { grid-template-columns: 1fr; }
    .details { position: static; }
    .mobile-default .year-layout { display: none; }
    .mobile-default .list-view { display: block; }
  }
</style>
</head>
<body class="view-wheel">
<div class="wrap">
  <header>
    <div class="eyebrow">RVV Hockey</div>
    <h1>Aktivitetskalender</h1>
    <p class="lead">Årshjul og kronologisk liste for aktiviteter i Region Viken Vest. Velg aldersgruppe for å se relevante samlinger, kurs og møteplasser.</p>
  </header>

  <div class="toolbar" aria-label="Visningsvalg og filtre">
    <div class="segmented" role="group" aria-label="Velg visning">
      <button type="button" id="wheelView" aria-pressed="true">Årshjul</button>
      <button type="button" id="listView" aria-pressed="false">Liste</button>
    </div>
    <label for="ageFilter">Aldersgruppe
      <select id="ageFilter" class="filter"><option value="">Alle aldersgrupper</option></select>
    </label>
    <div id="activityStatus" class="status" aria-live="polite">Laster aktiviteter…</div>
  </div>

  <main id="app" class="panel" aria-busy="true">
    <section class="year-layout" aria-labelledby="wheelHeading">
      <div class="wheel-shell">
        <h2 id="wheelHeading" class="sr-only" style="position:absolute;left:-9999px">Årshjul</h2>
        <svg id="yearWheel" class="wheel" viewBox="0 0 720 720" role="img" aria-label="Aktiviteter plassert etter dato gjennom året"></svg>
      </div>
      <aside id="details" class="details" tabindex="-1" aria-live="polite">
        <h2>Velg en aktivitet</h2>
        <p>Trykk på en markør i årshjulet eller en aktivitet i listen for detaljer.</p>
      </aside>
    </section>
    <section id="listContainer" class="list-view" aria-label="Kronologisk aktivitetsliste"></section>
  </main>
</div>
<script>
(function() {
  const DATA_URL = '../activities.json';
  const MONTHS = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember'];
  const MONTH_SHORT = ['jan','feb','mar','apr','mai','jun','jul','aug','sep','okt','nov','des'];
  const COLORS = ['#0d6efd','#7c3aed','#059669','#dc2626','#ea580c','#0891b2','#be123c','#4f46e5','#15803d','#9333ea'];
  const colorByType = new Map();
  let allActivities = [];
  let filteredActivities = [];
  let nextActivityId = null;

  const body = document.body;
  const app = document.getElementById('app');
  const svg = document.getElementById('yearWheel');
  const details = document.getElementById('details');
  const listContainer = document.getElementById('listContainer');
  const ageFilter = document.getElementById('ageFilter');
  const status = document.getElementById('activityStatus');
  const wheelBtn = document.getElementById('wheelView');
  const listBtn = document.getElementById('listView');

  if (window.matchMedia('(max-width: 760px)').matches) {
    body.classList.add('mobile-default', 'view-list');
    body.classList.remove('view-wheel');
    wheelBtn.setAttribute('aria-pressed', 'false');
    listBtn.setAttribute('aria-pressed', 'true');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  }

  function formatDate(iso) {
    return new Intl.DateTimeFormat('nb-NO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(iso + 'T00:00:00'));
  }

  function dayOfYear(date) {
    const start = new Date(date.getFullYear(), 0, 1);
    return Math.floor((date - start) / 86400000) + 1;
  }

  function daysInYear(year) {
    return ((year % 4 === 0 && year % 100 !== 0) || year % 400 === 0) ? 366 : 365;
  }

  function dateToAngle(iso, year) {
    const date = new Date(iso + 'T00:00:00');
    const targetYear = year || date.getFullYear();
    const fraction = (dayOfYear(date) - 1) / daysInYear(targetYear);
    return fraction * Math.PI * 2 - Math.PI / 2;
  }

  function colorFor(type) {
    const key = type || 'annet';
    if (!colorByType.has(key)) colorByType.set(key, COLORS[colorByType.size % COLORS.length]);
    return colorByType.get(key);
  }

  function withIds(activities) {
    return activities.map((activity, index) => ({ ...activity, id: `activity-${index}` }));
  }

  function setView(view) {
    const list = view === 'list';
    body.classList.toggle('view-list', list);
    body.classList.toggle('view-wheel', !list);
    wheelBtn.setAttribute('aria-pressed', String(!list));
    listBtn.setAttribute('aria-pressed', String(list));
    announceHeight();
  }

  function populateFilters(activities) {
    const groups = Array.from(new Set(activities.flatMap(a => a.age_groups || []))).sort((a, b) => a.localeCompare(b, 'nb', { numeric: true }));
    ageFilter.innerHTML = '<option value="">Alle aldersgrupper</option>' + groups.map(group => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`).join('');
  }

  function applyFilter() {
    const selected = ageFilter.value;
    filteredActivities = selected ? allActivities.filter(a => (a.age_groups || []).includes(selected)) : allActivities.slice();
    render();
  }

  function findNextActivity(activities) {
    const todayIso = new Date().toISOString().slice(0, 10);
    const upcoming = activities.filter(a => a.date >= todayIso).sort((a, b) => a.date.localeCompare(b.date));
    return upcoming.length ? upcoming[0].id : null;
  }

  function render() {
    nextActivityId = findNextActivity(allActivities);
    status.textContent = filteredActivities.length === 1 ? 'Viser 1 aktivitet' : `Viser ${filteredActivities.length} aktiviteter`;
    renderWheel();
    renderList();
    app.setAttribute('aria-busy', 'false');
    announceHeight();
  }

  function renderWheel() {
    const width = 720, cx = 360, cy = 360, radius = 255;
    const year = filteredActivities[0] ? Number(filteredActivities[0].date.slice(0, 4)) : new Date().getFullYear();
    svg.innerHTML = '';
    const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    ring.setAttribute('class', 'month-ring'); ring.setAttribute('cx', cx); ring.setAttribute('cy', cy); ring.setAttribute('r', radius);
    svg.appendChild(ring);

    for (let month = 0; month < 12; month++) {
      const date = new Date(year, month, 15);
      const angle = dateToAngle(date.toISOString().slice(0, 10), year);
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('class', 'month-label'); text.setAttribute('text-anchor', 'middle'); text.setAttribute('dominant-baseline', 'middle');
      text.setAttribute('x', cx + Math.cos(angle) * (radius + 42)); text.setAttribute('y', cy + Math.sin(angle) * (radius + 42));
      text.textContent = MONTH_SHORT[month]; svg.appendChild(text);
    }

    const today = new Date();
    if (today.getFullYear() === year) {
      const angle = dateToAngle(today.toISOString().slice(0, 10), year);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('class', 'today-line');
      line.setAttribute('x1', cx + Math.cos(angle) * 70); line.setAttribute('y1', cy + Math.sin(angle) * 70);
      line.setAttribute('x2', cx + Math.cos(angle) * (radius + 22)); line.setAttribute('y2', cy + Math.sin(angle) * (radius + 22));
      svg.appendChild(line);
    }

    if (!filteredActivities.length) {
      const empty = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      empty.setAttribute('x', width / 2); empty.setAttribute('y', width / 2); empty.setAttribute('text-anchor', 'middle'); empty.setAttribute('fill', '#5c6f85');
      empty.textContent = 'Ingen aktiviteter for valgt filter'; svg.appendChild(empty); return;
    }

    filteredActivities.forEach((activity, index) => {
      const angle = dateToAngle(activity.date, year);
      const lane = index % 4;
      const r = radius - lane * 24;
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', `activity-marker${activity.id === nextActivityId ? ' next' : ''}`);
      g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0');
      g.setAttribute('aria-label', `${formatDate(activity.date)}: ${activity.title}`);
      g.setAttribute('transform', `translate(${cx + Math.cos(angle) * r}, ${cy + Math.sin(angle) * r})`);
      g.addEventListener('click', () => showDetails(activity));
      g.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); showDetails(activity); } });
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('r', activity.id === nextActivityId ? 10 : 8); circle.setAttribute('fill', colorFor(activity.type));
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title'); title.textContent = `${formatDate(activity.date)} — ${activity.title}`;
      g.appendChild(title); g.appendChild(circle); svg.appendChild(g);
    });
  }

  function renderList() {
    if (!filteredActivities.length) { listContainer.innerHTML = '<div class="empty">Ingen aktiviteter for valgt filter.</div>'; return; }
    const groups = new Map();
    filteredActivities.forEach(activity => {
      const date = new Date(activity.date + 'T00:00:00');
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(activity);
    });
    listContainer.innerHTML = Array.from(groups.entries()).map(([key, activities]) => {
      const monthIndex = Number(key.slice(5, 7)) - 1;
      const year = key.slice(0, 4);
      const cards = activities.map(activity => `
        <li><button type="button" class="activity-card${activity.id === nextActivityId ? ' next' : ''}" data-id="${activity.id}">
          <time datetime="${escapeHtml(activity.date)}">${escapeHtml(formatDate(activity.date))}</time>
          <strong>${escapeHtml(activity.title)}</strong>
          <span>${escapeHtml(activity.location || 'Sted ikke oppgitt')}</span>
        </button></li>`).join('');
      return `<section class="month-group"><h2>${MONTHS[monthIndex]} ${year}</h2><ul class="activity-list">${cards}</ul></section>`;
    }).join('');
    listContainer.querySelectorAll('.activity-card').forEach(card => {
      card.addEventListener('click', () => showDetails(allActivities.find(a => a.id === card.dataset.id)));
    });
  }

  function showDetails(activity) {
    if (!activity) return;
    const badges = (activity.age_groups || []).map(group => `<span class="badge" style="background:${colorFor(activity.type)}">${escapeHtml(group)}</span>`).join('');
    details.innerHTML = `
      <h2>${escapeHtml(activity.title)}</h2>
      <p>${activity.description ? escapeHtml(activity.description) : 'Ingen ekstra beskrivelse er oppgitt.'}</p>
      <div class="badge-row">${badges || `<span class="badge" style="background:${colorFor(activity.type)}">Alle</span>`}</div>
      <dl>
        <dt>Dato</dt><dd><time datetime="${escapeHtml(activity.date)}">${escapeHtml(formatDate(activity.date))}</time></dd>
        <dt>Type</dt><dd>${escapeHtml(activity.type || 'Ikke oppgitt')}</dd>
        <dt>Sted</dt><dd>${escapeHtml(activity.location || 'Ikke oppgitt')}</dd>
        ${activity.url ? `<dt>Lenke</dt><dd><a href="${escapeHtml(activity.url)}" target="_blank" rel="noopener">Mer informasjon</a></dd>` : ''}
      </dl>`;
    details.focus({ preventScroll: true });
    announceHeight();
  }

  function announceHeight() {
    requestAnimationFrame(() => {
      window.parent.postMessage({ type: 'rvv-activities-height', height: document.documentElement.scrollHeight }, '*');
    });
  }

  wheelBtn.addEventListener('click', () => setView('wheel'));
  listBtn.addEventListener('click', () => setView('list'));
  ageFilter.addEventListener('change', applyFilter);
  window.addEventListener('resize', announceHeight);

  fetch(DATA_URL, { cache: 'no-store' })
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(data => {
      allActivities = withIds((data.activities || []).slice().sort((a, b) => a.date.localeCompare(b.date) || a.title.localeCompare(b.title, 'nb')));
      populateFilters(allActivities);
      applyFilter();
      if (allActivities.length) showDetails(allActivities.find(a => a.id === nextActivityId) || allActivities[0]);
    })
    .catch(error => {
      app.setAttribute('aria-busy', 'false');
      status.textContent = 'Kunne ikke laste aktiviteter';
      listContainer.innerHTML = `<div class="empty">Kunne ikke laste activities.json: ${escapeHtml(error.message)}</div>`;
      announceHeight();
    });
})();
</script>
<noscript><p class="wrap">Aktivitetskalenderen krever JavaScript for filtrering og årshjulvisning. Åpne activities.json for rådata.</p></noscript>
</body>
</html>
"""
