"""Opinionated end-of-report judgment for the season-plan report page."""

from __future__ import annotations

import html as _html
from typing import Any

from ..data_computation import _RVV_CLUBS, canonical_rvv_club_name


def _score_tone(*, gate_status: str, gate_score: int, pairwise: float, diversity: float, month_balance: float, missing_hosts: list[str], spread: int) -> str:
    if gate_status == "fail" or gate_score < 70 or pairwise < 0.75 or spread >= 5:
        return "rough"
    if gate_status == "warn" or missing_hosts or pairwise < 0.9 or diversity < 0.9 or month_balance < 0.9 or spread >= 3:
        return "mixed"
    return "strong"


def analyze_opinionated_judgment(
    plan: object,
    *,
    team_game_counts: dict[str, int],
    club_stats: dict[str, dict[str, object]],
    team_travel: dict[str, int],
) -> dict[str, object]:
    """Return a structured opinionated synthesis of the plan."""
    tournaments = [t for t in getattr(plan, "tournaments", []) if not getattr(t, "cancelled", False)]
    fairness_gate = getattr(plan, "fairness_gate", {}) if isinstance(getattr(plan, "fairness_gate", {}), dict) else {}

    gate_status = str(fairness_gate.get("status", "pass")).lower()
    gate_score = int(fairness_gate.get("score", 0) or 0)
    pairwise = float(getattr(plan, "pairwise_matchup_score", 0.0) or 0.0)
    diversity = float(getattr(plan, "diversity_score", 0.0) or 0.0)
    month_balance = float(getattr(plan, "month_balance_score", 0.0) or 0.0)

    host_counts: dict[str, int] = {}
    for tournament in tournaments:
        host = canonical_rvv_club_name(getattr(tournament, "host_club", None) or "")
        if host:
            host_counts[host] = host_counts.get(host, 0) + 1
    missing_hosts = [club for club in _RVV_CLUBS if club not in host_counts]
    top_host = ""
    top_host_count = 0
    if host_counts:
        top_host, top_host_count = max(host_counts.items(), key=lambda item: (item[1], item[0]))
    total_hosted = sum(host_counts.values())
    top_host_share = top_host_count / total_hosted if total_hosted else 0.0

    counts = list(team_game_counts.values())
    spread = max(counts) - min(counts) if counts else 0
    max_team = ""
    max_games = 0
    min_team = ""
    min_games = 0
    if team_game_counts:
        max_team, max_games = max(team_game_counts.items(), key=lambda item: (item[1], item[0]))
        min_team, min_games = min(team_game_counts.items(), key=lambda item: (item[1], item[0]))

    farthest_team = ""
    farthest_km = 0
    if team_travel:
        farthest_team, farthest_km = max(team_travel.items(), key=lambda item: (item[1], item[0]))

    busiest_club = ""
    busiest_club_load = 0
    if club_stats:
        busiest_club, busiest_club_load = max(
            (
                (club, int(stats.get("hosted", 0) or 0) + int(stats.get("away", 0) or 0))
                for club, stats in club_stats.items()
            ),
            key=lambda item: (item[1], item[0]),
        )

    tone = _score_tone(
        gate_status=gate_status,
        gate_score=gate_score,
        pairwise=pairwise,
        diversity=diversity,
        month_balance=month_balance,
        missing_hosts=missing_hosts,
        spread=spread,
    )
    tone_label = {
        "strong": "SOLID",
        "mixed": "BLANDET",
        "rough": "IKKE KLAR",
    }[tone]

    if tone == "strong":
        verdict = "Dette er en plan jeg ville sendt videre: den er jevn, variert og uten tydelige røde flagg."
    elif tone == "mixed":
        verdict = "Dette er brukbart, men jeg ville ikke kalt planen ferdig før de tydeligste skjevhetene er sjekket en gang til."
    else:
        verdict = "Dette er ikke en plan jeg ville sendt ut ennå; den trenger mer arbeid før den kan forsvares som helhet."

    matchup_text = (
        f"Matchupene er {('sterke' if pairwise >= 0.9 and diversity >= 0.9 else 'greie' if pairwise >= 0.8 else 'for smale')}: "
        f"{int(round(pairwise * 100))}% nye paringer og {int(round(diversity * 100))}% dekning på tvers av motstandere."
    )
    if pairwise >= 0.9 and diversity >= 0.9:
        matchup_text += " Her har planen faktisk et veldig ryddig kampbilde."
    elif pairwise >= 0.8:
        matchup_text += " Det fungerer, men jeg ville fortsatt passet på gjentakelser."
    else:
        matchup_text += " Her er det for mye gjentakelse til at jeg ville vært fornøyd."

    load_text = (
        f"Kampbelastningen er {'jevn' if spread <= 1 else 'akseptabel' if spread <= 2 else 'for ujevn'}: "
        f"{max_team or 'ingen lag'} har {max_games} kamper, {min_team or 'ingen lag'} har {min_games}, og spredningen er {spread}."
    )
    if month_balance >= 0.9 and spread <= 1:
        load_text += " Det ser veldig kontrollert ut over hele sesongen."
    elif month_balance >= 0.8:
        load_text += " Det er helt brukbart, men ikke spesielt elegant."
    else:
        load_text += " Det er et punkt jeg ville sett nærmere på før utsending."

    if missing_hosts:
        hosting_text = f"Vertskapet er planen svakeste del: {len(missing_hosts)} RVV-klubber mangler vertsturnering ({', '.join(missing_hosts)})."
        if busiest_club:
            hosting_text += f" {busiest_club} bærer mest av klubbbelastningen totalt ({busiest_club_load} roller)."
    elif top_host_share >= 0.4:
        hosting_text = f"Vertskapet er litt for konsentrert hos {top_host}: {top_host_count} av {total_hosted} vertsturneringer."
        if busiest_club:
            hosting_text += f" {busiest_club} er samtidig den mest belastede klubben totalt ({busiest_club_load} roller)."
    else:
        hosting_text = "Vertskapet ser balansert ut og gir et ryddig sesongbilde."

    if team_travel and farthest_km:
        travel_text = f"Reisebildet har også en klar topp: {farthest_team} ligger på {farthest_km} km total reise."
        if farthest_km >= 200:
            travel_text += " Det er verdt å dobbeltsjekke om den belastningen er bevisst."
    else:
        travel_text = "Reisebildet ser ikke ut til å være det som drar planen i noen retning her."

    action_text = {
        "strong": "Hvis du vil pirke, ville jeg først sjekket vertskap og reise, ikke matchupene.",
        "mixed": "Hvis jeg skulle justert noe nå, ville jeg startet med vertskapet og de mest skjeve lagene.",
        "rough": "Jeg ville stoppet her og brukt neste runde på å jevne ut kampbildet og fordele belastningen bedre.",
    }[tone]

    cards = [
        ("Matchup", matchup_text),
        ("Belastning", load_text),
        ("Vertskap", hosting_text),
        ("Reise", travel_text),
    ]

    return {
        "tone": tone,
        "tone_label": tone_label,
        "verdict": verdict,
        "action_text": action_text,
        "cards": cards,
    }


