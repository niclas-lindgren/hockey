"""LLM-based confidence assessment for scraping data before Stage 3 planning.

Passes the Stage 2 scraping checkpoint to an LLM and asks it to assess whether
the scraped calendar data is sufficient for reliable season planning.  Returns
an "OK" or "WARN" verdict together with suspicious sources, identified gaps, and
a short overall assessment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScrapingConfidenceVerdict:
    """Structured result of the scraping confidence assessment."""

    verdict: str  # "OK" or "WARN"
    suspicious_sources: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    overall_assessment: str = ""


def run_confidence_assessment(
    scraping_checkpoint: dict[str, Any],
    cfg: Any,
    client: Any,
) -> ScrapingConfidenceVerdict:
    """Ask an LLM whether the Stage 2 scraping results are good enough for planning.

    Args:
        scraping_checkpoint: The Stage 2 checkpoint dict.  Expected keys:
            ``sources`` (list of source dicts with ``name``, ``event_count``,
            ``blocked``, ``block_reason``), ``blocked`` (list of source names).
        cfg: Config object with ``start_date`` and ``end_date`` (datetime.date).
        client: An LMStudioClient (or compatible) with a
            ``complete(system, user, temperature) -> LLMResponse`` method where
            ``LLMResponse.text`` is the assistant reply string.

    Returns:
        A :class:`ScrapingConfidenceVerdict`.  On any parse failure the verdict
        defaults to ``"OK"`` so that the pipeline is never silently blocked by a
        malformed LLM response.
    """
    # ── Build a concise scraping summary ──────────────────────────────────────
    sources: list[dict[str, Any]] = scraping_checkpoint.get("sources", [])

    season_days = (cfg.end_date - cfg.start_date).days
    season_weeks = round(season_days / 7, 1)

    blocked_sources = [
        {"name": s["name"], "reason": s.get("block_reason", "")}
        for s in sources
        if s.get("blocked", False)
    ]

    sources_with_zero_events = [
        s["name"]
        for s in sources
        if s.get("event_count", 0) == 0 and not s.get("blocked", False)
    ]

    per_source_event_counts = {
        s["name"]: s.get("event_count", 0)
        for s in sources
    }

    # Events per week gives a rough density signal to help the LLM judge volume
    events_per_week_by_source = {
        name: round(count / season_weeks, 1) if season_weeks > 0 else count
        for name, count in per_source_event_counts.items()
    }

    summary: dict[str, Any] = {
        "total_sources": len(sources),
        "date_range": f"{cfg.start_date} to {cfg.end_date}",
        "season_weeks": season_weeks,
        "blocked_sources": blocked_sources,
        "sources_with_zero_events": sources_with_zero_events,
        "per_source_event_counts": per_source_event_counts,
        "events_per_week_by_source": events_per_week_by_source,
    }

    # ── Compose prompts ────────────────────────────────────────────────────────
    system_prompt = (
        "You are a hockey season calendar scraping quality controller. "
        "Assess whether the scraped calendar data is sufficient for reliable "
        "season planning. Be concise and precise."
    )

    user_prompt = (
        "Review the following scraping summary and decide whether the data quality "
        "is acceptable for season planning.\n\n"
        "Scraping summary (JSON):\n"
        f"{json.dumps(summary, ensure_ascii=False, indent=2)}\n\n"
        "Evaluation criteria:\n"
        "- An ice-hall calendar active year-round typically has 3–15 events per week. "
        "Much lower counts suggest scraping failures or coverage gaps.\n"
        "- Blocked sources mean those clubs' availability is unknown — flag as a gap "
        "if more than 1 source is blocked.\n"
        "- Sources with zero events (not blocked) are suspicious: either the hall is "
        "genuinely empty (unlikely for a full season) or scraping silently failed.\n"
        "- Date range gaps: if the season spans many weeks but event counts are very "
        "low for a source, flag as a possible gap.\n\n"
        "Respond with a JSON object and nothing else. Required keys:\n"
        '  "verdict"              — "OK" or "WARN"\n'
        '  "suspicious_sources"   — list of source names that look unreliable '
        "(empty list if none)\n"
        '  "gaps"                 — list of strings describing missing data or '
        "coverage issues (empty list if none)\n"
        '  "overall_assessment"   — one or two sentences summarising data quality\n'
    )

    # ── Call LLM ───────────────────────────────────────────────────────────────
    response = client.complete(system=system_prompt, user=user_prompt, temperature=0.1)
    raw_text: str = response.text.strip()

    # ── Parse response ─────────────────────────────────────────────────────────
    # 1. Try strict JSON parse (possibly inside a markdown code fence).
    json_candidate = raw_text
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    if fence_match:
        json_candidate = fence_match.group(1).strip()

    try:
        parsed: dict[str, Any] = json.loads(json_candidate)
        verdict = str(parsed.get("verdict", "OK")).upper()
        if verdict not in ("OK", "WARN"):
            verdict = "OK"
        return ScrapingConfidenceVerdict(
            verdict=verdict,
            suspicious_sources=list(parsed.get("suspicious_sources", [])),
            gaps=list(parsed.get("gaps", [])),
            overall_assessment=str(parsed.get("overall_assessment", "")),
        )
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Best-effort text parse: look for WARN / OK keyword.
    m = re.search(r"\b(WARN|OK)\b", raw_text, re.IGNORECASE)
    if m:
        verdict = m.group(1).upper()
        return ScrapingConfidenceVerdict(
            verdict=verdict,
            suspicious_sources=[],
            gaps=[],
            overall_assessment=raw_text[m.end():].strip() or raw_text,
        )

    # 3. Completely unparseable — default to OK to avoid silent pipeline blocks.
    return ScrapingConfidenceVerdict(
        verdict="OK",
        suspicious_sources=[],
        gaps=[],
        overall_assessment=(
            f"Parse error: could not interpret LLM response — defaulting to OK. "
            f"Raw: {raw_text[:200]}"
        ),
    )
