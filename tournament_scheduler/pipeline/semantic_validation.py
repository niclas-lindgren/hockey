"""Semantic pre-planning validation for the tournament scheduling pipeline.

Provides utilities to build an LLM prompt that checks whether the high-level
constraints (age groups, team counts, host clubs, available weekends, tournament
targets) describe a feasible season plan, and to parse the resulting warnings.

Typical usage (called after Stage 1, before Stage 3)::

    system_prompt, user_prompt = build_semantic_prompt(config)
    response = llm_client.complete(system_prompt, user_prompt, temperature=0.1)
    warnings = parse_semantic_warnings(response.text)
"""

import datetime
import re
from typing import Any


def build_semantic_prompt(config: dict[str, Any]) -> tuple[str, str]:
    """Build system and user prompts for LLM semantic validation.

    Parameters
    ----------
    config:
        Merged effective config dict as returned by
        ``stage1_config.load_effective_config``.  Expected keys:
        ``start_date``, ``end_date``, ``teams``, ``age_groups``,
        ``parallel_games``, ``target_tournament_count``,
        ``round_length_minutes``.

    Returns
    -------
    tuple[str, str]
        ``(system_prompt, user_prompt)`` ready to pass to an LLM client.
    """
    start_date = datetime.date.fromisoformat(config["start_date"])
    end_date = datetime.date.fromisoformat(config["end_date"])

    # Count available Saturdays in the date range
    available_weekends: list[str] = []
    current = start_date
    while current <= end_date:
        if current.weekday() == 5:  # Saturday
            available_weekends.append(current.isoformat())
        current += datetime.timedelta(days=1)

    # Teams per age group
    teams_by_age: dict[str, int] = {}
    for team in config.get("teams", []):
        ag = team.get("age_group", "unknown")
        teams_by_age[ag] = teams_by_age.get(ag, 0) + 1

    # Distinct host clubs (each club can host at most one tournament per weekend)
    host_clubs = sorted({team.get("club", "") for team in config.get("teams", []) if team.get("club")})
    num_clubs = len(host_clubs)

    # Age groups present
    age_groups = config.get("age_groups") or sorted(teams_by_age.keys())
    num_age_groups = len(age_groups)

    target_ttc = config.get("target_tournament_count")
    parallel_games = config.get("parallel_games", {})
    round_lengths = config.get("round_length_minutes", {})

    # Estimate minimum weekends needed: target_ttc rounds * num_age_groups,
    # but clubs can host at most one tournament per weekend, so constraint is
    # ceil(total_slots / num_clubs) <= available weekends.
    total_slots = (target_ttc or 0) * num_age_groups if target_ttc else None

    # ---- prompts ----
    system_prompt = (
        "You are an expert feasibility checker for Norwegian youth ice hockey season plans. "
        "You analyse high-level scheduling constraints and identify concrete reasons why "
        "the plan may be impossible or very difficult to fulfil. "
        "Focus only on structural infeasibilities that can be detected from the numbers alone. "
        "Do not suggest improvements — only flag problems."
    )

    lines = [
        "Analyse the following constraints for a Norwegian youth ice hockey season plan "
        "and list any obvious infeasibility issues.",
        "",
        "== Constraints ==",
        f"Season window : {start_date} to {end_date} ({len(available_weekends)} available Saturdays)",
        f"Age groups    : {', '.join(age_groups) if age_groups else 'not specified'} ({num_age_groups} total)",
        f"Host clubs    : {', '.join(host_clubs) if host_clubs else 'not specified'} ({num_clubs} total)",
        f"Teams per age group : {teams_by_age}",
        f"Target tournaments per team : {target_ttc if target_ttc is not None else 'not specified'}",
        f"Parallel games per age group: {parallel_games if parallel_games else 'not specified'}",
        f"Round length (min) per group : {round_lengths if round_lengths else 'not specified'}",
    ]
    if total_slots is not None:
        lines.append(
            f"Total tournament slots needed : {total_slots} "
            f"({target_ttc} per team x {num_age_groups} age groups)"
        )

    lines += [
        "",
        "== What to check ==",
        "Consider at least:",
        "- Whether the number of required tournaments exceeds available Saturdays",
        "- Whether fewer clubs are available to host than there are age groups needing a host",
        "- Whether parallel-game constraints make a tournament impossibly long for a single day",
        "- Any other structural constraint that makes the plan infeasible",
        "",
        "Return ONLY a numbered list of concrete warnings, one per line. "
        "If the plan looks feasible, reply with exactly: no issues detected",
    ]

    user_prompt = "\n".join(lines)
    return system_prompt, user_prompt


def parse_semantic_warnings(response_text: str) -> list[str]:
    """Parse an LLM response into a list of warning strings.

    Handles numbered lists (``1. ...``, ``2. ...``) and bullet lists
    (``- ...``, ``* ...``).  Returns an empty list when the response
    indicates no issues.

    Parameters
    ----------
    response_text:
        Raw text returned by the LLM.

    Returns
    -------
    list[str]
        One warning string per detected issue; empty list if none.
    """
    if not response_text:
        return []

    normalized = response_text.strip().lower()
    no_issue_phrases = (
        "no issues detected",
        "no issues",
        "no problems",
        "no infeasibility",
        "plan looks feasible",
        "appears feasible",
        "no obvious issues",
    )
    if any(phrase in normalized for phrase in no_issue_phrases):
        return []

    # Match lines that start with a number+dot or a bullet character
    bullet_re = re.compile(r"^(?:\d+[.)]\s*|[-*]\s+)(.*)", re.MULTILINE)
    matches = bullet_re.findall(response_text)

    warnings: list[str] = []
    for m in matches:
        stripped = m.strip()
        if stripped:
            warnings.append(stripped)

    # Fallback: if no bullet/number markers found, treat each non-empty line as a warning
    if not warnings:
        for line in response_text.splitlines():
            stripped = line.strip()
            if stripped:
                warnings.append(stripped)

    return warnings
