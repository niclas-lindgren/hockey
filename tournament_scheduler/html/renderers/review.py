"""Advisory final review summary for the season-plan report page.

Extracted from ``HtmlExporter._review_summary_html``.
"""

from __future__ import annotations

import html as _html

from tournament_scheduler.models import team_key as _team_key

from ..data_computation import (
    _RVV_CLUBS,
    canonical_rvv_club_name,
)
from ..templates import REVIEW_SUMMARY

_OVERLAPPING_TOPICS = {
    "missing_hosts",
    "age_group_host_summaries",
    "age_spread_summaries",
    "host_pattern",
    "game_spread",
}


def analyze_review_summary(plan: object) -> dict[str, object]:
    """Return the advisory review findings as structured data."""
    tournaments = getattr(plan, "tournaments", [])
    team_game_counts = getattr(plan, "team_game_counts", None) or {}
    skipped_age_groups = getattr(plan, "skipped_age_groups", None) or []

    sorted_tournaments = [t for t in tournaments if not getattr(t, "cancelled", False) and getattr(t, "date", None)]
    sorted_tournaments.sort(key=lambda t: (getattr(t, "date", None), getattr(t, "arena", ""), getattr(t, "age_group", "")))

    # Build the same duplicate-label set used by compute_team_game_counts so that
    # team_key() lookups against team_game_counts resolve to the correct keys.
    _label_to_identities: dict[str, set[tuple[str, str]]] = {}
    for _t in tournaments:
        for _team in getattr(_t, "teams", []):
            _identity = (getattr(_team, "club", ""), getattr(_team, "age_group", ""))
            _label_to_identities.setdefault(_team.label, set()).add(_identity)
    _plan_duplicate_labels = {lbl for lbl, ids in _label_to_identities.items() if len(ids) > 1}

    findings: list[dict[str, object]] = []

    def _add_finding(topic: str, severity: str, label: str, text: str) -> None:
        findings.append(
            {
                "topic": topic,
                "severity": severity,
                "label": label,
                "text": text,
                "overlap": topic in _OVERLAPPING_TOPICS,
            }
        )

    # Clumping — weekends with more tournaments than the seasonal average.
    week_counts: dict[tuple[int, int], int] = {}
    for tournament in sorted_tournaments:
        iso_year, iso_week, _ = getattr(tournament, "date").isocalendar()
        week_counts[(iso_year, iso_week)] = week_counts.get((iso_year, iso_week), 0) + 1
    if week_counts:
        busiest_week, busiest_count = max(week_counts.items(), key=lambda item: (item[1], item[0]))
        avg_week = sum(week_counts.values()) / len(week_counts)
        if busiest_count >= 2 and (busiest_count >= 3 or busiest_count > avg_week * 1.25):
            _add_finding(
                "clumping",
                "warn",
                "Klynge",
                f"Uke {busiest_week[0]}-W{busiest_week[1]:02d} har {busiest_count} turneringer, over snittet på {avg_week:.1f}.",
            )
        else:
            _add_finding("clumping", "pass", "Klynge", "Ingen tydelig ukeklynge funnet.")
    else:
        _add_finding("clumping", "pass", "Klynge", "Ingen turneringer å vurdere.")

    # Missing clubs — RVV clubs without a hosted tournament.
    host_counts: dict[str, int] = {}
    host_sequence: list[str] = []
    tournaments_by_age: dict[str, list[object]] = {}
    team_clubs = sorted(
        {
            canonical_rvv_club_name(team.club)
            for tournament in sorted_tournaments
            for team in getattr(tournament, "teams", [])
            if getattr(team, "club", None)
        }
    )
    for tournament in sorted_tournaments:
        age_group = str(getattr(tournament, "age_group", "") or "")
        tournaments_by_age.setdefault(age_group, []).append(tournament)
        host = getattr(tournament, "host_club", None) or ""
        if not host:
            continue
        canonical_host = canonical_rvv_club_name(host)
        host_counts[canonical_host] = host_counts.get(canonical_host, 0) + 1
        host_sequence.append(canonical_host)
    age_host_summaries: list[str] = []
    age_spread_summaries: list[str] = []
    for age_group, age_tournaments in sorted(tournaments_by_age.items()):
        age_hosts: dict[str, int] = {}
        age_team_objs = list({id(team): team for tournament in age_tournaments for team in getattr(tournament, "teams", [])}.values())
        age_counts = [team_game_counts.get(_team_key(team, _plan_duplicate_labels), 0) for team in age_team_objs]
        if age_counts:
            age_spread_summaries.append(f"{age_group} {min(age_counts)}–{max(age_counts)}")
        for tournament in age_tournaments:
            host = getattr(tournament, "host_club", None) or ""
            if not host:
                continue
            canonical_host = canonical_rvv_club_name(host)
            age_hosts[canonical_host] = age_hosts.get(canonical_host, 0) + 1
        if age_hosts:
            top_age_host, top_age_host_count = max(age_hosts.items(), key=lambda item: (item[1], item[0]))
            age_host_summaries.append(f"{age_group}: {top_age_host} {top_age_host_count}/{len(age_tournaments)}")
    missing_hosts = [club for club in _RVV_CLUBS if club not in host_counts]

    def _missing_host_label(club: str) -> str:
        return f"{club} (ingen lag i planen)" if club not in team_clubs else club

    if missing_hosts:
        _add_finding(
            "missing_hosts",
            "warn",
            "Manglende klubber",
            f"Følgende RVV-klubber har ingen hjemmeturnering: {', '.join(_missing_host_label(club) for club in missing_hosts)}.",
        )
    else:
        _add_finding("missing_hosts", "pass", "Manglende klubber", "Alle 9 RVV-klubber har minst én hjemmeturnering.")
    if age_host_summaries:
        _add_finding("age_group_host_summaries", "info", "Hjemmeturneringer per aldersgruppe", f"Fordeling: {', '.join(age_host_summaries[:4])}.")
    if age_spread_summaries:
        _add_finding("age_spread_summaries", "info", "Kampbredde per aldersgruppe", f"Spredning: {', '.join(age_spread_summaries[:4])}.")

    # Skipped age groups — <3-team age groups that were not planned.
    if skipped_age_groups:
        items = "; ".join(
            f"{entry['age_group']} ({entry['team_count']} lag: {entry['reason']})"
            for entry in skipped_age_groups
        )
        _add_finding("skipped_age_groups", "info", "Hoppet over", items)

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
            _add_finding(
                "host_pattern",
                "warn",
                "Vertsmønster",
                f"{top_host} står for {top_count} av {total_hosted} hjemmeturneringer; vurder jevnere fordeling.",
            )
        else:
            _add_finding("host_pattern", "pass", "Vertsmønster", "Vertsmønsteret ser jevnt ut.")
    else:
        _add_finding("host_pattern", "pass", "Vertsmønster", "Ingen vertsklubber å vurdere.")

    # Arena/day collisions — same hall booked twice on the same date.
    arena_day_collisions = getattr(plan, "arena_day_collisions", None) or []
    if arena_day_collisions:
        examples = "; ".join(
            f"{entry.get('date')} {entry.get('arena')}: {entry.get('age_group')} vs {entry.get('conflicting_age_group')}"
            for entry in arena_day_collisions[:3]
            if isinstance(entry, dict)
        )
        _add_finding(
            "arena_day_collisions",
            "warn",
            "Arena-/dagskollisjoner",
            f"{len(arena_day_collisions)} kollisjon(er): {examples}.",
        )
    else:
        _add_finding(
            "arena_day_collisions",
            "pass",
            "Arena-/dagskollisjoner",
            "Ingen samme-arena-samme-dag-kollisjoner funnet.",
        )

    # Suspicious outliers — unusually high or low per-team game counts.
    if team_game_counts:
        max_team, max_games = max(team_game_counts.items(), key=lambda item: (item[1], item[0]))
        min_team, min_games = min(team_game_counts.items(), key=lambda item: (item[1], item[0]))
        avg_games = sum(team_game_counts.values()) / len(team_game_counts)
        spread = max_games - min_games
        if spread >= 5 or (avg_games and max_games > avg_games * 1.35):
            _add_finding(
                "game_spread",
                "warn",
                "Avvik",
                f"{max_team} har {max_games} kamper, mens {min_team} har {min_games} (spredning {spread}).",
            )
        else:
            _add_finding("game_spread", "pass", "Avvik", "Ingen tydelige kampantallsavvik funnet.")
    else:
        _add_finding("game_spread", "pass", "Avvik", "Ingen per-lag kampdata å vurdere.")

    status = "warn" if any(f["severity"] not in ("pass", "info") for f in findings) else "pass"
    status_label = {"pass": "PASS", "warn": "VARSEL"}.get(status, "PASS")
    unique_non_pass_findings = [f for f in findings if f["severity"] not in ("pass", "info") and not f["overlap"]]
    return {
        "status": status,
        "status_label": status_label,
        "findings": findings,
        "unique_non_pass_findings": unique_non_pass_findings,
        "has_unique_findings": bool(unique_non_pass_findings),
    }


