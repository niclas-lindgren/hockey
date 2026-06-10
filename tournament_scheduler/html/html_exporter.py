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

from tournament_scheduler.club_distances import (
    compute_team_travel_distances,
    furthest_traveling_team,
)
from ..models import SeasonPlan

# ---------------------------------------------------------------------------
# Inline SVG icons (14x14 or 16x16 viewBox, currentColor stroke, 1.5px)
# ---------------------------------------------------------------------------

_ICON_CALENDAR = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="12" height="11" rx="2"/><line x1="2" y1="7" x2="14" y2="7"/><line x1="5" y1="1" x2="5" y2="5"/><line x1="11" y1="1" x2="11" y2="5"/></svg>'
_ICON_CLIPBOARD = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 1.5h5a1 1 0 011 1v1h-7v-1a1 1 0 011-1z"/><rect x="3" y="3.5" width="10" height="11" rx="1.5"/><line x1="6" y1="7" x2="10" y2="7"/><line x1="6" y1="10" x2="10" y2="10"/></svg>'
_ICON_USERS = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="4" r="2.5"/><path d="M1.5 14v-1.5a4 4 0 014-4h1a4 4 0 014 4V14"/><circle cx="12" cy="5" r="1.5"/><path d="M12 11.5a3 3 0 012.5 2.5"/></svg>'
_ICON_TARGET = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="3"/><circle cx="8" cy="8" r="1" fill="currentColor"/></svg>'
_ICON_TRAVEL = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 13.7C17.3 9 20 5 20 2a8 8 0 1 0-16 0c0 3 2.7 7 8 11.7z"/></svg>'
_ICON_WARNING = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.5l-7 12h14l-7-12z"/><line x1="8" y1="6" x2="8" y2="9"/><circle cx="8" cy="11" r=".5" fill="currentColor"/></svg>'
_ICON_DOWNLOAD = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 10v3a1 1 0 01-1 1H3a1 1 0 01-1-1v-3"/><polyline points="5 7 8 10 11 7"/><line x1="8" y1="10" x2="8" y2="2"/></svg>'
_ICON_FILE_SPREADSHEET = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2h6l4 4v8a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z"/><polyline points="9 2 9 6 13 6"/><line x1="5" y1="9" x2="11" y2="9"/><line x1="5" y1="12" x2="11" y2="12"/></svg>'
_ICON_CLOCK = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><polyline points="8 4 8 8 11 10"/></svg>'
_ICON_BAR_CHART = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="14" x2="2" y2="6"/><line x1="6" y1="14" x2="6" y2="10"/><line x1="10" y1="14" x2="10" y2="4"/><line x1="14" y1="14" x2="14" y2="8"/></svg>'

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
  :root {
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
    --amber: #f59e0b;
    --emerald: #10b981;
    --rose: #f43f5e;
    --violet: #8b5cf6;
    --radius: 8px;
    --radius-sm: 4px;
    --radius-pill: 999px;
    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    --font-mono: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
  body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    min-height: 100dvh;
    font-size: 15px;
  }

  /* Navbar */
  .navbar {
    display: flex; align-items: center; gap: 2px;
    background: var(--bg-raised); padding: 0 16px;
    border-bottom: 1px solid var(--border-dim);
    height: 44px;
  }
  .navbar .brand {
    font-weight: 700; font-size: 13px; margin-right: 20px;
    color: var(--text); letter-spacing: -.01em;
  }
  .nav-icon { display: inline-flex; align-items: center; opacity: .55; }
  .nav-icon svg { display: block; width: 14px; height: 14px; }
  .navbar a {
    color: var(--text-muted); text-decoration: none;
    padding: 4px 10px; border-radius: var(--radius-sm);
    font-size: 12px; font-weight: 500;
    transition: color .15s, background .15s;
    display: inline-flex; align-items: center; gap: 5px;
  }
  .navbar a:hover { background: rgba(255,255,255,0.06); color: var(--text-secondary); }
  .navbar a.active {
    background: var(--accent-glow); color: var(--accent); font-weight: 600;
  }
  .navbar a.active .nav-icon { opacity: .85; }
  .navbar .meta-nav { margin-left: auto; font-size: 11px; color: var(--text-muted); }

  .app { max-width: 1400px; margin: 0 auto; padding: 24px 28px 64px; }

  /* Header */
  .header {
    display: flex; align-items: center;
    justify-content: space-between;
    flex-wrap: wrap; gap: 16px;
    padding: 0 0 28px;
    border-bottom: 1px solid var(--border-dim);
    margin-bottom: 28px;
  }
  .header-left { display: flex; align-items: center; gap: 16px; }
  .logo-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, var(--accent), var(--accent-dim));
    border-radius: var(--radius);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 16px; color: #fff;
    flex-shrink: 0;
  }
  .header h1 { font-size: 22px; font-weight: 700; letter-spacing: -.02em; }
  .header h1 span { color: var(--accent); }
  .header-sub { font-size: 13px; color: var(--text-muted); margin-top: 2px; }
  .header-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .stat-badge {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 12px;
    background: var(--bg-raised);
    border-radius: var(--radius-pill);
    font-size: 12px;
    color: var(--text-muted);
    border: 1px solid var(--border-dim);
    white-space: nowrap;
  }
  .stat-badge strong { color: var(--text-secondary); font-weight: 600; }
  .stat-badge svg { width: 14px; height: 14px; flex-shrink: 0; }

  /* Summary/details icon helpers */
  .summary-icon { display: inline-flex; align-items: center; margin-right: 6px; opacity: .6; }
  .summary-icon svg { display: block; width: 14px; height: 14px; }
  .club-dash-icon { display: inline-flex; align-items: center; }
  .club-dash-icon svg { display: block; width: 16px; height: 16px; }
  .travel-icon { display: inline-flex; align-items: center; margin-right: 4px; opacity: .7; }
  .travel-icon svg { display: block; width: 12px; height: 12px; }
  .warning-icon { display: inline-flex; align-items: center; margin-right: 6px; opacity: .6; }
  .warning-icon svg { display: block; width: 14px; height: 14px; }

  /* Filters */
  .filters {
    display: flex; flex-wrap: wrap; gap: 10px;
    margin-bottom: 24px; padding-bottom: 20px;
    border-bottom: 1px solid var(--border-dim);
  }
  .filter-group { display: flex; flex-direction: column; gap: 4px; }
  .filter-group label {
    font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .1em;
    color: var(--text-muted);
  }
  .filter-select, .filter-input {
    padding: 7px 12px;
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 13px; font-family: var(--font);
    outline: none;
    transition: border-color .15s, box-shadow .15s;
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
  .filter-input::placeholder { color: var(--text-muted); }
  .filter-select {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2371717a' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    padding-right: 28px;
  }
  .filter-clear {
    padding: 7px 14px;
    background: transparent;
    border: 1px solid var(--border-dim);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: 12px; font-family: var(--font);
    cursor: pointer;
    transition: all .15s;
    align-self: flex-end;
  }
  .filter-clear:hover { background: var(--bg-surface); color: var(--text-secondary); border-color: var(--border); }

  /* Count bar */
  .count-bar {
    display: flex; align-items: center;
    justify-content: space-between;
    flex-wrap: wrap; gap: 8px;
    padding: 10px 14px;
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    border-radius: var(--radius);
    margin-bottom: 24px;
    font-size: 13px;
    color: var(--text-muted);
  }
  .count-bar strong { color: var(--text-secondary); }

  /* Timeline */
  .timeline {
    position: relative;
    padding-left: 32px;
  }
  .timeline::before {
    content: '';
    position: absolute;
    left: 11px; top: 8px; bottom: 8px;
    width: 2px;
    background: linear-gradient(to bottom, var(--accent), var(--border-dim));
    opacity: .4;
  }

  .tournament-card {
    position: relative;
    margin-bottom: 16px;
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    border-radius: var(--radius);
    padding: 16px 20px;
    cursor: pointer;
    transition: border-color .15s, box-shadow .15s, transform .15s;
    user-select: none;
  }
  .tournament-card:hover {
    border-color: var(--accent-dim);
    box-shadow: 0 0 0 1px var(--accent-glow), 0 4px 24px rgba(0,0,0,.2);
  }
  .tournament-card.hidden { display: none; }
  .tournament-card::before {
    content: '';
    position: absolute;
    left: -25px; top: 24px;
    width: 12px; height: 12px;
    background: var(--accent);
    border: 3px solid var(--bg);
    border-radius: 50%;
    z-index: 1;
  }
  .tournament-card-header {
    display: flex; align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }
  .tournament-date {
    display: flex; flex-direction: column;
    align-items: center;
    min-width: 52px;
    padding: 6px 10px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-dim);
  }
  .tournament-date .day { font-size: 20px; font-weight: 700; line-height: 1; }
  .tournament-date .month { font-size: 10px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .06em; margin-top: 2px; }
  .tournament-date .weekday { font-size: 9px; color: var(--accent); text-transform: uppercase; letter-spacing: .1em; margin-top: 3px; }
  .tournament-info { flex: 1; min-width: 0; }
  .tournament-info h3 { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  .tournament-info h3 span { color: var(--accent); }
  .tournament-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }

  .tag {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-size: 11px; font-weight: 500;
    background: var(--bg);
    border: 1px solid var(--border-dim);
    color: var(--text-muted);
  }
  .tag--age { background: rgba(14,165,233,.08); border-color: rgba(14,165,233,.15); color: var(--accent); }
  .tag--arena { background: rgba(245,158,11,.08); border-color: rgba(245,158,11,.15); color: var(--amber); }
  .tag--teams { background: rgba(16,185,129,.08); border-color: rgba(16,185,129,.15); color: var(--emerald); }
  .tag--travel { background: rgba(245,158,11,.08); border-color: rgba(245,158,11,.15); color: var(--amber); }
  .tag svg { width: 12px; height: 12px; flex-shrink: 0; }

  .tournament-arrow {
    color: var(--text-muted);
    transition: transform .25s cubic-bezier(.16,1,.3,1);
    flex-shrink: 0; margin-top: 4px;
  }
  .tournament-arrow svg { width: 18px; height: 18px; display: block; }
  .tournament-card.expanded .tournament-arrow { transform: rotate(180deg); }

  /* Cancelled badge */
  .cancelled-badge {
    display: inline-flex; align-items: center; gap: 4px;
    background: rgba(244,63,94,.1); color: var(--rose);
    border: 1px solid rgba(244,63,94,.2);
    font-size: 10px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em;
    padding: 2px 8px; border-radius: var(--radius-sm);
    margin-bottom: 8px;
  }
  .tournament-card.cancelled {
    border-left-color: rgba(244,63,94,.3);
    opacity: .88;
  }

  /* Match table */
  .matches {
    max-height: 0; overflow: hidden;
    transition: max-height .4s cubic-bezier(.16,1,.3,1), opacity .25s ease;
    opacity: 0;
  }
  .tournament-card.expanded .matches { max-height: 2000px; opacity: 1; }
  .matches-inner {
    margin-top: 14px; padding-top: 14px;
    border-top: 1px solid var(--border-dim);
  }
  .matches-header {
    display: flex; justify-content: space-between;
    align-items: center; margin-bottom: 10px;
  }
  .matches-header h4 { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: .08em; }
  .matches-header .count { font-size: 11px; color: var(--text-muted); }
  .match-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 5px;
  }
  .match-row {
    display: flex; align-items: center; gap: 6px;
    padding: 5px 8px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    font-size: 12px;
    color: var(--text-muted);
  }
  .match-row .vs { color: var(--border); font-size: 9px; font-weight: 600; }
  .match-row.bye-row {
    background: rgba(14,165,233,.03);
    border: 1px dashed var(--border);
    color: var(--text-muted);
  }
  .match-row .bye-label { font-style: italic; opacity: .6; }
  .match-row .slot {
    margin-left: auto;
    padding: 1px 7px;
    border-radius: var(--radius-pill);
    font-size: 9px; font-weight: 600;
    background: rgba(14,165,233,.08);
    color: var(--accent);
    white-space: nowrap;
  }

  /* Score quality */
  .score-bar {
    display: flex; gap: 20px; flex-wrap: wrap;
    padding: 12px 16px; margin-bottom: 20px;
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    border-radius: var(--radius);
  }
  .score-item { font-size: 12px; color: var(--text-muted); }
  .score-item strong { color: var(--text-secondary); }
  .score-dot {
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    margin-right: 3px;
  }

  .no-results {
    text-align: center;
    padding: 64px 24px;
    color: var(--text-muted);
  }
  .no-results svg { width: 48px; height: 48px; margin-bottom: 16px; opacity: .3; }
  .no-results p { font-size: 14px; }

  /* Export download links */
  .export-links {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding: 8px 0; margin-bottom: 8px;
  }
  .export-link-btn {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 12px; border-radius: var(--radius-sm);
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    color: var(--text-secondary); text-decoration: none;
    font-size: 12px; font-weight: 500;
    transition: background .15s, border-color .15s, color .15s;
  }
  .export-link-btn:hover {
    background: var(--link-color); color: #09090b;
    border-color: var(--link-color);
  }
  .export-link-btn svg { width: 14px; height: 14px; display: block; }

  /* Team stats details sections */
  .team-stats summary {
    cursor: pointer;
    padding: 10px 14px;
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    border-radius: var(--radius);
    font-size: 13px; font-weight: 600;
    color: var(--text-secondary);
    user-select: none;
    display: flex; align-items: center;
    transition: border-color .15s, background .15s;
  }
  .team-stats summary:hover {
    border-color: var(--border);
    background: var(--bg-surface);
  }
  .team-stats summary::-webkit-details-marker { display: none; }
  .team-stats summary::before {
    content: '';
    display: inline-block;
    width: 6px; height: 6px;
    border-right: 2px solid var(--text-muted);
    border-bottom: 2px solid var(--text-muted);
    margin-right: 8px;
    transform: rotate(-45deg);
    transition: transform .15s;
  }
  .team-stats[open] summary::before { transform: rotate(45deg); }

  .club-dashboard {
    margin-bottom: 20px;
    padding: 14px 18px;
    background: var(--bg-raised);
    border: 1px solid var(--border-dim);
    border-left: 3px solid var(--amber);
    border-radius: var(--radius);
  }

  @media (max-width: 768px) {
    .app { padding: 16px 12px 48px; }
    .navbar { height: auto; padding: 8px 12px; }
    .header { flex-direction: column; align-items: flex-start; }
    .header-right { width: 100%; }
    .filters { flex-direction: column; }
    .filter-select, .filter-input { min-width: 100%; }
    .timeline { padding-left: 24px; }
    .tournament-card { padding: 14px; }
    .tournament-card::before { left: -18px; width: 10px; height: 10px; }
    .timeline::before { left: 8px; }
    .tournament-card-header { flex-wrap: wrap; }
    .match-grid { grid-template-columns: 1fr; }
    .tournament-date { min-width: 48px; padding: 6px 8px; }
    .tournament-date .day { font-size: 18px; }
    h1 { font-size: 18px; }
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>
<div class="navbar">
  <span class="brand">RVV Miniputt</span>
  <a href="calendars.html"><span class="nav-icon">$ICON_CALENDAR$</span> Skrapede kalendere</a>
  <a href="season_plan.html" class="active"><span class="nav-icon">$ICON_CLIPBOARD$</span> Sesongplan</a>
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

  <!-- Export download links -->
  $EXPORT_LINKS_HTML$

  <!-- Club dashboard (hidden until a club is selected) -->
  <div class="club-dashboard" id="clubDashboard" style="display:none;margin-bottom:24px;padding:16px 20px;background:var(--bg-raised);border:1px solid var(--border-dim);border-left:4px solid var(--amber);border-radius:var(--radius)">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:12px">
      <h3 style="font-size:16px;color:var(--amber);font-weight:700;margin:0;display:flex;align-items:center;gap:6px"><span class="club-dash-icon">$ICON_TARGET$</span> <span id="clubDashName"></span></h3>
      <span style="font-size:12px;color:var(--text-muted)">Klubb-oversikt</span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:12px">
      <div class="stat-badge" style="background:rgba(52,211,153,.08);border-color:rgba(52,211,153,.2)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <span style="color:var(--emerald)"><strong id="clubDashHosted">0</strong> hjemmeturneringer</span>
      </div>
      <div class="stat-badge" style="background:rgba(56,189,248,.08);border-color:rgba(56,189,248,.2)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/></svg>
        <span style="color:var(--accent)"><strong id="clubDashAway">0</strong> borteturneringer</span>
      </div>
      <div class="stat-badge" style="background:rgba(251,191,36,.08);border-color:rgba(251,191,36,.2)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 21.7C17.3 17 20 13 20 10a8 8 0 1 0-16 0c0 3 2.7 7 8 11.7z"/></svg>
        <span style="color:var(--amber)"><strong id="clubDashTravel">0</strong> km reise</span>
      </div>
      <div class="stat-badge" style="background:rgba(167,139,250,.08);border-color:rgba(167,139,250,.2)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
        <span style="color:#a78bfa"><strong id="clubDashTeams">0</strong> lag</span>
      </div>
    </div>
  </div>

  <!-- Team game counts table -->
  <details class="team-stats" id="teamStats" style="margin-bottom:24px">
    <summary>
      <span class="summary-icon">$ICON_USERS$</span> Kamper per lag ($TEAM_COUNT$ lag) &mdash; klikk for å vise
    </summary>
    <div style="margin-top:8px;overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:2px solid var(--border-dim)">
            <th style="text-align:left;padding:8px 12px;color:var(--text-muted);font-weight:600">Lag</th>
            <th style="text-align:right;padding:8px 12px;color:var(--text-muted);font-weight:600">Kamper</th>
            <th style="text-align:left;padding:8px 12px;color:var(--text-muted);font-weight:600">Siste kamp</th>
          </tr>
        </thead>
        <tbody id="teamGameCountsBody">
        </tbody>
      </table>
    </div>
  </details>

  <!-- Team travel distances table -->
  <details class="team-stats travel-stats" id="travelStats" style="margin-bottom:24px">
    <summary>
      <span class="summary-icon">$ICON_TRAVEL$</span> Reiseavstand per lag &mdash; klikk for å vise
      <span style="margin-left:8px;font-weight:400;font-size:12px;color:var(--text-muted)">$MOST_TRAVEL_TEAM$ reiste lengst: $MOST_TRAVEL_KM$ km</span>
    </summary>
    <div style="margin-top:8px;overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
          <tr style="border-bottom:2px solid var(--border-dim)">
            <th style="text-align:left;padding:8px 12px;color:var(--text-muted);font-weight:600">Lag</th>
            <th style="text-align:right;padding:8px 12px;color:var(--text-muted);font-weight:600">Total reise (km)</th>
            <th style="text-align:right;padding:8px 12px;color:var(--text-muted);font-weight:600">Borteturneringer</th>
          </tr>
        </thead>
        <tbody id="teamTravelBody">
        </tbody>
      </table>
    </div>
  </details>

  $TRAVEL_COUNT_ESTIMATE_HTML$

  <!-- Calendar heatmap -->
  <details class="team-stats heatmap-stats" id="heatmapSection" style="margin-bottom:24px" open>
    <summary>
      <span class="summary-icon">$ICON_CALENDAR$</span> Sesongvarmekart &mdash; klikk for å vise/skjule
      <span style="margin-left:8px;font-weight:400;font-size:12px;color:var(--text-muted)">$HEATMAP_CLUBS_COUNT$ klubber · $HEATMAP_WEEKS_COUNT$ uker</span>
    </summary>
    <div style="margin-top:8px;overflow-x:auto;font-size:11px">
      <table id="heatmapTable" style="border-collapse:collapse;width:max-content;min-width:100%">
        <thead id="heatmapHead"></thead>
        <tbody id="heatmapBody"></tbody>
      </table>
      <div id="heatmapLegend" style="display:flex;flex-wrap:wrap;gap:12px;padding:10px 0;margin-top:8px"></div>
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
const TEAM_TRAVEL = $TEAM_TRAVEL_JSON$;
const HEATMAP = $HEATMAP_JSON$;
const HEATMAP_WEEKS = $HEATMAP_WEEKS_JSON$;
const HEATMAP_CLUBS = $HEATMAP_CLUBS_JSON$;
const CLUB_STATS = $CLUB_STATS_JSON$;
const ALL_CLUBS = $ALL_CLUBS_JSON$;

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
    tr.style.borderBottom = '1px solid var(--border-dim)';
    const tdLabel = document.createElement('td');
    tdLabel.style.padding = '6px 12px';
    tdLabel.textContent = label;
    const tdCount = document.createElement('td');
    tdCount.style.padding = '6px 12px';
    tdCount.style.textAlign = 'right';
    tdCount.textContent = count;
    const tdLast = document.createElement('td');
    tdLast.style.padding = '6px 12px';
    tdLast.style.color = 'var(--text-muted)';
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

// Render team travel distances table
(function() {
  const body = document.getElementById('teamTravelBody');
  if (!body) return;
  const sorted = Object.entries(TEAM_TRAVEL).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const maxKm = sorted.length > 0 ? sorted[0][1] : 0;
  let awayCounts = {};
  TOURNAMENTS.forEach(t => {
    if (t.cx) return;
    const hostClub = t.h;
    if (!hostClub) return;
    t.m.forEach(([h, a]) => {
      const hClub = getClubFromTeam(h);
      if (hClub !== hostClub) awayCounts[h] = (awayCounts[h] || 0) + 1;
      const aClub = getClubFromTeam(a);
      if (aClub !== hostClub) awayCounts[a] = (awayCounts[a] || 0) + 1;
    });
  });
  sorted.forEach(([label, km]) => {
    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid var(--border-dim)';
    const isMost = km === maxKm && km > 0;
    if (isMost) {
      tr.style.background = 'rgba(251,191,36,.08)';
    }
    const tdLabel = document.createElement('td');
    tdLabel.style.padding = '6px 12px';
    if (isMost) {
      tdLabel.innerHTML = '<span class="travel-icon">$ICON_TRAVEL$</span> <strong>' + label + '</strong> <span style="font-size:10px;color:var(--amber);font-weight:600">(lengst reisevei)</span>';
    } else {
      tdLabel.textContent = label;
    }
    const tdKm = document.createElement('td');
    tdKm.style.padding = '6px 12px';
    tdKm.style.textAlign = 'right';
    tdKm.textContent = km.toLocaleString();
    if (isMost) {
      tdKm.style.color = 'var(--amber)';
      tdKm.style.fontWeight = '600';
    }
    const tdAway = document.createElement('td');
    tdAway.style.padding = '6px 12px';
    tdAway.style.textAlign = 'right';
    tdAway.textContent = awayCounts[label] || 0;
    if (isMost) tdAway.style.color = 'var(--amber)';
    tr.appendChild(tdLabel);
    tr.appendChild(tdKm);
    tr.appendChild(tdAway);
    body.appendChild(tr);
  });
})();

// Render calendar heatmap
(function() {
  const head = document.getElementById('heatmapHead');
  const body = document.getElementById('heatmapBody');
  const legend = document.getElementById('heatmapLegend');
  if (!head || !body || !legend) return;
  if (!HEATMAP_WEEKS.length || !HEATMAP_CLUBS.length) {
    body.innerHTML = '<tr><td colspan="' + (HEATMAP_WEEKS.length + 1) + '" style="padding:16px;text-align:center;color:var(--text-muted)">Ingen turneringsdata for varmekart</td></tr>';
    return;
  }

  // Build legend
  HEATMAP_CLUBS.forEach(club => {
    const c = HEATMAP_CLUB_COLORS[club] || {bg: '#2a2a2a', text: '#999'};
    const span = document.createElement('span');
    span.style.cssText = 'display:inline-flex;align-items:center;gap:4px;font-size:11px;color:' + c.text;
    span.innerHTML = '<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:' + c.bg + ';border:1px solid ' + c.text + '"></span>' + club;
    legend.appendChild(span);
  });

  // Build header row: week labels with month grouping
  let headerRow = '<tr><th style="position:sticky;left:0;z-index:1;background:var(--bg);padding:6px 10px;text-align:left;color:var(--text-muted);font-weight:600;min-width:110px">Klubb</th>';
  const MONTHS_NO = ["","jan","feb","mar","apr","mai","jun","jul","aug","sep","okt","nov","des"];
  let lastMonth = '';
  HEATMAP_WEEKS.forEach(wk => {
    // wk is like "2025-W40" — extract month from first day of that week
    const parts = wk.split('-W');
    const year = parseInt(parts[0]);
    const week = parseInt(parts[1]);
    // Compute first day of ISO week (Monday)
    const jan4 = new Date(Date.UTC(year, 0, 4));
    const jan4Day = jan4.getUTCDay() || 7;
    const firstThursday = new Date(Date.UTC(year, 0, 4 - jan4Day + 4));
    const monday = new Date(firstThursday.getTime());
    monday.setUTCDate(monday.getUTCDate() + (week - 1) * 7);
    const month = MONTHS_NO[monday.getUTCMonth() + 1];
    const monthLabel = month !== lastMonth ? month : '';
    if (month !== lastMonth && month) lastMonth = month;
    headerRow += '<th style="padding:4px 2px;text-align:center;font-weight:600;font-size:10px;color:var(--text-muted)">' + monthLabel + '<br><span style="font-size:9px;color:var(--text-muted)">' + wk.slice(-2) + '</span></th>';
  });
  headerRow += '</tr>';
  head.innerHTML = headerRow;

  // Build body: one row per club
  let bodyHtml = '';
  HEATMAP_CLUBS.forEach(club => {
    const c = HEATMAP_CLUB_COLORS[club] || {bg: '#2a2a2a', text: '#999'};
    bodyHtml += '<tr style="border-bottom:1px solid var(--border-dim)">';
    bodyHtml += '<td style="position:sticky;left:0;z-index:0;background:var(--bg);padding:6px 10px;font-size:12px;color:' + c.text + ';font-weight:600">' + club + '</td>';
    HEATMAP_WEEKS.forEach(wk => {
      const weekData = HEATMAP[wk] || {};
      const clubData = weekData[club];
      if (clubData && clubData.length) {
        const label = clubData.join(',');
        bodyHtml += '<td style="background:' + c.bg + ';border:1px solid ' + c.text + ';padding:3px 4px;text-align:center;font-size:10px;color:' + c.text + ';font-weight:600;white-space:nowrap">' + label + '</td>';
      } else {
        bodyHtml += '<td style="background:rgba(30,41,59,.4);border:1px solid var(--border-dim);padding:3px 4px;text-align:center"></td>';
      }
    });
    bodyHtml += '</tr>';
  });
  body.innerHTML = bodyHtml;
})();

function buildMatchHTML(matches, byes) {
  let html = matches.map(([home, away, slot]) =>
    '<div class="match-row"><span>' + home + '</span><span class="vs">vs</span><span>' + away +
    '</span><span class="slot">' + slotLabel(slot) + '</span></div>'
  ).join('');
  if (byes && Object.keys(byes).length) {
    for (const [roundNum, labels] of Object.entries(byes)) {
      for (const label of labels) {
        html += '<div class="match-row bye-row"><span class="bye-label">Pause</span><span class="vs">·</span><span>' + label + '</span><span class="slot"></span></div>';
      }
    }
  }
  return html;
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
    const cancelledClass = t.cx ? ' cancelled' : '';
    const cancelledBadge = t.cx
      ? '<div class="cancelled-badge"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>AVLYST' + (t.cr ? ': ' + t.cr : '') + '</div>'
      : '';
    html += '<div class="tournament-card' + cancelledClass + '" onclick="this.classList.toggle(\'expanded\')">' +
      cancelledBadge +
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
        '<div class="match-grid">' + buildMatchHTML(t.m, t.b) + '</div>' +
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
document.getElementById('filterClub').addEventListener('change', function() {
  const club = this.value;
  const dashboard = document.getElementById('clubDashboard');
  if (club && CLUB_STATS[club]) {
    const s = CLUB_STATS[club];
    document.getElementById('clubDashName').textContent = club;
    document.getElementById('clubDashHosted').textContent = s.hosted;
    document.getElementById('clubDashAway').textContent = s.away;
    document.getElementById('clubDashTravel').textContent = (s.travel_km || 0).toLocaleString();
    document.getElementById('clubDashTeams').textContent = s.teams;
    dashboard.style.display = 'block';
  } else {
    dashboard.style.display = 'none';
  }
  render();
});
document.getElementById('filterSearch').addEventListener('input', render);
document.getElementById('filterClear').addEventListener('click', function() {
  document.getElementById('filterAge').value = '';
  document.getElementById('filterArena').value = '';
  document.getElementById('filterClub').value = '';
  document.getElementById('filterSearch').value = '';
  document.getElementById('clubDashboard').style.display = 'none';
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

    def export(self, plan: SeasonPlan, path: str | os.PathLike[str], meta: dict[str, Any] | None = None, *, output_files: dict[str, str] | None = None) -> str:
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
        output_files:
            Optional dict mapping format name (``excel``, ``csv_overview``,
            ``csv_games``, ``ical``) to absolute file paths. Download links
            are rendered with relative filenames (same directory as HTML).
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

        # Compute per-team travel distances for the travel table
        team_travel = compute_team_travel_distances(plan)
        team_travel_json = json.dumps(team_travel, ensure_ascii=False)

        # Identify the most-traveled team
        if team_travel:
            most_travel_team = max(team_travel, key=team_travel.get)  # type: ignore[arg-type]
            most_travel_km = str(team_travel[most_travel_team])
        else:
            most_travel_team = "-"
            most_travel_km = "0"

        # Travel-count estimate HTML (shown only when travel data is thin)
        travel_count_estimate_html = ""
        if len(team_travel) < 3:
            travel_count_estimate_html = (
                '<div style="padding:8px 16px;font-size:12px;color:var(--text-muted);'
                'text-align:center;margin-bottom:12px">'
                '<span class="warning-icon">$ICON_WARNING$</span> '
                'Få lag med reisedata &mdash; avstander er estimater basert på '
                'kjente arenaer.</div>'
            )

        # --- Heatmap data: week → {club: [age_groups]} ---
        from collections import OrderedDict
        heatmap: dict[str, dict[str, list[str]]] = {}
        all_host_clubs: set[str] = set()
        for t in plan.tournaments:
            if t.cancelled:
                continue
            if not t.date:
                continue
            host = t.host_club or ""
            if not host:
                continue
            iso_year, iso_week, _ = t.date.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            if week_key not in heatmap:
                heatmap[week_key] = {}
            if host not in heatmap[week_key]:
                heatmap[week_key][host] = []
            heatmap[week_key][host].append(t.age_group)
            all_host_clubs.add(host)

        # Ordered weeks (ISO format, Sept–Apr window)
        heatmap_weeks = sorted(heatmap.keys())
        heatmap_clubs = sorted(all_host_clubs)
        heatmap_json = json.dumps(heatmap, ensure_ascii=False)
        heatmap_weeks_json = json.dumps(heatmap_weeks, ensure_ascii=False)
        heatmap_clubs_json = json.dumps(heatmap_clubs, ensure_ascii=False)

        # Club colour palette (same as calendar_viewer.py dark-theme adjusted)
        _club_colors = [
            {"bg": "#1a3a5c", "text": "#64b5f6"},
            {"bg": "#1b3a1b", "text": "#81c784"},
            {"bg": "#3a2e0a", "text": "#ffd54f"},
            {"bg": "#2a1a3a", "text": "#ba68c8"},
            {"bg": "#3a1a1a", "text": "#e57373"},
            {"bg": "#0a2a3a", "text": "#4dd0e1"},
            {"bg": "#3a3a0a", "text": "#fff176"},
            {"bg": "#1a3a2a", "text": "#aed581"},
            {"bg": "#3a1a0a", "text": "#ff8a65"},
        ]
        club_color_map: dict[str, dict[str, str]] = {}
        for i, club in enumerate(heatmap_clubs):
            club_color_map[club] = _club_colors[i % len(_club_colors)]
        heatmap_club_colors_json = json.dumps(club_color_map, ensure_ascii=False)

        # --- Per-club aggregate stats for club dashboard ---
        # hosted: count of tournaments this club hosts
        # away: count of tournaments where this club's teams participate but don't host
        # teams: set of team labels belonging to this club
        # travel_km: total travel km (sum across club's teams from team_travel dict)
        club_hosted: dict[str, int] = {}
        club_away: dict[str, int] = {}
        club_teams: dict[str, list[str]] = {}
        club_travel: dict[str, int] = {}

        for t in plan.tournaments:
            if t.cancelled:
                continue
            host = t.host_club or ""
            if host:
                club_hosted[host] = club_hosted.get(host, 0) + 1
            # Collect away clubs from participating teams
            seen_clubs: set[str] = set()
            for team in t.teams:
                tc = team.club
                if tc not in club_teams:
                    club_teams[tc] = []
                if team.label not in club_teams[tc]:
                    club_teams[tc].append(team.label)
                if host and tc != host and tc not in seen_clubs:
                    seen_clubs.add(tc)
                    club_away[tc] = club_away.get(tc, 0) + 1

        # Aggregate travel per club from per-team travel
        for team_label, km in team_travel.items():
            # Derive club from team label (club is first token or known pattern)
            for club_name in club_teams:
                if team_label.startswith(club_name):
                    club_travel[club_name] = club_travel.get(club_name, 0) + km
                    break

        club_stats: dict[str, dict[str, object]] = {}
        all_clubs_set: set[str] = set()
        for club in set(list(club_hosted.keys()) + list(club_away.keys()) + list(club_teams.keys())):
            all_clubs_set.add(club)
            club_stats[club] = {
                "hosted": club_hosted.get(club, 0),
                "away": club_away.get(club, 0),
                "teams": len(club_teams.get(club, [])),
                "travel_km": club_travel.get(club, 0),
                "team_list": club_teams.get(club, []),
            }
        all_clubs_list = sorted(all_clubs_set)
        club_stats_json = json.dumps(club_stats, ensure_ascii=False)
        all_clubs_json = json.dumps(all_clubs_list, ensure_ascii=False)

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
            scrape_meta = f"{src} kilder &middot; {ev} hendelser &middot; {age}" if age else f"{src} kilder &middot; {ev} hendelser"
        else:
            scrape_meta = ""

        # Build export download links HTML.
        export_links_html = ""
        if output_files:
            export_links_html = '<div class="export-links">'
            link_defs = [
                ("excel", _ICON_DOWNLOAD + " Last ned Excel (.xlsx)", "#38bdf8"),
                ("csv_overview", _ICON_BAR_CHART + " Last ned CSV", "#34d399"),
                ("csv_games", _ICON_FILE_SPREADSHEET + " Last ned CSV (kamper)", "#fbbf24"),
                ("ical", _ICON_CALENDAR + " Last ned iCal (.ics)", "#f87171"),
            ]
            for key, label, color in link_defs:
                if key in output_files:
                    filename = Path(output_files[key]).name
                    export_links_html += (
                        f'<a href="{filename}" class="export-link-btn" '
                        f'style="--link-color:{color}" download>{label}</a>'
                    )
            export_links_html += '</div>'

        replacements = {
            "$ICON_CALENDAR$": _ICON_CALENDAR,
            "$ICON_CLIPBOARD$": _ICON_CLIPBOARD,
            "$ICON_USERS$": _ICON_USERS,
            "$ICON_TARGET$": _ICON_TARGET,
            "$ICON_TRAVEL$": _ICON_TRAVEL,
            "$ICON_WARNING$": _ICON_WARNING,
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
            "$TEAM_TRAVEL_JSON$": team_travel_json,
            "$MOST_TRAVEL_TEAM$": most_travel_team,
            "$MOST_TRAVEL_KM$": most_travel_km,
            "$TRAVEL_COUNT_ESTIMATE_HTML$": travel_count_estimate_html,
            "$HEATMAP_JSON$": heatmap_json,
            "$HEATMAP_WEEKS_JSON$": heatmap_weeks_json,
            "$HEATMAP_CLUBS_JSON$": heatmap_clubs_json,
            "$HEATMAP_CLUB_COLORS_JSON$": heatmap_club_colors_json,
            "$HEATMAP_CLUBS_COUNT$": str(len(heatmap_clubs)),
            "$HEATMAP_WEEKS_COUNT$": str(len(heatmap_weeks)),
            "$CLUB_STATS_JSON$": club_stats_json,
            "$ALL_CLUBS_JSON$": all_clubs_json,
            "$DIVERSITY_SCORE$": str(int((plan.diversity_score or 0) * 100)),
            "$MONTH_BALANCE_SCORE$": str(int((plan.month_balance_score or 0) * 100)),
            "$PAIRWISE_SCORE$": str(int((plan.pairwise_matchup_score or 0) * 100)),
            "$EXTRA_AGE_OPTIONS$": extra_age_options,
            "$TOURNAMENTS_JSON$": tournaments_json,
            "$EXPORT_LINKS_HTML$": export_links_html,
        }

        html = _HTML_TEMPLATE
        for marker, value in replacements.items():
            html = html.replace(marker, value)

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        return str(dest)

    @staticmethod
    @staticmethod
    def _plan_to_json(plan: SeasonPlan) -> str:
        """Serialize the plan's tournaments to the compact JSON format used by the HTML."""
        data = []
        for t in plan.tournaments:
            games = [
                [g.home.label, g.away.label, g.parallel_slot]
                for g in t.games
            ]
            bye_data = {
                str(r): labels
                for r, labels in t.get_bye_rounds().items()
            } if t.get_bye_rounds() else {}
            travel = furthest_traveling_team(t)
            travel_str = f"{travel[0].label} ~{travel[1]} km" if travel else ""
            entry: dict[str, object] = {
                "d": t.date.isoformat(),
                "a": t.arena,
                "g": t.age_group,
                "h": t.host_club or "",
                "m": games,
                "b": bye_data,
                "tr": travel_str,
            }
            if t.cancelled:
                entry["cx"] = True
                entry["cr"] = t.cancellation_reason or ""
            data.append(entry)
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
