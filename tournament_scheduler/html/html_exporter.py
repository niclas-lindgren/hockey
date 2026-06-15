"""Interactive HTML overview for the season plan.

Reads a :class:`~tournament_scheduler.models.SeasonPlan` and generates a
standalone, interactive HTML page showing all tournaments, filtering by
age group / arena / club / search, and expandable match tables.

HTML is assembled from template fragments in ``templates/``.
"""

from __future__ import annotations

import html as _html
import json
import os
from pathlib import Path
from typing import Any
import re

from tournament_scheduler.club_distances import (
    compute_team_travel_distances,
    furthest_traveling_team,
)
from tournament_scheduler.fairness_model import SeasonFairnessModel
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

_RVV_CLUBS = (
    "Ringerike",
    "Tønsberg",
    "Frisk Asker",
    "Sandefjord Penguins",
    "Jar",
    "Holmen",
    "Skien",
    "Jutul",
    "Kongsberg",
)

# ---------------------------------------------------------------------------
# Load template fragments
# ---------------------------------------------------------------------------

from .templates import (
    STYLES_CSS,
    NAVBAR,
    HEADER,
    SCORES,
    METRICS,
    FILTERS,
    TEAM_STATS,
    TRAVEL_STATS,
    HEATMAP,
    CLUB_DASHBOARD,
    REVIEW_SUMMARY,
    PAGE_TEMPLATE,
    JAVASCRIPT,
    COUNT_BAR,
)


# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class HtmlExporter:
    """Generates a standalone interactive HTML overview of a :class:`SeasonPlan`."""

    def export(
        self,
        plan: SeasonPlan,
        path: str | os.PathLike[str],
        meta: dict[str, Any] | None = None,
        *,
        output_files: dict[str, str] | None = None,
        pipeline_meta: dict[str, Any] | None = None,
        round_length_for_age_group: dict[str, int] | None = None,
        age_groups: list[str] | None = None,
    ) -> str:
        """Write an interactive HTML overview to *path*, return the path.

        Parameters
        ----------
        plan: The season plan to export.
        path: Output file path.
        meta: Optional metadata from scraped data cache (total_events, source_count, etc.).
        output_files: Optional dict mapping format name to absolute file paths for download links.
        pipeline_meta: Optional pipeline-wide metadata with blocked sources, date range, etc.
        round_length_for_age_group: Optional mapping of age group -> round
            length in minutes, used together with each tournament's
            ``start_time`` to compute and display a "HH:MM-HH:MM" time
            range via ``Tournament.end_time()``.
        """
        tournaments_json = self._plan_to_json(plan, round_length_for_age_group)

        # Count unique teams
        all_teams: set[str] = set()
        for t in plan.tournaments:
            for g in t.games:
                all_teams.add(g.home.label)
                all_teams.add(g.away.label)

        # Team game counts
        team_game_counts: dict[str, int] = {}
        for t in plan.tournaments:
            for g in t.games:
                for team_label in (g.home.label, g.away.label):
                    team_game_counts[team_label] = team_game_counts.get(team_label, 0) + 1
        team_game_counts_json = json.dumps(team_game_counts, ensure_ascii=False)

        # Team travel distances
        team_travel = compute_team_travel_distances(plan)
        team_travel_json = json.dumps(team_travel, ensure_ascii=False)

        # Most-traveled team
        most_travel_team = next(iter(team_travel.keys()), "-") if team_travel else "-"
        most_travel_km = str(max(team_travel.values())) if team_travel else "0"

        # Total travel km
        total_travel_km = sum(team_travel.values())

        # Travel estimate warning
        travel_count_estimate_html = ""
        if len(team_travel) < 3:
            travel_count_estimate_html = (
                '<div style="padding:8px 16px;font-size:12px;color:var(--text-muted);'
                'text-align:center;margin-bottom:12px">'
                '<span class="warning-icon">$ICON_WARNING$</span> '
                'F\u00e5 lag med reisedata &mdash; avstander er estimater basert p\u00e5 '
                'kjente arenaer.</div>'
            )

        # --- Heatmap ---
        heatmap: dict[str, dict[str, list[str]]] = {}
        all_host_clubs: set[str] = set()
        for t in plan.tournaments:
            if t.cancelled or not t.date:
                continue
            host = t.host_club or ""
            if not host:
                continue
            iso_year, iso_week, _ = t.date.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            heatmap.setdefault(week_key, {}).setdefault(host, []).append(t.age_group)
            all_host_clubs.add(host)

        heatmap_weeks = sorted(heatmap.keys())
        heatmap_clubs = sorted(all_host_clubs)
        heatmap_json = json.dumps(heatmap, ensure_ascii=False)
        heatmap_weeks_json = json.dumps(heatmap_weeks, ensure_ascii=False)
        heatmap_clubs_json = json.dumps(heatmap_clubs, ensure_ascii=False)

        # Club colors for heatmap (dark theme)
        _club_colors_dark = [
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
        # Club colors for heatmap (light theme) — pastel backgrounds with
        # darker, high-contrast text, suited for a `--bg: #f4f4f5` page.
        _club_colors_light = [
            {"bg": "#dbeafe", "text": "#1d4ed8"},  # blue
            {"bg": "#dcfce7", "text": "#15803d"},  # green
            {"bg": "#fef3c7", "text": "#b45309"},  # amber
            {"bg": "#ede9fe", "text": "#6d28d9"},  # purple
            {"bg": "#ffe4e6", "text": "#be123c"},  # rose
            {"bg": "#cffafe", "text": "#0e7490"},  # cyan
            {"bg": "#fef9c3", "text": "#a16207"},  # yellow
            {"bg": "#ecfccb", "text": "#4d7c0f"},  # lime
            {"bg": "#ffedd5", "text": "#c2410c"},  # orange
        ]
        club_color_map_dark = {
            club: _club_colors_dark[i % len(_club_colors_dark)]
            for i, club in enumerate(heatmap_clubs)
        }
        club_color_map_light = {
            club: _club_colors_light[i % len(_club_colors_light)]
            for i, club in enumerate(heatmap_clubs)
        }
        heatmap_club_colors_json = json.dumps(
            {"dark": club_color_map_dark, "light": club_color_map_light},
            ensure_ascii=False,
        )

        # --- Per-club aggregate stats ---
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
            seen_clubs: set[str] = set()
            for team in t.teams:
                tc = team.club
                club_teams.setdefault(tc, [])
                if team.label not in club_teams[tc]:
                    club_teams[tc].append(team.label)
                if host and tc != host and tc not in seen_clubs:
                    seen_clubs.add(tc)
                    club_away[tc] = club_away.get(tc, 0) + 1

        for team_label, km in team_travel.items():
            for club_name in club_teams:
                if team_label.startswith(club_name):
                    club_travel[club_name] = club_travel.get(club_name, 0) + km
                    break

        club_stats: dict[str, dict[str, object]] = {}
        all_clubs_set: set[str] = set()
        for club in set(club_hosted) | set(club_away) | set(club_teams):
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
        display_age_groups = list(dict.fromkeys(age_groups or sorted({t.age_group for t in plan.tournaments})))
        age_group_options = "".join(
            f'<option value="{ag}">{ag}</option>'
            for ag in display_age_groups
        )

        # Scrape metadata for navbar
        if meta:
            ev = meta.get("total_events", 0)
            src = meta.get("source_count", 0)
            ts = meta.get("updated_at", "")
            age = _age_string(ts)
            scrape_meta = f"{src} kilder &middot; {ev} hendelser &middot; {age}" if age else f"{src} kilder &middot; {ev} hendelser"
        else:
            scrape_meta = ""
            ev = 0
            src = 0

        # --- Pipeline metrics ---
        pipeline = pipeline_meta or {}
        source_count = pipeline.get("source_count", src)
        event_count = pipeline.get("total_events", ev)
        blocked = pipeline.get("blocked", [])
        blocked_count = len(blocked)
        blocked_names = ""
        if blocked:
            blocked_names = ": " + ", ".join(blocked)
        date_range = pipeline.get("date_range", f"{_fmt_date(plan.start_date)} &ndash; {_fmt_date(plan.end_date)}" if plan.start_date else "")
        scrape_age = pipeline.get("scrape_age", "")
        scrape_age_html = ""
        if scrape_age:
            scrape_age_html = f'<div class="metrics-group"><span class="metrics-group-label">Data-alder</span><span class="metrics-group-value">{scrape_age}</span></div>'

        fairness_gate_html = self._fairness_gate_html(plan.fairness_gate)
        review_summary_html = self._review_summary_html(plan)
        fairness_adjustments_html = self._fairness_adjustments_html(plan)

        # --- Header export download links ---
        export_links_html = ""
        if output_files:
            links_parts = ['<div class="export-links">']
            link_defs = [
                ("excel", _ICON_DOWNLOAD + " Last ned Excel (.xlsx)", "#38bdf8"),
                ("csv_overview", _ICON_BAR_CHART + " Last ned CSV", "#34d399"),
                ("csv_games", _ICON_FILE_SPREADSHEET + " Last ned CSV (kamper)", "#fbbf24"),
                ("ical", _ICON_CALENDAR + " Last ned iCal (.ics)", "#f87171"),
            ]
            for key, label, color in link_defs:
                if key in output_files:
                    filename = Path(output_files[key]).name
                    links_parts.append(
                        f'<a href="{filename}" class="export-link-btn" '
                        f'style="--link-color:{color}" download>{label}</a>'
                    )
            links_parts.append('</div>')
            export_links_html = "".join(links_parts)

        # --- Assemble pages from fragments ---
        calendars_href = "calendars.html"
        season_plan_href = "season_plan.html"
        report_href = "season_plan_report.html"

        def _render_page(*, page_title: str, page_subtitle: str, include_diagnostics: bool, include_timeline: bool, active_page: str) -> str:
            parts = {
                "$STYLES$": STYLES_CSS,
                "$NAVBAR$": NAVBAR,
                "$HEADER$": HEADER,
                "$SCORES$": SCORES if include_diagnostics else "",
                "$METRICS$": METRICS if include_diagnostics else "",
                "$FAIRNESS_ADJUSTMENTS$": fairness_adjustments_html if include_diagnostics else "",
                "$REVIEW_SUMMARY$": review_summary_html if include_diagnostics else "",
                "$EXPORT_LINKS$": export_links_html,
                "$CLUB_DASHBOARD$": CLUB_DASHBOARD if include_diagnostics else "",
                "$TEAM_STATS$": TEAM_STATS if include_diagnostics else "",
                "$TRAVEL_STATS$": TRAVEL_STATS if include_diagnostics else "",
                "$HEATMAP$": HEATMAP if include_diagnostics else "",
                "$FILTERS$": FILTERS if include_timeline else "",
                "$COUNT_BAR$": COUNT_BAR if include_timeline else "",
                "$TIMELINE$": '<div class="timeline" id="timeline"></div>' if include_timeline else "",
                "$SCRIPT$": JAVASCRIPT,
            }

            replacements = {
                "$ICON_CALENDAR$": _ICON_CALENDAR,
                "$ICON_CLIPBOARD$": _ICON_CLIPBOARD,
                "$ICON_USERS$": _ICON_USERS,
                "$ICON_TARGET$": _ICON_TARGET,
                "$ICON_TRAVEL$": _ICON_TRAVEL,
                "$ICON_WARNING$": _ICON_WARNING,
                "$ICON_BAR_CHART$": _ICON_BAR_CHART,
                "$CALENDARS_HREF$": calendars_href,
                "$SEASON_PLAN_HREF$": season_plan_href,
                "$REPORT_HREF$": report_href,
                "$CALENDARS_ACTIVE$": "active" if active_page == "calendars" else "",
                "$SEASON_PLAN_ACTIVE$": "active" if active_page == "season" else "",
                "$REPORT_ACTIVE$": "active" if active_page == "report" else "",
                "$PAGE_TITLE$": page_title,
                "$PAGE_SUBTITLE$": page_subtitle,
                "$SEASON_LABEL$": season_label,
                "$SCRAPE_META$": scrape_meta,
                "$AGE_GROUPS$": " + ".join(display_age_groups),
                "$TOURNAMENT_COUNT$": str(len(plan.tournaments)),
                "$GAME_COUNT$": str(sum(len(t.games) for t in plan.tournaments)),
                "$UNIQUE_TEAMS$": str(len(all_teams)),
                "$TEAM_COUNT$": str(len(team_game_counts)),
                "$GAME_COUNT_SPREAD$": (
                    f"{max(team_game_counts.values()) - min(team_game_counts.values())} spread"
                    if team_game_counts else "-"
                ),
                "$SOURCE_COUNT$": str(source_count),
                "$EVENT_COUNT$": str(event_count),
                "$BLOCKED_COUNT$": str(blocked_count),
                "$BLOCKED_NAMES$": blocked_names,
                "$DATE_RANGE$": date_range,
                "$TOTAL_TRAVEL_KM$": str(total_travel_km),
                "$SCRAPE_AGE_HTML$": scrape_age_html,
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
                "$FAIRNESS_GATE_SCORE$": str(int((plan.fairness_gate.get("score", 0) if isinstance(plan.fairness_gate, dict) else 0))),
                "$FAIRNESS_GATE_STATUS$": str((plan.fairness_gate.get("status", "pass") if isinstance(plan.fairness_gate, dict) else "pass")),
                "$FAIRNESS_GATE_STATUS_LABEL$": str({"pass": "PASS", "warn": "VARSEL", "fail": "FEIL"}.get(plan.fairness_gate.get("status", "pass") if isinstance(plan.fairness_gate, dict) else "pass", "PASS")),
                "$FAIRNESS_GATE_HTML$": fairness_gate_html,
                "$AGE_GROUP_OPTIONS$": age_group_options,
                "$TOURNAMENTS_JSON$": tournaments_json,
            }

            html = PAGE_TEMPLATE
            for part_key, part_value in parts.items():
                html = html.replace(part_key, part_value)
            for marker, value in replacements.items():
                html = html.replace(marker, value)
            return html

        schedule_html = _render_page(
            page_title="Sesongplan",
            page_subtitle=f"RVV Hockey &mdash; {' + '.join(display_age_groups)}",
            include_diagnostics=False,
            include_timeline=True,
            active_page="season",
        )
        report_html = _render_page(
            page_title="Sesongrapport",
            page_subtitle=f"RVV Hockey &mdash; {' + '.join(display_age_groups)} &middot; diagnostikk",
            include_diagnostics=True,
            include_timeline=False,
            active_page="report",
        )
        report_html = self._strip_schedule_controls(report_html)

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(schedule_html, encoding="utf-8")
        report_dest = dest.with_name(f"{dest.stem}_report{dest.suffix}")
        report_dest.write_text(report_html, encoding="utf-8")
        return str(dest)

    @staticmethod
    def _strip_schedule_controls(html: str) -> str:
        """Remove schedule-only filter and count-bar fragments from report pages."""
        html = re.sub(r"\n?\s*<!-- Filters -->\s*<div class=\"filters\">.*?</div>\s*", "\n", html, flags=re.S)
        html = re.sub(r"\n?\s*<!-- Count bar -->\s*<div class=\"count-bar\">.*?</div>\s*", "\n", html, flags=re.S)
        html = re.sub(r"\n{3,}", "\n\n", html)
        return html

    @staticmethod
    def _plan_to_json(plan: SeasonPlan, round_length_for_age_group: dict[str, int] | None = None) -> str:
        """Serialize the plan's tournaments to the compact JSON format used by the HTML."""
        round_length_for_age_group = round_length_for_age_group or {}
        data = []
        for t in plan.tournaments:
            games = [
                [g.home.label, g.away.label, g.parallel_slot, g.round_number]
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
            if t.start_time:
                entry["ts"] = t.start_time
                round_length = round_length_for_age_group.get(t.age_group)
                if round_length:
                    end_time = t.end_time(round_length)
                    if end_time:
                        entry["te"] = end_time
            if t.cancelled:
                entry["cx"] = True
                entry["cr"] = t.cancellation_reason or ""
            data.append(entry)
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _review_summary_html(plan: SeasonPlan) -> str:
        """Render the advisory final review summary."""
        sorted_tournaments = [t for t in plan.tournaments if not t.cancelled and t.date]
        sorted_tournaments.sort(key=lambda t: (t.date, t.arena, t.age_group))

        findings: list[tuple[str, str, str]] = []

        # Clumping — weekends with more tournaments than the seasonal average.
        week_counts: dict[tuple[int, int], int] = {}
        for tournament in sorted_tournaments:
            iso_year, iso_week, _ = tournament.date.isocalendar()
            week_counts[(iso_year, iso_week)] = week_counts.get((iso_year, iso_week), 0) + 1
        if week_counts:
            busiest_week, busiest_count = max(week_counts.items(), key=lambda item: (item[1], item[0]))
            avg_week = sum(week_counts.values()) / len(week_counts)
            if busiest_count >= 2 and (busiest_count >= 3 or busiest_count > avg_week * 1.25):
                findings.append(
                    (
                        "warn",
                        "Klynge",
                        f"Uke {busiest_week[0]}-W{busiest_week[1]:02d} har {busiest_count} turneringer, over snittet på {avg_week:.1f}.",
                    )
                )
            else:
                findings.append(("pass", "Klynge", "Ingen tydelig ukeklynge funnet."))
        else:
            findings.append(("pass", "Klynge", "Ingen turneringer å vurdere."))

        # Missing clubs — RVV clubs without a hosted tournament.
        host_counts: dict[str, int] = {}
        host_sequence: list[str] = []
        for tournament in sorted_tournaments:
            host = tournament.host_club or ""
            if not host:
                continue
            host_counts[host] = host_counts.get(host, 0) + 1
            host_sequence.append(host)
        missing_hosts = [club for club in _RVV_CLUBS if club not in host_counts]
        if missing_hosts:
            findings.append(
                (
                    "warn",
                    "Manglende klubber",
                    f"Følgende RVV-klubber har ingen vertsturnering: {', '.join(missing_hosts)}.",
                )
            )
        else:
            findings.append(("pass", "Manglende klubber", "Alle 9 RVV-klubber har minst én vertsturnering."))

        # Strange host patterns — concentration or long runs at the same host.
        if host_counts:
            top_host, top_count = max(host_counts.items(), key=lambda item: (item[1], item[0]))
            total_hosted = sum(host_counts.values())
            top_share = top_count / total_hosted if total_hosted else 0.0
            longest_run = 1
            current_host = ""
            current_run = 0
            for host in host_sequence:
                if host == current_host:
                    current_run += 1
                else:
                    current_host = host
                    current_run = 1
                longest_run = max(longest_run, current_run)
            if longest_run >= 3 or (top_count >= 3 and top_share >= 0.4):
                findings.append(
                    (
                        "warn",
                        "Vertsmønster",
                        f"{top_host} står for {top_count} av {total_hosted} vertsturneringer; vurder jevnere fordeling.",
                    )
                )
            else:
                findings.append(("pass", "Vertsmønster", "Vertsmønsteret ser jevnt ut."))
        else:
            findings.append(("pass", "Vertsmønster", "Ingen vertsklubber å vurdere."))

        # Suspicious outliers — unusually high or low per-team game counts.
        team_counts = plan.team_game_counts or {}
        if team_counts:
            max_team, max_games = max(team_counts.items(), key=lambda item: (item[1], item[0]))
            min_team, min_games = min(team_counts.items(), key=lambda item: (item[1], item[0]))
            avg_games = sum(team_counts.values()) / len(team_counts)
            spread = max_games - min_games
            if spread >= 5 or (avg_games and max_games > avg_games * 1.35):
                findings.append(
                    (
                        "warn",
                        "Avvik",
                        f"{max_team} har {max_games} kamper, mens {min_team} har {min_games} (spredning {spread}).",
                    )
                )
            else:
                findings.append(("pass", "Avvik", "Ingen tydelige kampantallsavvik funnet."))
        else:
            findings.append(("pass", "Avvik", "Ingen per-lag kampdata å vurdere."))

        status = "warn" if any(severity != "pass" for severity, _, _ in findings) else "pass"
        status_label = {"pass": "PASS", "warn": "VARSEL"}.get(status, "PASS")
        items_html = "".join(
            (
                f'<div class="review-summary-item review-summary-item--{severity}">'
                f'<div class="review-summary-item-label">{_html.escape(label)}</div>'
                f'<div class="review-summary-item-text">{_html.escape(text)}</div>'
                "</div>"
            )
            for severity, label, text in findings
        )
        return (
            REVIEW_SUMMARY.replace("$REVIEW_STATUS$", status)
            .replace("$REVIEW_STATUS_LABEL$", status_label)
            .replace("$REVIEW_ITEMS$", items_html)
        )

    @staticmethod
    def _fairness_gate_html(fairness_gate: dict[str, Any] | None) -> str:
        """Render the fairness gate summary and metric cards."""
        if not fairness_gate or not isinstance(fairness_gate, dict):
            return ""

        metrics = fairness_gate.get("metrics", [])
        if not metrics:
            return ""

        status = str(fairness_gate.get("status", "pass")).lower()
        score = int(fairness_gate.get("score", 0) or 0)
        status_labels = {"pass": "PASS", "warn": "VARSEL", "fail": "FEIL"}
        status_label = status_labels.get(status, "PASS")

        metric_cards = []
        for metric in metrics:
            metric_status = str(metric.get("status", "pass")).lower()
            metric_label = _html.escape(str(metric.get("label", "")))
            value = metric.get("value", "")
            threshold = metric.get("threshold", "")
            unit = str(metric.get("unit", ""))
            if unit and value != "":
                value = f"{value} {unit}"
            if unit and threshold != "":
                threshold = f"{threshold} {unit}"
            metric_cards.append(
                f"<div class=\"fairness-metric fairness-metric--{metric_status}\">"
                "<div class=\"fairness-metric-head\">"
                f"<span class=\"fairness-metric-label\">{metric_label}</span>"
                f"<span class=\"fairness-metric-status fairness-metric-status--{metric_status}\">{status_labels.get(metric_status, metric_status.upper())}</span>"
                "</div>"
                f"<div class=\"fairness-metric-value\"><strong>{_html.escape(str(value))}</strong> · terskel {_html.escape(str(threshold))}</div>"
                f"<div class=\"fairness-metric-score\">Score {int(metric.get('score', 0) or 0)}%</div>"
                f"<div class=\"fairness-metric-detail\">{_html.escape(str(metric.get('detail', '')))}</div>"
                "</div>"
            )

        return (
            '<div class="fairness-gate-panel">'
            '<div class="fairness-gate-head">'
            '<div>'
            '<div class="metrics-group-label">Rettferdighetskontroll</div>'
            f'<div class="metrics-group-value"><strong>{score}%</strong> · {status_label}</div>'
            '</div>'
            f'<span class="fairness-gate-status fairness-gate-status--{status}">{status_label}</span>'
            '</div>'
            f'<div class="fairness-gate-grid">{"".join(metric_cards)}</div>'
            '</div>'
        )

    @staticmethod
    def _fairness_adjustments_html(plan: SeasonPlan) -> str:
        """Render the fairness adjustment overview table."""
        rows = SeasonFairnessModel().adjustment_rows_for_plan(plan)
        if not rows:
            return ""

        total_abs = sum(abs(float(row.get("adjustment", 0.0))) for row in rows)
        avg_abs = total_abs / len(rows)
        max_row = rows[0]
        under_count = sum(1 for row in rows if str(row.get("status", "")) == "under")
        over_count = sum(1 for row in rows if str(row.get("status", "")) == "over")

        def fmt(value: float) -> str:
            return f"{value:+.1f}".replace(".", ",")

        summary = (
            '<div class="fairness-adjustment-summary">'
            f'<div class="metrics-group"><span class="metrics-group-label">Lag med positiv rettferdighetsjustering</span><span class="metrics-group-value"><strong>{under_count}</strong></span></div>'
            f'<div class="metrics-group"><span class="metrics-group-label">Lag over mål</span><span class="metrics-group-value"><strong>{over_count}</strong></span></div>'
            f'<div class="metrics-group"><span class="metrics-group-label">Snitt absolutt avvik</span><span class="metrics-group-value"><strong>{fmt(avg_abs)}</strong></span></div>'
            f'<div class="metrics-group"><span class="metrics-group-label">Største avvik</span><span class="metrics-group-value"><strong>{_html.escape(str(max_row["label"]))}</strong> {fmt(abs(float(max_row["adjustment"])))}</span></div>'
            '</div>'
        )

        status_labels = {"under": "UNDER MÅL", "over": "OVER MÅL", "on_target": "PÅ MÅL"}
        table_rows = []
        for row in rows:
            status = str(row.get("status", ""))
            adj = float(row.get("adjustment", 0.0))
            table_rows.append(
                '<tr class="fairness-adjustment-row fairness-adjustment-row--' + _html.escape(status) + '">' 
                f'<td>{_html.escape(str(row.get("label", "")))}</td>'
                f'<td>{_html.escape(str(row.get("club", "")))}</td>'
                f'<td>{_html.escape(str(row.get("age_group", "")))}</td>'
                f'<td style="text-align:right">{int(row.get("actual", 0))}</td>'
                f'<td style="text-align:right">{fmt(float(row.get("target", 0.0)))}</td>'
                f'<td class="fairness-adjustment-adjustment fairness-adjustment-adjustment--{_html.escape(status)}" style="text-align:right">{fmt(adj)}</td>'
                f'<td>{status_labels.get(status, status.upper())}</td>'
                f'<td>{"Mangler flere kamper" if adj > 0.5 else ("For mange kamper" if adj < -0.5 else "På mål")}</td>'
                '</tr>'
            )

        return (
            '<section class="fairness-adjustment-panel">'
            '<div class="fairness-adjustment-head">'
            '<div>'
            '<div class="metrics-group-label">Rettferdighetsjusteringer</div>'
            '<div class="metrics-group-value">Forskjell mellom faktisk kampantall og rettferdighetsmål</div>'
            '</div>'
            f'<span class="fairness-gate-status fairness-gate-status--warn">{len(rows)} lag</span>'
            '</div>'
            f'{summary}'
            '<table class="fairness-adjustment-table">'
            '<thead><tr>'
            '<th>Lag</th><th>Klubb</th><th>Aldersgruppe</th><th>Faktisk</th><th>Mål</th><th>Justering</th><th>Status</th><th>Kommentar</th>'
            '</tr></thead><tbody>'
            f'{"".join(table_rows)}'
            '</tbody></table>'
            '</section>'
        )


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


def _fmt_date(d: Any) -> str:
    if d is None:
        return "?"
    return d.strftime("%d.%m.%Y") if hasattr(d, "strftime") else str(d)


def _age_string(iso_str: str) -> str:
    if not iso_str:
        return ""
    from datetime import datetime as _dt
    try:
        dt = _dt.fromisoformat(iso_str)
        delta = _dt.now() - dt
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s siden"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() // 60)}m siden"
        if delta.days < 1:
            return f"{int(delta.total_seconds() // 3600)}t siden"
        return f"{delta.days}d siden"
    except (ValueError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys
    from ..pipeline.state import PipelineState, StageName

    parser = argparse.ArgumentParser(description="Generer interaktiv HTML-oversikt over sesongplanen")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    parser.add_argument("--output", default="export/season_plan.html", help="Output HTML path")
    args = parser.parse_args()

    state = PipelineState(args.work_dir)
    plan_ckpt = state.read_stage(StageName.PLANNING)
    if not plan_ckpt or "plan" not in plan_ckpt:
        print("Fant ikke Stage 3-planen - kj\u00f8r Stage 3 f\u00f8rst.", file=sys.stderr)
        sys.exit(1)

    from ..pipeline.stage4_export import _dict_to_plan
    plan = _dict_to_plan(plan_ckpt["plan"])

    exporter = HtmlExporter()
    path = exporter.export(plan, args.output)
    print(f"HTML generert: {path}")