def render_review_summary_html(plan: object, *, compact: bool = False) -> str:
    """Render the advisory final review summary section."""
    analysis = analyze_review_summary(plan)
    findings = list(analysis["findings"])

    if compact and not analysis["has_unique_findings"]:
        compact_finding = next((f for f in findings if f["label"] == "Manglende klubber"), findings[0] if findings else None)
        compact_items = ""
        if compact_finding:
            compact_items = (
                '<div class="review-summary-item review-summary-item--compact">'
                f'<div class="review-summary-item-label">{_html.escape(str(compact_finding["label"]))}</div>'
                f'<div class="review-summary-item-text">{_html.escape(str(compact_finding["text"]))}</div>'
                '</div>'
            )
        return (
            '<section class="review-summary-panel review-summary-panel--compact" id="reviewSummary">'
            '<div class="review-summary-head">'
            '<div>'
            '<div class="metrics-group-label">Rådgivende kontroll</div>'
            '<div class="metrics-group-value">Kortversjon av kontrollen — de øvrige punktene er allerede omtalt over.</div>'
            '</div>'
            '<span class="fairness-gate-status fairness-gate-status--pass">PASS</span>'
            '</div>'
            f'<div class="review-summary-items">{compact_items}</div>'
            '</section>'
        )

    items_html = "".join(
        (
            f'<div class="review-summary-item review-summary-item--{_html.escape(str(finding["severity"]))}">'
            f'<div class="review-summary-item-label">{_html.escape(str(finding["label"]))}</div>'
            f'<div class="review-summary-item-text">{_html.escape(str(finding["text"]))}</div>'
            "</div>"
        )
        for finding in findings
    )
    return (
        REVIEW_SUMMARY.replace("$REVIEW_STATUS$", str(analysis["status"]))
        .replace("$REVIEW_STATUS_LABEL$", str(analysis["status_label"]))
        .replace("$REVIEW_ITEMS$", items_html)
    )
