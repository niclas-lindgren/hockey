"""Stage-specific prompt builders for inter-stage headless pipeline judgment.

Each builder produces a concise, structured prompt that describes what the
stage produced and asks whether the pipeline should continue.  The prompts
are designed to work with any LLM backend — they include enough context to
make a meaningful PROCEED / ABORT decision without requiring the judge to
know the codebase.

Usage::

    from tournament_scheduler.llm_judge.prompts import build_stage_prompt

    prompt = build_stage_prompt("config", checkpoint_summary)
    verdict = judge.judge(prompt)
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Stage template registry
# ---------------------------------------------------------------------------

def _build_config_prompt(summary: dict[str, Any]) -> str:
    sources = summary.get("sources", summary.get("source_count", "?"))
    start = summary.get("start_date", "?")
    end = summary.get("end_date", "?")
    age_groups = summary.get("age_groups", [])
    clubs = summary.get("clubs", [])

    lines = [
        "PIPELINE STAGE: Configuration (Stage 1)",
        "",
        "The pipeline has loaded its input configuration file and validated it.",
        "Key metrics:",
        f"  - Calendar sources configured: {sources}",
        f"  - Date range: {start} → {end}",
    ]
    if age_groups:
        lines.append(f"  - Age groups: {', '.join(str(a) for a in age_groups)}")
    if clubs:
        lines.append(f"  - Clubs: {', '.join(str(c) for c in clubs)}")

    lines += [
        "",
        "Evaluation criteria: Does the configuration look plausible?",
        "  - At least one calendar source should be configured.",
        "  - The date range should be a realistic hockey season window.",
        "",
        "Respond with exactly one of:",
        "  PROCEED — configuration looks valid, continue to Stage 2 (scraping)",
        "  ABORT   — there is a problem; briefly explain after the keyword",
    ]
    return "\n".join(lines)


def _build_scraping_prompt(summary: dict[str, Any]) -> str:
    n = summary.get("sources_scanned", summary.get("sources", "?"))
    blocked = summary.get("blocked", [])
    n_blocked = len(blocked) if isinstance(blocked, list) else blocked
    llm_fallback = summary.get("llm_fallback", [])
    n_llm = len(llm_fallback) if isinstance(llm_fallback, list) else llm_fallback

    lines = [
        "PIPELINE STAGE: Calendar Scraping (Stage 2)",
        "",
        "The pipeline has attempted to scrape calendar data from all configured sources.",
        "Key metrics:",
        f"  - Sources scanned: {n}",
        f"  - Blocked / unavailable: {n_blocked}",
        f"  - Needing LLM fallback: {n_llm}",
    ]
    if isinstance(blocked, list) and blocked:
        lines.append(f"  - Blocked source names: {', '.join(str(b) for b in blocked)}")

    lines += [
        "",
        "Evaluation criteria: Is there enough data to proceed to planning?",
        "  - PROCEED if most sources were scraped successfully.",
        "  - ABORT if so many sources are blocked that planning would be meaningless",
        "    (e.g. fewer than half the sources have data).",
        "",
        "Respond with exactly one of:",
        "  PROCEED — enough calendar data was collected, continue to Stage 3 (planning)",
        "  ABORT   — too many sources are missing; briefly explain after the keyword",
    ]
    return "\n".join(lines)


def _build_planning_prompt(summary: dict[str, Any]) -> str:
    n_tournaments = summary.get("tournaments_planned", summary.get("n_tournaments", "?"))
    clubs = summary.get("clubs_covered", [])
    age_groups = summary.get("age_groups_covered", [])
    warnings = summary.get("warnings", [])

    lines = [
        "PIPELINE STAGE: Season Planning (Stage 3)",
        "",
        "The pipeline has generated a draft season plan assigning tournaments to",
        "weekends and arenas for the RVV (Region Viken Vest) youth hockey clubs.",
        "Key metrics:",
        f"  - Tournaments planned: {n_tournaments}",
    ]
    if clubs:
        lines.append(f"  - Clubs covered: {', '.join(str(c) for c in clubs)}")
    if age_groups:
        lines.append(f"  - Age groups covered: {', '.join(str(a) for a in age_groups)}")
    if warnings:
        lines.append(f"  - Planning warnings: {len(warnings)}")
        for w in warnings[:5]:
            lines.append(f"      • {w}")

    lines += [
        "",
        "Evaluation criteria: Does the plan look reasonable?",
        "  - There should be at least a handful of tournaments in the plan.",
        "  - A zero-tournament plan likely indicates a configuration or data error.",
        "",
        "Respond with exactly one of:",
        "  PROCEED — the plan looks reasonable, continue to Stage 4 (export)",
        "  ABORT   — the plan is empty or clearly wrong; briefly explain after the keyword",
    ]
    return "\n".join(lines)


_BUILDERS = {
    "config": _build_config_prompt,
    "stage1": _build_config_prompt,
    "scraping": _build_scraping_prompt,
    "stage2": _build_scraping_prompt,
    "planning": _build_planning_prompt,
    "stage3": _build_planning_prompt,
}


def build_stage_prompt(stage_name: str, checkpoint_summary: dict[str, Any]) -> str:
    """Build a structured judgment prompt for the given pipeline stage.

    Args:
        stage_name: One of ``"config"`` / ``"stage1"``, ``"scraping"`` /
                    ``"stage2"``, or ``"planning"`` / ``"stage3"``.
        checkpoint_summary: A dict of key metrics extracted from the stage
                            checkpoint.  Each builder uses a best-effort
                            approach — unknown keys are ignored gracefully.

    Returns:
        A prompt string ready to pass to :meth:`LLMJudge.judge`.

    Raises:
        ValueError: If *stage_name* is not recognised.
    """
    key = stage_name.lower()
    if key not in _BUILDERS:
        raise ValueError(
            f"Unknown stage name {stage_name!r}. "
            f"Valid values: {', '.join(sorted(set(_BUILDERS)))}"
        )
    return _BUILDERS[key](checkpoint_summary)
