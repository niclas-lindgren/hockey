"""LLM-based go/no-go approval gate between Stage 3 planning and Stage 4 export.

Passes the stage3 checkpoint (plan + rules_report) to an LLM and asks it to make
a GO/NO_GO decision with a short rationale, a list of blockers, and proposed changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApprovalVerdict:
    """Structured result of the LLM approval gate."""

    decision: str  # "GO" or "NO_GO"
    rationale: str
    blockers: list[str] = field(default_factory=list)
    proposed_changes: list[str] = field(default_factory=list)


def run_approval_gate(plan_checkpoint: dict[str, Any], client: Any) -> ApprovalVerdict:
    """Ask an LLM to approve or reject the stage3 plan before export.

    Args:
        plan_checkpoint: The stage3 checkpoint dict, containing ``plan`` (serialised
            SeasonPlan) and ``rules_report`` (list of rule dicts with ``regel``,
            ``forklaring``, ``kategori`` keys).
        client: An LMStudioClient (or compatible) with a
            ``complete(system, user, temperature) -> LLMResponse`` method where
            ``LLMResponse.text`` is the assistant reply string.

    Returns:
        An :class:`ApprovalVerdict` with decision, rationale, blockers and proposed
        changes.  On any parse failure the verdict defaults to GO so that the pipeline
        is never silently blocked by a malformed LLM response.
    """
    # ── Build a concise plan summary ──────────────────────────────────────────
    plan = plan_checkpoint.get("plan", {})
    tournaments: list[dict[str, Any]] = plan.get("tournaments", [])

    num_tournaments = len(tournaments)
    age_groups = sorted({t.get("age_group", "") for t in tournaments} - {""})
    hosts = sorted({t.get("host", "") for t in tournaments} - {""})

    rules_report: list[dict[str, str]] = plan_checkpoint.get("rules_report", [])
    issues = [
        item
        for item in rules_report
        if item.get("kategori") in ("Advarsel", "Hard krav") and item.get("forklaring")
    ]

    summary: dict[str, Any] = {
        "tournaments_count": num_tournaments,
        "age_groups": age_groups,
        "hosts": hosts,
        "issues": issues,
    }

    # ── Compose prompts ────────────────────────────────────────────────────────
    system_prompt = (
        "You are a hockey season planning quality controller. "
        "You review tournament plans and rules compliance to ensure quality and "
        "adherence to regulations. Be concise and precise."
    )

    user_prompt = (
        "Review the following tournament plan summary and decide whether to approve it "
        "for export.\n\n"
        "Plan summary (JSON):\n"
        f"{json.dumps(summary, ensure_ascii=False, indent=2)}\n\n"
        "Respond with a JSON object and nothing else. Required keys:\n"
        '  "decision"         — "GO" or "NO_GO"\n'
        '  "rationale"        — one or two sentences explaining the decision\n'
        '  "blockers"         — list of strings describing issues that prevent approval '
        "(empty list if GO)\n"
        '  "proposed_changes" — list of strings with concrete suggested changes '
        "(empty list if none)\n"
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
        decision = str(parsed.get("decision", "GO")).upper()
        if decision not in ("GO", "NO_GO"):
            decision = "GO"
        return ApprovalVerdict(
            decision=decision,
            rationale=str(parsed.get("rationale", "")),
            blockers=list(parsed.get("blockers", [])),
            proposed_changes=list(parsed.get("proposed_changes", [])),
        )
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Best-effort text parse: look for GO / NO_GO keyword.
    m = re.search(r"\b(NO_GO|GO)\b", raw_text, re.IGNORECASE)
    if m:
        decision = m.group(1).upper()
        rationale = raw_text[m.end():].strip() or raw_text
        return ApprovalVerdict(
            decision=decision,
            rationale=rationale,
            blockers=[],
            proposed_changes=[],
        )

    # 3. Completely unparseable — default to GO to avoid silent pipeline blocks.
    return ApprovalVerdict(
        decision="GO",
        rationale=f"Parse error: could not interpret LLM response — defaulting to GO. Raw: {raw_text[:200]}",
        blockers=[],
        proposed_changes=[],
    )
