"""Standalone public activity calendar page generation (issue #33/#38)."""

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
    --bg: #f7fafc; --surface: #ffffff; --surface-soft: #edf3f8; --surface-strong: #dbe7f1;
    --border: #cfdce8; --text: #102033; --muted: #5b6f84; --accent: #0b66c3; --accent-dark: #07477f;
    --today: #d82148; --next: #b45309; --shadow: 0 18px 45px rgba(15, 23, 42, .10);
    --radius: 18px; --lane-height: 82px; --font: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  }
  * { box-sizing: border-box; }
  html { min-width: 0; overflow-x: hidden; }
  body { margin: 0; min-width: 0; overflow-x: hidden; background: radial-gradient(circle at top left, #dceffd, transparent 28rem), var(--bg); color: var(--text); font-family: var(--font); line-height: 1.5; }
  button, select { font: inherit; }
  .wrap { width: min(1180px, 100%); margin: 0 auto; padding: clamp(16px, 3vw, 32px); }
  header { display: grid; gap: 10px; margin-bottom: 20px; }
  .eyebrow { color: var(--accent-dark); font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h1 { margin: 0; font-size: clamp(28px, 5vw, 48px); letter-spacing: -.04em; line-height: 1.04; }
  .lead { max-width: 800px; margin: 0; color: var(--muted); font-size: clamp(15px, 2vw, 18px); }
  .toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 12px; margin: 22px 0; background: rgba(255,255,255,.82); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); backdrop-filter: blur(12px); }
  .segmented { display: inline-flex; padding: 4px; background: var(--surface-soft); border-radius: 999px; }
  .segmented button, .filter { min-height: 40px; border-radius: 999px; }
  .segmented button { border: 0; padding: 0 16px; color: var(--muted); background: transparent; cursor: pointer; font-weight: 800; }
  .segmented button[aria-pressed="true"] { background: var(--surface); color: var(--accent-dark); box-shadow: 0 6px 16px rgba(15,23,42,.10); }
  .segmented button:focus-visible, .filter:focus-visible, .activity-card:focus-visible, .timeline-item:focus-visible { outline: 3px solid rgba(11,102,195,.35); outline-offset: 2px; }
  label { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); font-size: 14px; font-weight: 800; }
  .filter { padding: 0 14px; border: 1px solid var(--border); background: var(--surface); color: var(--text); min-width: 170px; }
  .status { margin-left: auto; color: var(--muted); font-size: 14px; }
  .panel { background: rgba(255,255,255,.88); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); }
  .content-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 360px); gap: 18px; padding: clamp(12px, 2vw, 22px); }
  .content-view { min-width: 0; }
  .timeline-view, .list-view, .wheel-view { display: none; }
  .view-timeline .timeline-view, .view-list .list-view, .view-wheel .wheel-view { display: block; }
  .details { padding: 18px; align-self: start; position: sticky; top: 12px; }
  .details h2 { margin: 0 0 8px; font-size: 20px; }
  .details dl { display: grid; grid-template-columns: auto 1fr; gap: 8px 12px; margin: 14px 0 0; }
  .details dt { color: var(--muted); font-weight: 800; }
  .details dd { margin: 0; }
  .details a { color: var(--accent-dark); font-weight: 800; }
  .badge-row, .legend { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
  .badge, .type-pill { display: inline-flex; align-items: center; gap: 6px; min-height: 24px; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 850; }
  .badge { color: #fff; }
  .type-pill { border: 1px solid var(--border); background: var(--surface); color: var(--text); }
  .type-cue { width: 12px; height: 12px; display: inline-block; flex: none; background: var(--cue-color); border: 2px solid #fff; box-shadow: 0 0 0 1px rgba(15,23,42,.22); }
  .shape-circle { border-radius: 999px; }
  .shape-square { border-radius: 3px; }
  .shape-diamond { transform: rotate(45deg); border-radius: 2px; }
  .shape-ring { border-radius: 999px; background: transparent; border-color: var(--cue-color); box-shadow: 0 0 0 1px rgba(15,23,42,.20); }
  .shape-pill { width: 16px; border-radius: 999px; }
  .timeline-shell { overflow: hidden; border: 1px solid var(--border); border-radius: calc(var(--radius) - 6px); background: linear-gradient(180deg, #fff, #f6f9fd); }
  .timeline-head { display: flex; justify-content: space-between; gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--border); }
  .timeline-head h2 { margin: 0; font-size: 18px; }
  .next-summary { margin: 0; color: var(--muted); font-size: 14px; }
  .timeline-track { position: relative; min-width: 0; overflow-x: auto; scrollbar-gutter: stable; }
  .timeline-grid { display: grid; grid-template-columns: minmax(92px, 132px) minmax(0, 1fr); min-width: 690px; }
  .corner-cell, .axis-cell { position: sticky; top: 0; z-index: 3; min-height: 46px; background: rgba(246,249,253,.96); border-bottom: 1px solid var(--border); }
  .corner-cell { left: 0; z-index: 4; display: flex; align-items: center; padding: 0 12px; color: var(--muted); font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: .04em; border-right: 1px solid var(--border); }
  .axis-cell { position: relative; }
  .month-tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid rgba(91,111,132,.22); }
  .month-tick span { position: absolute; top: 11px; left: 7px; color: var(--muted); font-size: 12px; font-weight: 850; text-transform: uppercase; }
  .timeline-lane-label { position: sticky; left: 0; z-index: 2; display: flex; align-items: center; min-height: var(--lane-height); padding: 0 12px; border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); background: rgba(255,255,255,.96); font-weight: 900; }
  .timeline-lane { position: relative; min-height: var(--lane-height); border-bottom: 1px solid var(--border); background-image: linear-gradient(90deg, rgba(207,220,232,.42) 1px, transparent 1px); background-size: calc(100% / 12) 100%; }
  .timeline-today { position: absolute; top: 0; bottom: 0; width: 0; border-left: 2px solid var(--today); z-index: 1; }
  .timeline-today span { position: absolute; top: 3px; left: 5px; padding: 1px 6px; border-radius: 999px; background: var(--today); color: #fff; font-size: 11px; font-weight: 900; white-space: nowrap; }
  .timeline-item { position: absolute; left: var(--x); top: calc(10px + (var(--stack) * 20px)); max-width: min(180px, 28vw); min-height: 32px; transform: translateX(-50%); display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border: 1px solid rgba(15,23,42,.14); border-left: 5px solid var(--cue-color); border-radius: 12px; background: #fff; color: var(--text); box-shadow: 0 8px 18px rgba(15,23,42,.12); cursor: pointer; text-align: left; font-size: 12px; font-weight: 850; line-height: 1.2; white-space: normal; z-index: 2; }
  .timeline-item.next { box-shadow: 0 0 0 3px rgba(180,83,9,.22), 0 8px 18px rgba(15,23,42,.12); border-color: var(--next); }
  .timeline-item .label { overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .timeline-empty, .empty { padding: 40px 18px; color: var(--muted); text-align: center; }
  .wheel-shell { min-width: 0; overflow: hidden; border-radius: calc(var(--radius) - 6px); background: linear-gradient(180deg, #fff, #f6f9fd); }
  .wheel { display: block; width: 100%; height: auto; max-height: 650px; }
  .month-label { fill: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
  .month-ring { fill: none; stroke: #d8e1ec; stroke-width: 1; }
  .today-line { stroke: var(--today); stroke-width: 2; stroke-linecap: round; }
  .activity-marker { cursor: pointer; outline: none; }
  .activity-marker circle, .activity-marker rect, .activity-marker polygon { stroke: #fff; stroke-width: 2; filter: drop-shadow(0 3px 5px rgba(15,23,42,.22)); }
  .activity-marker:focus-visible circle, .activity-marker:focus-visible rect, .activity-marker:focus-visible polygon { stroke: #111827; stroke-width: 4; }
  .activity-marker.next circle, .activity-marker.next rect, .activity-marker.next polygon { stroke: var(--next); stroke-width: 4; }
  .month-group { margin-bottom: 20px; }
  .month-group h2 { margin: 0 0 10px; font-size: 18px; }
  .activity-list { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
  .activity-card { width: 100%; text-align: left; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); padding: 14px; cursor: pointer; font: inherit; color: var(--text); }
  .activity-card.next { border-color: var(--next); box-shadow: 0 0 0 3px rgba(180,83,9,.20); }
  .activity-card time { display: block; color: var(--muted); font-size: 13px; font-weight: 800; }
  .activity-card strong { display: block; margin-top: 2px; }
  .activity-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; color: var(--muted); font-size: 13px; font-weight: 750; }
  @media (max-width: 900px) {
    .content-layout { grid-template-columns: 1fr; }
    .details { position: static; }
    .timeline-grid { min-width: 640px; }
  }
  @media (max-width: 760px) {
    .wrap { padding: 14px; }
    .toolbar { align-items: stretch; }
    .status { width: 100%; margin-left: 0; }
    label, .filter, .segmented { width: 100%; }
    .segmented button { flex: 1; padding: 0 10px; }
    .mobile-default .timeline-view, .mobile-default .wheel-view { display: none; }
    .mobile-default .list-view { display: block; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }
  }
</style>
</head>
<body class="view-timeline">
<div class="wrap">
  <header>
    <div class="eyebrow">RVV Hockey</div>
    <h1>Aktivitetskalender</h1>
    <p class="lead">Sesongsløp, liste og årshjul for aktiviteter i Region Viken Vest. Sammenlign aldersgrupper, aktivitetstyper og perioder med høy eller lav aktivitet.</p>
  </header>

  <div class="toolbar" aria-label="Visningsvalg og filtre">
    <div class="segmented" role="group" aria-label="Velg visning">
      <button type="button" id="timelineView" aria-pressed="true">Sesongsløp</button>
      <button type="button" id="listView" aria-pressed="false">Liste</button>
      <button type="button" id="wheelView" aria-pressed="false">Årshjul</button>
    </div>
    <label for="ageFilter">Aldersgruppe
      <select id="ageFilter" class="filter"><option value="">Alle aldersgrupper</option></select>
    </label>
    <label for="typeFilter">Aktivitetstype
      <select id="typeFilter" class="filter"><option value="">Alle typer</option></select>
    </label>
    <div id="activityStatus" class="status" aria-live="polite">Laster aktiviteter…</div>
  </div>

  <main id="app" class="panel" aria-busy="true">
    <div class="content-layout">
      <div class="content-view">
        <section id="timelineContainer" class="timeline-view" aria-labelledby="timelineHeading"></section>
        <section id="listContainer" class="list-view" aria-label="Kronologisk aktivitetsliste"></section>
        <section class="wheel-view" aria-labelledby="wheelHeading">
          <div class="wheel-shell">
            <h2 id="wheelHeading" class="sr-only" style="position:absolute;left:-9999px">Årshjul</h2>
            <svg id="yearWheel" class="wheel" viewBox="0 0 720 720" role="img" aria-label="Aktiviteter plassert etter dato gjennom året"></svg>
          </div>
        </section>
      </div>
      <aside id="details" class="details" tabindex="-1" aria-live="polite">
        <h2>Velg en aktivitet</h2>
        <p>Trykk på en aktivitet i sesongsløpet, årshjulet eller listen for detaljer.</p>
      </aside>
    </div>
  </main>
</div>
<script>
(function() {
  const DATA_URL = '../activities.json';
  const MONTHS = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember'];
  const MONTH_SHORT = ['jan','feb','mar','apr','mai','jun','jul','aug','sep','okt','nov','des'];
  const COLORS = ['#0b66c3','#7c3aed','#047857','#d82148','#c2410c','#0e7490','#be123c','#4f46e5','#15803d','#9333ea'];
  const SHAPES = ['circle','square','diamond','ring','pill'];
  const colorByType = new Map();
  const shapeByType = new Map();
  let allActivities = [];
  let filteredActivities = [];
  let nextActivityId = null;
  let timelineYear = new Date().getFullYear();

  const body = document.body;
  const app = document.getElementById('app');
  const svg = document.getElementById('yearWheel');
  const details = document.getElementById('details');
  const timelineContainer = document.getElementById('timelineContainer');
  const listContainer = document.getElementById('listContainer');
  const ageFilter = document.getElementById('ageFilter');
  const typeFilter = document.getElementById('typeFilter');
  const status = document.getElementById('activityStatus');
  const timelineBtn = document.getElementById('timelineView');
  const listBtn = document.getElementById('listView');
  const wheelBtn = document.getElementById('wheelView');

  if (window.matchMedia('(max-width: 760px)').matches) {
    body.classList.add('mobile-default', 'view-list');
    body.classList.remove('view-timeline');
    timelineBtn.setAttribute('aria-pressed', 'false');
    listBtn.setAttribute('aria-pressed', 'true');
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  }

  function formatDate(iso) {
    return new Intl.DateTimeFormat('nb-NO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(iso + 'T00:00:00'));
  }

  function shortDate(iso) {
    return new Intl.DateTimeFormat('nb-NO', { day: 'numeric', month: 'short' }).format(new Date(iso + 'T00:00:00'));
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

  function dateToPercent(iso, year) {
    const date = new Date(iso + 'T00:00:00');
    const targetYear = year || date.getFullYear();
    return ((dayOfYear(date) - 1) / Math.max(1, daysInYear(targetYear) - 1)) * 100;
  }

  function daysBetween(a, b) {
    return Math.abs((new Date(a + 'T00:00:00') - new Date(b + 'T00:00:00')) / 86400000);
  }

  function colorFor(type) {
    const key = normalizeType(type);
    if (!colorByType.has(key)) colorByType.set(key, COLORS[colorByType.size % COLORS.length]);
    return colorByType.get(key);
  }

  function shapeFor(type) {
    const key = normalizeType(type);
    if (!shapeByType.has(key)) shapeByType.set(key, SHAPES[shapeByType.size % SHAPES.length]);
    return shapeByType.get(key);
  }

  function normalizeType(type) {
    return String(type || 'annet').trim() || 'annet';
  }

  function cueHtml(type) {
    const key = normalizeType(type);
    return `<span class="type-cue shape-${shapeFor(key)}" style="--cue-color:${colorFor(key)}" aria-hidden="true"></span>`;
  }

  function withIds(activities) {
    return activities.map((activity, index) => ({ ...activity, id: `activity-${index}` }));
  }

  function activityGroups(activity) {
    return (activity.age_groups && activity.age_groups.length) ? activity.age_groups : ['Alle'];
  }

  function uniqueAgeGroups(activities) {
    return Array.from(new Set(activities.flatMap(activityGroups))).sort((a, b) => a.localeCompare(b, 'nb', { numeric: true }));
  }

  function uniqueTypes(activities) {
    return Array.from(new Set(activities.map(a => normalizeType(a.type)))).sort((a, b) => a.localeCompare(b, 'nb', { numeric: true }));
  }

  function setView(view) {
    body.classList.toggle('view-timeline', view === 'timeline');
    body.classList.toggle('view-list', view === 'list');
    body.classList.toggle('view-wheel', view === 'wheel');
    timelineBtn.setAttribute('aria-pressed', String(view === 'timeline'));
    listBtn.setAttribute('aria-pressed', String(view === 'list'));
    wheelBtn.setAttribute('aria-pressed', String(view === 'wheel'));
    announceHeight();
  }

  function populateFilters(activities) {
    const groups = uniqueAgeGroups(activities);
    const types = uniqueTypes(activities);
    ageFilter.innerHTML = '<option value="">Alle aldersgrupper</option>' + groups.map(group => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`).join('');
    typeFilter.innerHTML = '<option value="">Alle typer</option>' + types.map(type => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join('');
  }

  function applyFilter() {
    const selectedAge = ageFilter.value;
    const selectedType = typeFilter.value;
    filteredActivities = allActivities.filter(activity => {
      const ageMatch = selectedAge ? activityGroups(activity).includes(selectedAge) : true;
      const typeMatch = selectedType ? normalizeType(activity.type) === selectedType : true;
      return ageMatch && typeMatch;
    });
    render();
  }

  function findNextActivity(activities) {
    const todayIso = new Date().toISOString().slice(0, 10);
    const upcoming = activities.filter(a => a.date >= todayIso).sort((a, b) => a.date.localeCompare(b.date));
    return upcoming.length ? upcoming[0].id : null;
  }

  function currentYearFrom(data) {
    if (data && data.year) return Number(data.year);
    const first = data && data.activities && data.activities[0];
    if (first && first.date) return Number(first.date.slice(0, 4));
    return new Date().getFullYear();
  }

  function render() {
    nextActivityId = findNextActivity(allActivities);
    status.textContent = filteredActivities.length === 1 ? 'Viser 1 aktivitet' : `Viser ${filteredActivities.length} aktiviteter`;
    renderTimeline();
    renderWheel();
    renderList();
    app.setAttribute('aria-busy', 'false');
    announceHeight();
  }

  function renderLegend(types) {
    if (!types.length) return '';
    return `<div class="legend" aria-label="Forklaring av aktivitetstyper">${types.map(type => `<span class="type-pill">${cueHtml(type)}${escapeHtml(type)}</span>`).join('')}</div>`;
  }

  function nextSummary() {
    const next = allActivities.find(a => a.id === nextActivityId);
    if (!next) return '<p class="next-summary">Neste aktivitet: ingen kommende aktivitet i datasettet.</p>';
    return `<p class="next-summary"><strong>Neste aktivitet:</strong> ${escapeHtml(shortDate(next.date))} · ${escapeHtml(next.title)}</p>`;
  }

  function buildLaneEntries(activities, lanes) {
    const entries = [];
    activities.forEach(activity => {
      activityGroups(activity).forEach(group => {
        if (!lanes.includes(group)) return;
        entries.push({ activity, group, x: dateToPercent(activity.date, timelineYear), stack: 0 });
      });
    });
    lanes.forEach(group => {
      const laneEntries = entries.filter(entry => entry.group === group).sort((a, b) => a.activity.date.localeCompare(b.activity.date) || a.activity.title.localeCompare(b.activity.title, 'nb'));
      laneEntries.forEach((entry, index) => {
        let stack = 0;
        for (let i = index - 1; i >= 0; i--) {
          if (daysBetween(entry.activity.date, laneEntries[i].activity.date) > 3) break;
          stack = Math.max(stack, laneEntries[i].stack + 1);
        }
        entry.stack = stack % 3;
      });
    });
    return entries;
  }

  function renderTimeline() {
    const selectedAge = ageFilter.value;
    const lanes = selectedAge ? [selectedAge] : uniqueAgeGroups(allActivities);
    const activeTypes = uniqueTypes(filteredActivities.length ? filteredActivities : allActivities);
    if (!allActivities.length) {
      timelineContainer.innerHTML = '<div class="timeline-empty">Ingen aktiviteter er publisert ennå.</div>';
      return;
    }
    const entries = buildLaneEntries(filteredActivities, lanes);
    const monthTicks = MONTH_SHORT.map((month, index) => {
      const left = dateToPercent(`${timelineYear}-${String(index + 1).padStart(2, '0')}-01`, timelineYear);
      return `<div class="month-tick" style="left:${left.toFixed(4)}%"><span>${month}</span></div>`;
    }).join('');
    const today = new Date();
    const todayLine = today.getFullYear() === timelineYear ? `<div class="timeline-today" style="left:${dateToPercent(today.toISOString().slice(0, 10), timelineYear).toFixed(4)}%"><span>I dag</span></div>` : '';
    const laneRows = lanes.map(group => {
      const laneItems = entries.filter(entry => entry.group === group).map(entry => {
        const activity = entry.activity;
        const type = normalizeType(activity.type);
        return `<button type="button" class="timeline-item${activity.id === nextActivityId ? ' next' : ''}" data-id="${activity.id}" style="--x:${entry.x.toFixed(4)}%;--stack:${entry.stack};--cue-color:${colorFor(type)}" aria-label="${escapeHtml(formatDate(activity.date))}: ${escapeHtml(activity.title)} (${escapeHtml(group)}, ${escapeHtml(type)})">${cueHtml(type)}<span class="label">${escapeHtml(shortDate(activity.date))} · ${escapeHtml(activity.title)}</span></button>`;
      }).join('');
      return `<div class="timeline-lane-label">${escapeHtml(group)}</div><div class="timeline-lane">${todayLine}${laneItems || '<div class="timeline-empty">Ingen aktiviteter i valgt filter.</div>'}</div>`;
    }).join('');

    timelineContainer.innerHTML = `
      <div class="timeline-shell">
        <div class="timeline-head">
          <div><h2 id="timelineHeading">Sesongsløp ${timelineYear}</h2>${renderLegend(activeTypes)}</div>
          ${nextSummary()}
        </div>
        <div class="timeline-track" role="region" aria-label="Sesongsløp med aldersgrupper som rader og dato gjennom året som vannrett akse" tabindex="0">
          <div class="timeline-grid">
            <div class="corner-cell">Aldersgruppe</div>
            <div class="axis-cell">${monthTicks}</div>
            ${laneRows}
          </div>
        </div>
      </div>`;
    timelineContainer.querySelectorAll('.timeline-item').forEach(item => {
      item.addEventListener('click', () => showDetails(allActivities.find(a => a.id === item.dataset.id)));
    });
  }

  function renderWheelShape(g, activity, size) {
    const type = normalizeType(activity.type);
    const shape = shapeFor(type);
    const color = colorFor(type);
    if (shape === 'square' || shape === 'pill') {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', -size); rect.setAttribute('y', -size * .75); rect.setAttribute('width', size * 2); rect.setAttribute('height', size * 1.5);
      rect.setAttribute('rx', shape === 'pill' ? size : 3); rect.setAttribute('fill', color); g.appendChild(rect); return;
    }
    if (shape === 'diamond') {
      const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      polygon.setAttribute('points', `0,${-size} ${size},0 0,${size} ${-size},0`); polygon.setAttribute('fill', color); g.appendChild(polygon); return;
    }
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('r', size); circle.setAttribute('fill', shape === 'ring' ? '#fff' : color);
    if (shape === 'ring') circle.setAttribute('stroke', color);
    g.appendChild(circle);
  }

  function renderWheel() {
    const width = 720, cx = 360, cy = 360, radius = 255;
    const year = timelineYear;
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
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title'); title.textContent = `${formatDate(activity.date)} — ${activity.title}`;
      g.appendChild(title); renderWheelShape(g, activity, activity.id === nextActivityId ? 10 : 8); svg.appendChild(g);
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
      const cards = activities.map(activity => {
        const type = normalizeType(activity.type);
        return `<li><button type="button" class="activity-card${activity.id === nextActivityId ? ' next' : ''}" data-id="${activity.id}" aria-label="${escapeHtml(formatDate(activity.date))}: ${escapeHtml(activity.title)}">
          <time datetime="${escapeHtml(activity.date)}">${escapeHtml(formatDate(activity.date))}</time>
          <strong>${escapeHtml(activity.title)}</strong>
          <span>${escapeHtml(activity.location || 'Sted ikke oppgitt')}</span>
          <span class="activity-meta">${cueHtml(type)}<span>${escapeHtml(type)}</span><span>${escapeHtml(activityGroups(activity).join(', '))}</span></span>
        </button></li>`;
      }).join('');
      return `<section class="month-group"><h2>${MONTHS[monthIndex]} ${year}</h2><ul class="activity-list">${cards}</ul></section>`;
    }).join('');
    listContainer.querySelectorAll('.activity-card').forEach(card => {
      card.addEventListener('click', () => showDetails(allActivities.find(a => a.id === card.dataset.id)));
    });
  }

  function showDetails(activity) {
    if (!activity) return;
    const type = normalizeType(activity.type);
    const badges = activityGroups(activity).map(group => `<span class="badge" style="background:${colorFor(type)}">${escapeHtml(group)}</span>`).join('');
    details.innerHTML = `
      <h2>${escapeHtml(activity.title)}</h2>
      <p>${activity.description ? escapeHtml(activity.description) : 'Ingen ekstra beskrivelse er oppgitt.'}</p>
      <div class="badge-row">${badges}</div>
      <dl>
        <dt>Dato</dt><dd><time datetime="${escapeHtml(activity.date)}">${escapeHtml(formatDate(activity.date))}</time></dd>
        <dt>Type</dt><dd>${cueHtml(type)} ${escapeHtml(type)}</dd>
        <dt>Aldersgruppe</dt><dd>${escapeHtml(activityGroups(activity).join(', '))}</dd>
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

  timelineBtn.addEventListener('click', () => setView('timeline'));
  listBtn.addEventListener('click', () => setView('list'));
  wheelBtn.addEventListener('click', () => setView('wheel'));
  ageFilter.addEventListener('change', applyFilter);
  typeFilter.addEventListener('change', applyFilter);
  window.addEventListener('resize', announceHeight);

  fetch(DATA_URL, { cache: 'no-store' })
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(data => {
      timelineYear = currentYearFrom(data);
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
<noscript><p class="wrap">Aktivitetskalenderen krever JavaScript for filtrering og sesongsløpvisning. Åpne activities.json for rådata.</p></noscript>
</body>
</html>
"""
