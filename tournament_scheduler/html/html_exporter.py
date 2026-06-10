"""Interactive HTML overview for the season plan.

Reads a :class:`~tournament_scheduler.models.SeasonPlan` and generates a
standalone, interactive HTML page showing all tournaments, filtering by
age group / arena / club / search, and expandable match tables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tournament_scheduler.club_distances import furthest_traveling_team
from ..models import SeasonPlan

# ---------------------------------------------------------------------------
# Template — uses $MARKER$ placeholders replaced by .replace()
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sesongplan $SEASON_LABEL$ — RVV Hockey</title>
<style>
  /* Navbar */
  .navbar { display: flex; align-items: center; gap: 4px;
             background: #1a1a2e; color: #fff; padding: 8px 16px;
             border-bottom: 1px solid #333; }
  .navbar .brand { font-weight: 700; font-size: 0.9em; margin-right: 20px; color: #38bdf8; }
  .navbar a { color: #94a3b8; text-decoration: none; padding: 4px 12px;
               border-radius: 4px; font-size: 0.8em; }
  .navbar a:hover { background: rgba(255,255,255,0.1); color: #fff; }
  .navbar a.active { background: #38bdf8; color: #0f172a; font-weight: 600; }
  .navbar .meta-nav { margin-left: auto; font-size: 0.75em; color: #666; }
  :root {
    --ice: #0f172a;
    --ice-light: #1e293b;
    --ice-surface: #334155;
    --ice-border: #475569;
    --text: #f1f5f9;
    --text-dim: #94a3b8;
    --accent: #38bdf8;
    --accent-dim: #0284c7;
    --accent-glow: rgba(56, 189, 248, .15);
    --amber: #fbbf24;
    --emerald: #34d399;
    --rose: #fb7185;
    --radius: 12px;
    --radius-sm: 8px;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: var(--font);
    background: var(--ice);
    color: var(--text);
    line-height: 1.5;
    min-height: 100dvh;
  }
  .app { max-width: 1400px; margin: 0 auto; padding: 24px 20px 64px; }

  /* Header */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    padding: 20px 0 32px;
    border-bottom: 1px solid var(--ice-surface);
    margin-bottom: 32px;
  }
  .header-left { display: flex; align-items: center; gap: 16px; }
  .logo-icon {
    width: 44px; height: 44px;
    background: linear-gradient(135deg, var(--accent), var(--accent-dim));
    border-radius: var(--radius);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 18px; color: #fff;
    flex-shrink: 0;
  }
  .header h1 { font-size: 24px; font-weight: 700; letter-spacing: -.02em; }
  .header h1 span { color: var(--accent); }
  .header-sub { font-size: 14px; color: var(--text-dim); margin-top: 2px; }
  .header-right { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .stat-badge {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 14px;
    background: var(--ice-light);
    border-radius: 999px;
    font-size: 13px;
    color: var(--text-dim);
    border: 1px solid var(--ice-surface);
    white-space: nowrap;
  }
  .stat-badge strong { color: var(--text); font-weight: 600; }
  .stat-badge svg { width: 16px; height: 16px; flex-shrink: 0; }

  /* Filters */
  .filters {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 32px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--ice-surface);
  }
  .filter-group { display: flex; flex-direction: column; gap: 6px; }
  .filter-group label {
    font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .08em;
    color: var(--text-dim);
  }
  .filter-select, .filter-input {
    padding: 8px 14px;
    background: var(--ice-light);
    border: 1px solid var(--ice-surface);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 14px;
    outline: none;
    transition: border-color .2s, box-shadow .2s;
    appearance: none;
    -webkit-appearance: none;
    cursor: pointer;
    min-width: 140px;
  }
  .filter-select:focus, .filter-input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-glow);
  }
  .filter-input { cursor: text; min-width: 180px; }
  .filter-input::placeholder { color: var(--text-dim); }
  .filter-clear {
    padding: 8px 16px;
    background: transparent;
    border: 1px solid var(--ice-surface);
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    font-size: 13px;
    cursor: pointer;
    transition: all .2s;
    align-self: flex-end;
  }
  .filter-clear:hover { background: var(--ice-surface); color: var(--text); }

  /* Count bar */
  .count-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 16px;
    background: var(--ice-light);
    border: 1px solid var(--ice-surface);
    border-radius: var(--radius);
    margin-bottom: 24px;
    font-size: 14px;
    color: var(--text-dim);
  }
  .count-bar strong { color: var(--text); }

  /* Timeline */
  .timeline {
    position: relative;
    padding-left: 32px;
  }
  .timeline::before {
    content: '';
    position: absolute;
    left: 11px;
    top: 8px;
    bottom: 8px;
    width: 2px;
    background: linear-gradient(to bottom, var(--accent), var(--ice-surface));
    opacity: .5;
  }

  .tournament-card {
    position: relative;
    margin-bottom: 20px;
    background: var(--ice-light);
    border: 1px solid var(--ice-surface);
    border-radius: var(--radius);
    padding: 20px 24px;
    cursor: pointer;
    transition: all .25s cubic-bezier(.16,1,.3,1);
    user-select: none;
  }
  .tournament-card:hover {
    border-color: var(--accent-dim);
    box-shadow: 0 0 0 1px var(--accent-glow), 0 8px 32px rgba(0,0,0,.3);
    transform: translateY(-2px);
  }
  .tournament-card.hidden { display: none; }
  .tournament-card::before {
    content: '';
    position: absolute;
    left: -25px;
    top: 26px;
    width: 12px;
    height: 12px;
    background: var(--accent);
    border: 3px solid var(--ice);
    border-radius: 50%;
    z-index: 1;
  }
  .tournament-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }
  .tournament-date {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 56px;
    padding: 8px 12px;
    background: var(--ice);
    border-radius: var(--radius-sm);
    border: 1px solid var(--ice-surface);
  }
  .tournament-date .day { font-size: 22px; font-weight: 700; line-height: 1; }
  .tournament-date .month { font-size: 11px; text-transform: uppercase; color: var(--text-dim); letter-spacing: .06em; margin-top: 2px; }
  .tournament-date .weekday { font-size: 10px; color: var(--accent); text-transform: uppercase; letter-spacing: .1em; margin-top: 4px; }
  .tournament-info { flex: 1; min-width: 0; }
  .tournament-info h3 { font-size: 17px; font-weight: 600; margin-bottom: 4px; }
  .tournament-info h3 span { color: var(--accent); }
  .tournament-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }

  .tag {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 500;
    background: var(--ice);
    border: 1px solid var(--ice-surface);
    color: var(--text-dim);
  }
  .tag--age { background: rgba(56,189,248,.1); border-color: rgba(56,189,248,.2); color: var(--accent); }
  .tag--arena { background: rgba(251,191,36,.08); border-color: rgba(251,191,36,.2); color: var(--amber); }
  .tag--teams { background: rgba(52,211,153,.08); border-color: rgba(52,211,153,.2); color: var(--emerald); }
  .tag--travel { background: rgba(251,191,36,.08); border-color: rgba(251,191,36,.2); color: var(--amber); }
  .tag svg { width: 14px; height: 14px; flex-shrink: 0; }

  .tournament-arrow {
    color: var(--text-dim);
    transition: transform .3s cubic-bezier(.16,1,.3,1);
    flex-shrink: 0;
    margin-top: 4px;
  }
  .tournament-arrow svg { width: 20px; height: 20px; display: block; }
  .tournament-card.expanded .tournament-arrow { transform: rotate(180deg); }

  /* Match table */
  .matches {
    max-height: 0;
    overflow: hidden;
    transition: max-height .5s cubic-bezier(.16,1,.3,1), opacity .3s ease;
    opacity: 0;
  }
  .tournament-card.expanded .matches {
    max-height: 2000px;
    opacity: 1;
  }
  .matches-inner {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--ice-surface);
  }
  .matches-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .matches-header h4 { font-size: 13px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: .06em; }
  .matches-header .count { font-size: 12px; color: var(--text-dim); }
  .match-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 6px;
  }
  .match-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: var(--ice);
    border-radius: var(--radius-sm);
    font-size: 13px;
    color: var(--text-dim);
  }
  .match-row .vs { color: var(--ice-border); font-size: 10px; font-weight: 600; }
  .match-row .slot {
    margin-left: auto;
    padding: 1px 8px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 600;
    background: rgba(56,189,248,.1);
    color: var(--accent);
    white-space: nowrap;
  }

  /* Score quality */
  .score-bar {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    padding: 16px 20px;
    margin-bottom: 24px;
    background: var(--ice-light);
    border: 1px solid var(--ice-surface);
    border-radius: var(--radius);
  }
  .score-item { font-size: 13px; color: var(--text-dim); }
  .score-item strong { color: var(--text); }
  .score-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 4px;
  }

  .no-results {
    text-align: center;
    padding: 64px 24px;
    color: var(--text-dim);
  }
  .no-results svg { width: 48px; height: 48px; margin-bottom: 16px; opacity: .4; }
  .no-results p { font-size: 15px; }

  @media (max-width: 768px) {
    .app { padding: 16px 12px 48px; }
    .header { flex-direction: column; align-items: flex-start; }
    .header-right { width: 100%; }
    .filters { flex-direction: column; }
    .filter-select, .filter-input { min-width: 100%; }
    .timeline { padding-left: 24px; }
    .tournament-card { padding: 16px; }
    .tournament-card::before { left: -18px; width: 10px; height: 10px; }
    .timeline::before { left: 8px; }
    .tournament-card-header { flex-wrap: wrap; }
    .match-grid { grid-template-columns: 1fr; }
    .tournament-date { min-width: 48px; padding: 6px 10px; }
    .tournament-date .day { font-size: 18px; }
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>
<div class="navbar">
  <span class="brand">🏒 RVV Miniputt</span>
  <a href="calendars.html">🗓️ Skrapede kalendere</a>
  <a href="season_plan.html" class="active">📋 Sesongplan</a>
  <span class="meta-nav">$SCRAPE_META$</span>
</div>
<div class="app" id="app">
  <header class="header">
    <div class="header-left">
      <div class="logo-icon">RVV</div>
      <div>
        <h1>Sesongplan <span>$SEASON_LABEL$</span></h1>
        <div class="header-sub">RVV Hockey &mdash; $AGE_GROUPS$</div>
      </div>
    </div>
    <div class="header-right">
      <div class="stat-badge">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <span><strong id="totalTournaments">$TOURNAMENT_COUNT$</strong> turneringer</span>
      </div>
      <div class="stat-badge">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 8l-4 8-4-4"/></svg>
        <span><strong id="totalMatches">$GAME_COUNT$</strong> kamper</span>
      </div>
      <div class="stat-badge">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <span><strong id="totalTeams">$UNIQUE_TEAMS$</strong> lag</span>
      </div>
    </div>
  </header>

  <!-- Scores -->
  <div class="score-bar">
    <span class="score-item">
      <span class="score-dot" style="background:var(--accent)"></span>
      Spredning: <strong>$DIVERSITY_SCORE$%</strong>
    </span>
    <span class="score-item">
      <span class="score-dot" style="background:var(--emerald)"></span>
      Manedsbalanse: <strong>$MONTH_BALANCE_SCORE$%</strong>
    </span>
    <span class="score-item">
      <span class="score-dot" style="background:var(--amber)"></span>
      Nye matchups: <strong>$PAIRWISE_SCORE$%</strong>
    </span>
    <span class="score-item">
      <span class="score-dot" style="background:var(--rose)"></span>
      Kamper per lag: <strong>$GAME_COUNT_SPREAD$</strong>
    </span>
  </div>

  <!-- Team game counts table -->
  <details class="team-stats" id="teamStats" style="margin-bottom:24px">
    <summary style="cursor:pointer;padding:12px 16px;background:var(--ice-light);border:1px solid var(--ice-surface);border-radius:var(--radius);font-size:14px;color:var(--accent);font-weight:600;user-select:none">
      🏒 Kamper per lag ($TEAM_COUNT$ lag) — klikk for å vise
    </summary>
    <div style="margin-top:8px;overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:2px solid var(--ice-surface)">
            <th style="text-align:left;padding:8px 12px;color:var(--text-dim);font-weight:600">Lag</th>
            <th style="text-align:right;padding:8px 12px;color:var(--text-dim);font-weight:600">Kamper</th>
            <th style="text-align:left;padding:8px 12px;color:var(--text-dim);font-weight:600">Siste kamp</th>
          </tr>
        </thead>
        <tbody id="teamGameCountsBody">
        </tbody>
      </table>
    </div>
  </details>

  <!-- Filters -->
  <div class="filters">
    <div class="filter-group">
      <label>Klassetrinn</label>
      <select class="filter-select" id="filterAge">
        <option value="">Alle ($AGE_GROUPS$)</option>
        <option value="U10">U10</option>
        <option value="U11">U11</option>
        $EXTRA_AGE_OPTIONS$
      </select>
    </div>
    <div class="filter-group">
      <label>Arena</label>
      <select class="filter-select" id="filterArena">
        <option value="">Alle arenaer</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Klubb</label>
      <select class="filter-select" id="filterClub">
        <option value="">Alle klubber</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Sok</label>
      <input class="filter-input" id="filterSearch" type="text" placeholder="Sok i turneringer..." autocomplete="off">
    </div>
    <button class="filter-clear" id="filterClear">Nullstill filter</button>
  </div>

  <!-- Count bar -->
  <div class="count-bar">
    <span>Viser <strong id="visibleCount">0</strong> av <strong id="totalCount">$TOURNAMENT_COUNT$</strong> turneringer</span>
    <span id="monthRange" style="color:var(--accent);font-weight:500;"></span>
  </div>

  <!-- Timeline -->
  <div class="timeline" id="timeline"></div>
</div>

<script>
// Data embedded as JSON
const TOURNAMENTS = $TOURNAMENTS_JSON$;
const TEAM_GAME_COUNTS = $TEAM_GAME_COUNTS_JSON$;

// Helpers
const MONTHS = ["jan","feb","mar","apr","mai","jun","jul","aug","sep","okt","nov","des"];
const WEEKDAYS = ["son","man","tir","ons","tor","fre","lor"];

function parseDate(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function formatDateInfo(dateStr) {
  const d = parseDate(dateStr);
  return { day: d.getDate(), month: MONTHS[d.getMonth()], weekday: WEEKDAYS[d.getDay()] };
}

function slotLabel(n) {
  const labels = ["Bane 1", "Bane 2", "Bane 3", "Bane 4"];
  return n >= 0 && n < labels.length ? labels[n] : 'Bane ' + (n + 1);
}

function getClubFromTeam(team) {
  const clubs = ["Jar","Frisk Asker","Sandefjord","Jutul","Holmen","Skien","Ringerike","Kongsberg","Tonsberg"];
  for (const c of clubs) {
    if (team === c || team.startsWith(c + ' ')) return c;
  }
  return team.split(' ')[0];
}

// Populate filter selects
(function() {
  const arenas = [...new Set(TOURNAMENTS.map(t => t.a))].sort();
  const clubs = new Set();
  TOURNAMENTS.forEach(t => {
    clubs.add(t.h);
    t.m.forEach(([h, a]) => { clubs.add(getClubFromTeam(h)); clubs.add(getClubFromTeam(a)); });
  });
  const arenaSel = document.getElementById('filterArena');
  arenas.forEach(a => { const o = document.createElement('option'); o.value = a; o.textContent = a; arenaSel.appendChild(o); });
  const clubSel = document.getElementById('filterClub');
  [...clubs].sort().forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; clubSel.appendChild(o); });
})();

// Render team game counts table
(function() {
  const body = document.getElementById('teamGameCountsBody');
  if (!body) return;
  const sorted = Object.entries(TEAM_GAME_COUNTS).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  sorted.forEach(([label, count]) => {
    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid var(--ice-surface)';
    const tdLabel = document.createElement('td');
    tdLabel.style.padding = '6px 12px';
    tdLabel.textContent = label;
    const tdCount = document.createElement('td');
    tdCount.style.padding = '6px 12px';
    tdCount.style.textAlign = 'right';
    tdCount.textContent = count;
    const tdLast = document.createElement('td');
    tdLast.style.padding = '6px 12px';
    tdLast.style.color = 'var(--text-dim)';
    // Find last tournament date for this team
    let lastDate = '';
    for (const t of TOURNAMENTS) {
      if (t.m.some(([h, a]) => h === label || a === label)) {
        lastDate = t.d;
      }
    }
    tdLast.textContent = lastDate || '-';
    tr.appendChild(tdLabel);
    tr.appendChild(tdCount);
    tr.appendChild(tdLast);
    body.appendChild(tr);
  });
})();

function buildMatchHTML(matches) {
  return matches.map(([home, away, slot]) =>
    '<div class="match-row"><span>' + home + '</span><span class="vs">vs</span><span>' + away +
    '</span><span class="slot">' + slotLabel(slot) + '</span></div>'
  ).join('');
}

function render() {
  const age = document.getElementById('filterAge').value;
  const arena = document.getElementById('filterArena').value;
  const club = document.getElementById('filterClub').value;
  const search = document.getElementById('filterSearch').value.toLowerCase().trim();
  const timeline = document.getElementById('timeline');

  let html = '';
  let visible = 0;

  for (const t of TOURNAMENTS) {
    if (age && t.g !== age) continue;
    if (arena && t.a !== arena) continue;
    if (club && t.h !== club) {
      const hasClub = t.m.some(([h, a]) => getClubFromTeam(h) === club || getClubFromTeam(a) === club);
      if (!hasClub) continue;
    }
    if (search) {
      const haystack = (t.a + ' ' + t.h + ' ' + t.g + ' ' + t.m.map(m => m[0] + ' ' + m[1]).join(' ')).toLowerCase();
      if (!haystack.includes(search)) continue;
    }

    visible++;
    const di = formatDateInfo(t.d);
    html += '<div class="tournament-card" onclick="this.classList.toggle(\'expanded\')">' +
      '<div class="tournament-card-header">' +
        '<div class="tournament-date"><div class="day">' + di.day + '</div><div class="month">' + di.month + '</div><div class="weekday">' + di.weekday + '</div></div>' +
        '<div class="tournament-info"><h3>' + t.h + ' <span>&middot;</span> ' + t.a + '</h3>' +
          '<div class="tournament-meta">' +
            '<span class="tag tag--age"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>' + t.g + '</span>' +
            '<span class="tag tag--arena"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>' + t.a + '</span>' +
            '<span class="tag tag--teams"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>' + t.m.length + ' kamper</span>' +
            (t.tr ? '<span class="tag tag--travel">' + t.tr + '</span>' : '') +
          '</div></div>' +
        '<div class="tournament-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg></div>' +
      '</div>' +
      '<div class="matches"><div class="matches-inner">' +
        '<div class="matches-header"><h4>Kamper</h4><span class="count">' + t.m.length + ' stk</span></div>' +
        '<div class="match-grid">' + buildMatchHTML(t.m) + '</div>' +
      '</div></div></div>';
  }

  document.getElementById('totalTournaments').textContent = TOURNAMENTS.length;
  document.getElementById('visibleCount').textContent = visible;
  document.getElementById('totalCount').textContent = TOURNAMENTS.length;

  if (TOURNAMENTS.length) {
    const first = parseDate(TOURNAMENTS[0].d);
    const last = parseDate(TOURNAMENTS[TOURNAMENTS.length - 1].d);
    document.getElementById('monthRange').textContent = MONTHS[first.getMonth()] + ' ' + first.getFullYear() + ' ' + MONTHS[last.getMonth()] + ' ' + last.getFullYear();
  }

  timeline.innerHTML = html ||
    '<div class="no-results"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><p>Ingen turneringer matcher filteret</p></div>';
}

document.getElementById('filterAge').addEventListener('change', render);
document.getElementById('filterArena').addEventListener('change', render);
document.getElementById('filterClub').addEventListener('change', render);
document.getElementById('filterSearch').addEventListener('input', render);
document.getElementById('filterClear').addEventListener('click', function() {
  document.getElementById('filterAge').value = '';
  document.getElementById('filterArena').value = '';
  document.getElementById('filterClub').value = '';
  document.getElementById('filterSearch').value = '';
  render();
});

render();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class HtmlExporter:
    """Generates a standalone interactive HTML overview of a :class:`SeasonPlan`."""

    def export(self, plan: SeasonPlan, path: str | os.PathLike[str], meta: dict[str, Any] | None = None) -> str:
        """Write an interactive HTML overview to *path*, return the path.

        Parameters
        ----------
        plan:
            The season plan to export.
        path:
            Output file path.
        meta:
            Optional metadata dict with ``total_events``, ``source_count``,
            ``updated_at`` etc. from the scraped data cache. Shown in navbar.
        """
        tournaments_json = self._plan_to_json(plan)

        # Count unique teams
        all_teams: set[str] = set()
        for t in plan.tournaments:
            for g in t.games:
                all_teams.add(g.home.label)
                all_teams.add(g.away.label)

        # Build team game counts JSON for HTML template
        team_game_counts: dict[str, int] = {}
        for t in plan.tournaments:
            for g in t.games:
                for team_label in (g.home.label, g.away.label):
                    team_game_counts[team_label] = team_game_counts.get(team_label, 0) + 1
        team_game_counts_json = json.dumps(team_game_counts, ensure_ascii=False)

        season_label = _season_label(plan)
        age_groups = sorted({t.age_group for t in plan.tournaments})

        extra_age_options = ""
        for ag in sorted({t.age_group for t in plan.tournaments}):
            if ag not in ("U10", "U11"):
                extra_age_options += f'<option value="{ag}">{ag}</option>\n'

        # Scrape metadata for navbar
        if meta:
            ev = meta.get("total_events", 0)
            src = meta.get("source_count", 0)
            ts = meta.get("updated_at", "")
            age = ""
            if ts:
                try:
                    from datetime import datetime as _dt
                    delta = _dt.now() - _dt.fromisoformat(ts)
                    if delta.total_seconds() < 60:
                        age = f"{int(delta.total_seconds())}s siden"
                    elif delta.total_seconds() < 3600:
                        age = f"{int(delta.total_seconds() // 60)}m siden"
                    elif delta.days < 1:
                        age = f"{int(delta.total_seconds() // 3600)}t siden"
                    else:
                        age = f"{delta.days}d siden"
                except Exception:
                    pass
            scrape_meta = f"🏒 {src} kilder · 📊 {ev} hendelser · 🕐 {age}" if age else f"🏒 {src} kilder · 📊 {ev} hendelser"
        else:
            scrape_meta = ""

        replacements = {
            "$SEASON_LABEL$": season_label,
            "$SCRAPE_META$": scrape_meta,
            "$AGE_GROUPS$": " + ".join(age_groups),
            "$TOURNAMENT_COUNT$": str(len(plan.tournaments)),
            "$GAME_COUNT$": str(sum(len(t.games) for t in plan.tournaments)),
            "$UNIQUE_TEAMS$": str(len(all_teams)),
            "$TEAM_COUNT$": str(len(team_game_counts)),
            "$GAME_COUNT_SPREAD$": (
                f"{max(team_game_counts.values()) - min(team_game_counts.values())} spread"
                if team_game_counts else "-"
            ),
            "$TEAM_GAME_COUNTS_JSON$": team_game_counts_json,
            "$DIVERSITY_SCORE$": str(int((plan.diversity_score or 0) * 100)),
            "$MONTH_BALANCE_SCORE$": str(int((plan.month_balance_score or 0) * 100)),
            "$PAIRWISE_SCORE$": str(int((plan.pairwise_matchup_score or 0) * 100)),
            "$EXTRA_AGE_OPTIONS$": extra_age_options,
            "$TOURNAMENTS_JSON$": tournaments_json,
        }

        html = _HTML_TEMPLATE
        for marker, value in replacements.items():
            html = html.replace(marker, value)

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        return str(dest)

    @staticmethod
    def _plan_to_json(plan: SeasonPlan) -> str:
        """Serialize the plan's tournaments to the compact JSON format used by the HTML."""
        data = []
        for t in plan.tournaments:
            games = [
                [g.home.label, g.away.label, g.parallel_slot]
                for g in t.games
            ]
            travel = furthest_traveling_team(t)
            travel_str = f"{travel[0].label} ~{travel[1]} km" if travel else ""
            data.append({
                "d": t.date.isoformat(),
                "a": t.arena,
                "g": t.age_group,
                "h": t.host_club or "",
                "m": games,
                "tr": travel_str,
            })
        return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _season_label(plan: SeasonPlan) -> str:
    start = plan.start_date
    end = plan.end_date
    if start and end:
        sy = start.year
        ey = end.year
        if sy == ey:
            return f"{sy}/{ey + 1}"
        return f"{sy}-{ey}"
    return ""


# ---------------------------------------------------------------------------
# Standalone CLI: python3 -m tournament_scheduler.html.html_exporter
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    from ..pipeline.state import PipelineState, StageName  # noqa: E402

    parser = argparse.ArgumentParser(description="Generer interaktiv HTML-oversikt over sesongplanen")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    parser.add_argument("--output", default="export/season_plan.html", help="Output HTML path")
    args = parser.parse_args()

    state = PipelineState(args.work_dir)
    plan_ckpt = state.read_stage(StageName.PLANNING)
    if not plan_ckpt or "plan" not in plan_ckpt:
        print("Fant ikke Stage 3-planen - kjor Stage 3 forst.", file=sys.stderr)
        sys.exit(1)

    from ..pipeline.stage4_export import _dict_to_plan  # noqa: E402
    plan = _dict_to_plan(plan_ckpt["plan"])

    exporter = HtmlExporter()
    path = exporter.export(plan, args.output)
    print(f"HTML generert: {path}")
