"""LLM-generated narrative conclusion for the season-plan report.

This module provides `generate_report_conclusion`, which asks an LLM to write
a short Norwegian narrative summarising the season plan quality.  When no
client is provided, or when the LLM server is unavailable, the function
returns ``None`` so the caller can fall back to static text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tournament_scheduler.llm.lm_studio_client import LMStudioClient

_SYSTEM_PROMPT = (
    "Du er en erfaren ishockeyplanlegger med ansvar for å vurdere sesongrammer "
    "for RVV (Region Viken Vest). Skriv en konkluderende vurdering på norsk — "
    "3 til 5 setninger — som oppsummerer planens styrker og svakheter basert på "
    "tallene du får. Vær direkte og praktisk. Unngå bullet points og markdown."
)


def generate_report_conclusion(
    plan: Any,
    blocked: list[str] | None = None,
    client: "LMStudioClient | None" = None,
) -> str | None:
    """Generate a 3–5-sentence Norwegian narrative conclusion using an LLM.

    Parameters
    ----------
    plan:
        The ``SeasonPlan`` object (or any object with the attributes described
        below).  Expected attributes (all optional — missing ones are skipped):

        * ``fairness_gate`` — dict with ``"status"`` and ``"score"``
        * ``pairwise_matchup_score`` — float
        * ``diversity_score`` — float
        * ``month_balance_score`` — float
        * ``manual_adjustments`` — dict[str, list[str]]

    blocked:
        List of calendar-source names that could not be fetched.  ``None``
        and empty list are treated equivalently (no blocked sources).

    client:
        An instantiated ``LMStudioClient``.  When ``None`` the function
        returns ``None`` immediately without hitting the network.

    Returns
    -------
    str | None
        The LLM-generated conclusion text, or ``None`` when unavailable.
    """
    if client is None:
        return None

    from tournament_scheduler.llm.lm_studio_client import LMStudioUnavailableError

    user_prompt = _build_user_prompt(plan, blocked)

    try:
        response = client.complete(system=_SYSTEM_PROMPT, user=user_prompt)
        text = response.text.strip() if hasattr(response, "text") else str(response).strip()
        return text if text else None
    except LMStudioUnavailableError:
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_user_prompt(plan: Any, blocked: list[str] | None) -> str:
    """Assemble the user-facing part of the LLM prompt from plan metrics."""
    lines: list[str] = ["Her er tallene for sesongrammens kvalitetsvurdering:"]

    # Fairness gate ---------------------------------------------------------
    gate = getattr(plan, "fairness_gate", None)
    if isinstance(gate, dict):
        status = gate.get("status", "ukjent")
        score = gate.get("score", None)
        score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
        lines.append(f"- Fairness-gate: {status} (score {score_str})")
    elif gate is not None:
        lines.append(f"- Fairness-gate: {gate}")

    # Per-metric breakdown --------------------------------------------------
    pairwise = getattr(plan, "pairwise_matchup_score", None)
    if pairwise is not None:
        lines.append(f"- Pairwise matchup-score: {pairwise:.2f}")

    diversity = getattr(plan, "diversity_score", None)
    if diversity is not None:
        lines.append(f"- Diversitetsscore: {diversity:.2f}")

    month_balance = getattr(plan, "month_balance_score", None)
    if month_balance is not None:
        lines.append(f"- Månedlig balansescore: {month_balance:.2f}")

    # Blocked sources -------------------------------------------------------
    blocked_count = len(blocked) if blocked else 0
    if blocked_count > 0:
        lines.append(
            f"- Blokkerte kalenderkilder: {blocked_count} "
            f"({', '.join(blocked[:5])}{'...' if blocked_count > 5 else ''})"
        )
    else:
        lines.append("- Blokkerte kalenderkilder: ingen")

    # Manual adjustments ----------------------------------------------------
    adjustments: dict = getattr(plan, "manual_adjustments", None) or {}
    total_adj = sum(len(v) for v in adjustments.values()) if isinstance(adjustments, dict) else 0
    if total_adj > 0:
        lines.append(f"- Manuelle justeringer: {total_adj} totalt")
    else:
        lines.append("- Manuelle justeringer: ingen")

    lines.append(
        "\nBaser vurderingen utelukkende på disse tallene. "
        "Konkluder med om planen er klar til å sendes ut, trenger mindre justeringer, "
        "eller trenger grundig gjennomgang."
    )
    return "\n".join(lines)