def render_opinionated_judgment_html(
    plan: object,
    *,
    team_game_counts: dict[str, int],
    club_stats: dict[str, dict[str, object]],
    team_travel: dict[str, int],
) -> str:
    """Render a separate, opinionated synthesis of the full plan.

    This is intentionally distinct from the scripted metrics tables: it
    compresses the main signals into a human-style judgment at the end of
    the report.
    """
    analysis = analyze_opinionated_judgment(
        plan,
        team_game_counts=team_game_counts,
        club_stats=club_stats,
        team_travel=team_travel,
    )
    tone = str(analysis["tone"])
    card_html = "".join(
        f'<article class="judgment-card"><span>{_html.escape(label)}</span><p>{_html.escape(text)}</p></article>'
        for label, text in analysis["cards"]
    )

    return (
        f'<section class="report-section report-section--judgment report-section--judgment-{tone}" id="opinionatedJudgment">'
        '<div class="section-head">'
        '<div>'
        '<p class="eyebrow">Egen vurdering</p>'
        '<h2>Min ærlige dom på hele planen</h2>'
        '</div>'
        '<p class="section-note">Dette er en separat tolkning av tallene — ikke en ny metrikk eller en kopi av tabellene over.</p>'
        '</div>'
        f'<div class="judgment-callout judgment-callout--{tone}">'
        f'<div class="judgment-callout-label">{_html.escape(str(analysis["tone_label"]))}</div>'
        f'<p class="judgment-callout-verdict">{_html.escape(str(analysis["verdict"]))}</p>'
        f'<p class="judgment-callout-action">{_html.escape(str(analysis["action_text"]))}</p>'
        '</div>'
        f'<div class="judgment-grid">{card_html}</div>'
        '</section>'
    )
