"""Interactive HTML overview for the season plan.

Reads a :class:`~tournament_scheduler.models.SeasonPlan` and generates a
standalone, interactive HTML page showing all tournaments, filtering by
age group / arena / club / search, and expandable match tables.

HTML is assembled from template fragments in ``templates/``.
Data computation lives in :mod:`data_computation`; rendering helpers
live in :mod:`renderers`.
"""

from __future__ import annotations

import html as _html
import json
import os
import re
from pathlib import Path
from typing import Any

from tournament_scheduler.club_distances import furthest_traveling_team
from ..models import SeasonPlan

from .data_computation import (
    ICON_CALENDAR,
    ICON_CLIPBOARD,
    ICON_USERS,
    ICON_TARGET,
    ICON_TRAVEL,
    ICON_WARNING,
    ICON_BAR_CHART,
    ICON_FILE_SPREADSHEET,
    ICON_CLOCK,
    _RVV_CLUBS,
    _CLUB_ALIASES,
    canonical_rvv_club_name,
    season_label,
    fmt_date,
    age_string,
    compute_team_game_counts,
    compute_team_travel_info,
    compute_heatmap_data,
    compute_club_stats,
    build_export_links_html,
    compute_display_age_groups,
)
from .renderers.fairness import (
    render_fairness_gate_html,
    render_fairness_adjustments_html,
)
from .renderers.review import render_review_summary_html
from .renderers.heatmap import build_club_color_maps

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
    REPORT_OVERVIEW,
    PAGE_TEMPLATE,
    SHARED_JAVASCRIPT,
    SCHEDULE_JAVASCRIPT,
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
        team_game_counts = compute_team_game_counts(plan)
        team_game_counts_json = json.dumps(team_game_counts, ensure_ascii=False)

        # Travel info
        team_travel, most_travel_team, most_travel_km, total_travel_km, travel_count_estimate_html = (
            compute_team_travel_info(plan)
        )
        team_travel_json = json.dumps(team_travel, ensure_ascii=False)

        # Heatmap data
        heatmap, heatmap_weeks, heatmap_clubs = compute_heatmap_data(plan)
        heatmap_json = json.dumps(heatmap, ensure_ascii=False)
        heatmap_weeks_json = json.dumps(heatmap_weeks, ensure_ascii=False)
        heatmap_clubs_json = json.dumps(heatmap_clubs, ensure_ascii=False)

        # Club colours
        club_color_maps = build_club_color_maps(heatmap_clubs)
        heatmap_club_colors_json = json.dumps(club_color_maps, ensure_ascii=False)

        # Club stats
        club_stats, all_clubs_list = compute_club_stats(plan, team_travel)
        club_stats_json = json.dumps(club_stats, ensure_ascii=False)
        all_clubs_json = json.dumps(all_clubs_list, ensure_ascii=False)

        season_label_str = season_label(plan)
        display_age_groups = compute_display_age_groups(plan, age_groups)
        age_group_options = "".join(
            f'<option value="{ag}">{ag}</option>'
            for ag in display_age_groups
        )

        # Scrape metadata for navbar
        if meta:
            ev = meta.get("total_events", 0)
            src = meta.get("source_count", 0)
            ts = meta.get("updated_at", "")
            age = age_string(ts)
            scrape_meta = f"{src} kilder &middot; {ev} hendelser &middot; {age}" if age else f"{src} kilder &middot; {ev} hendelser"
        else:
            scrape_meta = ""
            ev = 0
            src = 0

        # Pipeline metrics
        pipeline = pipeline_meta or {}
        source_count = pipeline.get("source_count", src)
        event_count = pipeline.get("total_events", ev)
        blocked = pipeline.get("blocked", [])
        blocked_count = len(blocked)
        blocked_names = ""
        if blocked:
            blocked_names = ": " + ", ".join(blocked)
        date_range = pipeline.get("date_range", f"{fmt_date(plan.start_date)} &ndash; {fmt_date(plan.end_date)}" if plan.start_date else "")
        scrape_age = pipeline.get("scrape_age", "")
        scrape_age_html = ""
        if scrape_age:
            scrape_age_html = f'<div class="metrics-group"><span class="metrics-group-label">Data-alder</span><span class="metrics-group-value">{scrape_age}</span></div>'

        # Render components
        fairness_gate_html = render_fairness_gate_html(
            plan.fairness_gate if isinstance(plan.fairness_gate, dict) else None
        )
        review_summary_html = render_review_summary_html(plan)
        fairness_adjustments_html = render_fairness_adjustments_html(plan)
        report_overview_html = self._report_overview_html(
            plan,
            source_count=source_count,
            event_count=event_count,
            blocked=blocked,
            date_range=date_range,
            display_age_groups=display_age_groups,
            team_game_counts=team_game_counts,
            club_stats=club_stats,
            team_travel=team_travel,
        )
        export_links_html = build_export_links_html(output_files)

        # Assemble pages from fragments
        calendars_href = "calendars.html"
        season_plan_href = "season_plan.html"
        report_href = "season_plan_report.html"

        def _render_page(*, page_title: str, page_subtitle: str, include_diagnostics: bool, include_timeline: bool, active_page: str) -> str:
            parts = {
                "$STYLES$": STYLES_CSS,
                "$NAVBAR$": NAVBAR,
                "$HEADER$": HEADER,
                "$REPORT_OVERVIEW$": report_overview_html if include_diagnostics else "",
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
                "$SCRIPT$": (
                    SHARED_JAVASCRIPT + ("\n" + SCHEDULE_JAVASCRIPT if include_timeline else "")
                ),
            }

            replacements = {
                "$ICON_CALENDAR$": ICON_CALENDAR,
                "$ICON_CLIPBOARD$": ICON_CLIPBOARD,
                "$ICON_USERS$": ICON_USERS,
                "$ICON_TARGET$": ICON_TARGET,
                "$ICON_TRAVEL$": ICON_TRAVEL,
                "$ICON_WARNING$": ICON_WARNING,
                "$ICON_BAR_CHART$": ICON_BAR_CHART,
                "$CALENDARS_HREF$": calendars_href,
                "$SEASON_PLAN_HREF$": season_plan_href,
                "$REPORT_HREF$": report_href,
                "$CALENDARS_ACTIVE$": "active" if active_page == "calendars" else "",
                "$SEASON_PLAN_ACTIVE$": "active" if active_page == "season" else "",
                "$REPORT_ACTIVE$": "active" if active_page == "report" else "",
                "$PAGE_TITLE$": page_title,
                "$PAGE_SUBTITLE$": page_subtitle,
                "$SEASON_LABEL$": season_label_str,
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
    def _report_overview_html(
        plan: SeasonPlan,
        *,
        source_count: int,
        event_count: int,
        blocked: list[str],
        date_range: str,
        display_age_groups: list[str],
        team_game_counts: dict[str, int],
        club_stats: dict[str, dict[str, object]],
        team_travel: dict[str, int],
    ) -> str:
        """Render the organizer-first report overview above raw diagnostics."""
        gate = plan.fairness_gate if isinstance(plan.fairness_gate, dict) else {}
        gate_status = str(gate.get("status", "pass"))
        status_rank = {"pass": 0, "warn": 1, "fail": 2}
        cancelled_count = sum(1 for tournament in plan.tournaments if tournament.cancelled)
        overall_status = gate_status if gate_status in status_rank else "pass"
        if blocked and status_rank[overall_status] < status_rank["warn"]:
            overall_status = "warn"
        if cancelled_count and status_rank[overall_status] < status_rank["warn"]:
            overall_status = "warn"

        status_labels = {"pass": "KLAR FOR GJENNOMGANG", "warn": "M\u00c5 SJEKKES", "fail": "KREVER ENDRING"}
        answer_by_status = {
            "pass": "Ja, planen ser brukbar ut for klubbvis gjennomgang.",
            "warn": "Nesten, men punktene under b\u00f8r sjekkes f\u00f8r planen sendes til klubbene.",
            "fail": "Ikke enn\u00e5. Planen har feil eller store avvik som b\u00f8r rettes f\u00f8rst.",
        }
        note_by_status = {
            "pass": "Start med klubb- og aldersgruppeoppsummeringene, og bruk detaljdiagnostikken nederst ved behov.",
            "warn": "Prioriter varsler og klubbpunkter f\u00f8r du vurderer om planen er god nok.",
            "fail": "Rett kritiske punkter, kj\u00f8r planlegging/eksport p\u00e5 nytt og kontroller rapporten igjen.",
        }

        active_tournaments = [t for t in plan.tournaments if not t.cancelled]
        active_tournaments.sort(key=lambda t: (t.date or plan.end_date, t.age_group, t.host_club or "", t.arena))
        host_counts: dict[str, int] = {}
        for tournament in active_tournaments:
            host = tournament.host_club or ""
            if host:
                canonical_host = canonical_rvv_club_name(host)
                host_counts[canonical_host] = host_counts.get(canonical_host, 0) + 1
        missing_hosts = [club for club in _RVV_CLUBS if club not in host_counts]

        metric_warnings = [m for m in gate.get("metrics", []) if isinstance(m, dict) and m.get("status") in {"warn", "fail"}]
        actions: list[tuple[str, str, str]] = []
        if gate_status in {"warn", "fail"}:
            actions.append((gate_status, "Rettferdighetskontroll", f"Samlet status er {status_labels.get(gate_status, gate_status).lower()} med score {gate.get('score', 0)}%."))
        for metric in metric_warnings[:4]:
            label = str(metric.get("label", "M\u00e5ltall"))
            detail = str(metric.get("detail", "Sjekk avviket f\u00f8r utsending."))
            actions.append((str(metric.get("status", "warn")), label, detail))
        if blocked:
            actions.append(("warn", "Datagrunnlag", f"{len(blocked)} kalenderkilde(r) er blokkert: {', '.join(blocked)}."))
        if missing_hosts:
            actions.append(("warn", "Vertskap", f"Ingen vertsturnering registrert for: {', '.join(missing_hosts)}."))
        if cancelled_count:
            actions.append(("warn", "Avlyst/hoppet over", f"{cancelled_count} turnering(er) er markert som avlyst eller hoppet over."))
        if not actions:
            actions.append(("pass", "Ingen kritiske handlinger", "G\u00e5 videre til aldersgrupper og klubboversikt for manuell kvalitetssjekk."))

        age_rows: list[str] = []
        for age_group in display_age_groups:
            tournaments = [t for t in active_tournaments if t.age_group == age_group]
            labels = sorted({team.label for tournament in tournaments for team in tournament.teams})
            hosts = sorted({canonical_rvv_club_name(t.host_club or "") for t in tournaments if t.host_club})
            game_counts = [team_game_counts.get(label, 0) for label in labels]
            spread = f"{min(game_counts)}\u2013{max(game_counts)}" if game_counts else "-"
            first_date = fmt_date(min((t.date for t in tournaments if t.date), default=None))
            last_date = fmt_date(max((t.date for t in tournaments if t.date), default=None))
            dates = f"{first_date} \u2013 {last_date}" if first_date and last_date and first_date != last_date else (first_date or "-")
            age_rows.append(
                "<tr>"
                f"<td><strong>{_html.escape(age_group)}</strong></td>"
                f"<td class=\"numeric-cell\">{len(tournaments)}</td>"
                f"<td class=\"numeric-cell\">{len(labels)}</td>"
                f"<td>{_html.escape(', '.join(hosts) or '-')}</td>"
                f"<td>{_html.escape(spread)}</td>"
                f"<td>{_html.escape(dates)}</td>"
                "</tr>"
            )
        if not age_rows:
            age_rows.append('<tr><td colspan="6" class="empty-cell">Ingen aldersgrupper i planen</td></tr>')

        club_rows: list[str] = []
        for club in sorted(club_stats):
            stats = club_stats[club]
            hosted = int(stats.get("hosted", 0) or 0)
            away = int(stats.get("away", 0) or 0)
            teams = int(stats.get("teams", 0) or 0)
            travel_km = int(stats.get("travel_km", 0) or 0)
            review_note = "Sjekk hjemmedatoer og lagliste"
            if hosted == 0:
                review_note = "Mangler vertskap i planen"
            elif travel_km > 0 and team_travel:
                review_note = "Sjekk reisebelastning og bortedatoer"
            club_rows.append(
                "<tr>"
                f"<td><strong>{_html.escape(club)}</strong></td>"
                f"<td class=\"numeric-cell\">{teams}</td>"
                f"<td class=\"numeric-cell\">{hosted}</td>"
                f"<td class=\"numeric-cell\">{away}</td>"
                f"<td class=\"numeric-cell\">{travel_km}</td>"
                f"<td>{_html.escape(review_note)}</td>"
                "</tr>"
            )
        if not club_rows:
            club_rows.append('<tr><td colspan="6" class="empty-cell">Ingen klubbdata tilgjengelig</td></tr>')

        tournament_rows: list[str] = []
        for tournament in active_tournaments[:120]:
            team_count = len(tournament.teams)
            tournament_rows.append(
                "<tr>"
                f"<td>{_html.escape(fmt_date(tournament.date) or '-')}</td>"
                f"<td><strong>{_html.escape(tournament.age_group)}</strong></td>"
                f"<td>{_html.escape(canonical_rvv_club_name(tournament.host_club or '-') or '-')}</td>"
                f"<td>{_html.escape(tournament.arena)}</td>"
                f"<td class=\"numeric-cell\">{team_count}</td>"
                f"<td class=\"numeric-cell\">{len(tournament.games)}</td>"
                "</tr>"
            )
        if len(active_tournaments) > 120:
            tournament_rows.append(f'<tr><td colspan="6" class="empty-cell">Viser 120 av {len(active_tournaments)} turneringer</td></tr>')
        if not tournament_rows:
            tournament_rows.append('<tr><td colspan="6" class="empty-cell">Ingen turneringer i planen</td></tr>')

        card_defs = [
            ("Planstatus", status_labels.get(overall_status, "STATUS"), f"{len(active_tournaments)} turneringer, {sum(len(t.games) for t in active_tournaments)} kamper"),
            ("Datagrunnlag", f"{source_count} kilder", f"{event_count} kalenderhendelser, {len(blocked)} blokkert"),
            ("Tidsrom", date_range or "Ikke oppgitt", f"{len(display_age_groups)} aldersgrupper"),
            ("Klubbfordeling", f"{len(host_counts)} vertsklubber", f"{len(missing_hosts)} RVV-klubber uten vertskap"),
        ]
        status_cards = "".join(
            '<article class="report-card">'
            f'<span>{_html.escape(label)}</span>'
            f'<strong>{_html.escape(value)}</strong>'
            f'<p>{_html.escape(note)}</p>'
            '</article>'
            for label, value, note in card_defs
        )
        actions_html = '<div class="report-action-list">' + "".join(
            f'<article class="report-action report-action--{_html.escape(status)}"><strong>{_html.escape(label)}</strong><p>{_html.escape(text)}</p></article>'
            for status, label, text in actions
        ) + '</div>'
        age_summary = (
            '<div class="table-wrap"><table class="report-table"><thead><tr>'
            '<th>Aldersgruppe</th><th>Turneringer</th><th>Lag</th><th>Vertsklubber</th><th>Kamper per lag</th><th>Datoer</th>'
            '</tr></thead><tbody>' + "".join(age_rows) + '</tbody></table></div>'
        )
        club_summary = (
            '<div class="table-wrap"><table class="report-table"><thead><tr>'
            '<th>Klubb</th><th>Lag</th><th>Hjemme</th><th>Borte</th><th>Reise (km)</th><th>Klubben b\u00f8r sjekke</th>'
            '</tr></thead><tbody>' + "".join(club_rows) + '</tbody></table></div>'
        )
        tournament_table = (
            '<div class="table-wrap"><table class="report-table"><thead><tr>'
            '<th>Dato</th><th>Aldersgruppe</th><th>Vert</th><th>Arena</th><th>Lag</th><th>Kamper</th>'
            '</tr></thead><tbody>' + "".join(tournament_rows) + '</tbody></table></div>'
        )

        replacements = {
            "$REPORT_STATUS$": overall_status,
            "$REPORT_STATUS_LABEL$": status_labels.get(overall_status, "STATUS"),
            "$REPORT_ANSWER$": answer_by_status.get(overall_status, answer_by_status["warn"]),
            "$REPORT_NOTE$": note_by_status.get(overall_status, note_by_status["warn"]),
            "$REPORT_STATUS_CARDS$": status_cards,
            "$REPORT_ACTIONS$": actions_html,
            "$REPORT_AGE_SUMMARY$": age_summary,
            "$REPORT_CLUB_SUMMARY$": club_summary,
            "$REPORT_TOURNAMENT_TABLE$": tournament_table,
        }
        html = REPORT_OVERVIEW
        for marker, value in replacements.items():
            html = html.replace(marker, value)
        return html

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
