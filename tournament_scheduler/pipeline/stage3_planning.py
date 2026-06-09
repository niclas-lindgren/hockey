"""Stage 3 — planning with LLM evaluation and retry loop.

Calls :class:`~tournament_scheduler.season_planner.SeasonPlanner` to produce a
:class:`~tournament_scheduler.models.SeasonPlan`, then asks the LLM to evaluate
the plan for:

- **Coverage** — every team plays enough games
- **Opponent diversity** — varied opponents across the season
- **Time balance** — no month is overloaded with tournaments

If the LLM returns low confidence, the stage re-runs the planner up to
``MAX_RETRIES`` (default 3) times. The planner is re-initialised on each retry
so its internal opponent-history state is reset, giving a fresh draw.

The accepted plan is written to the Stage 3 checkpoint as JSON.

Minimal usage::

    from tournament_scheduler.pipeline.stage3_planning import run
    from tournament_scheduler.pipeline.state import PipelineState

    state = PipelineState(".pipeline")
    result = run(config=stage1_data, scraping_result=stage2_data, state=state,
                 start_date=..., end_date=...)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from ..models import Game, Roster, SeasonPlan, Team, Tournament
from ..season_planner import SeasonPlanner
from ..season_config import ParallelGamesConfig
from ..roster_loader import RosterLoader
from ..club_registry import CLUB_REGISTRY
from .state import PipelineState, StageName, StageStatus

# LLM client — optional; quality gate is skipped if unavailable
try:
    from ..llm.lm_studio_client import (
        LMStudioClient,
        LMStudioUnavailableError,
        extract_confidence,
    )

    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
CONFIDENCE_THRESHOLD = 0.65

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Stage3Error(RuntimeError):
    """Raised when Stage 3 cannot produce a plan that passes the LLM gate."""

    def __init__(self, reason: str, attempts: int) -> None:
        self.reason = reason
        self.attempts = attempts
        super().__init__(
            f"Stage 3 feilet etter {attempts} forsøk: {reason}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run(
    config: dict[str, Any],
    scraping_result: dict[str, Any],
    state: PipelineState,
    start_date: datetime,
    end_date: datetime,
    *,
    llm_client: "LMStudioClient | None" = None,
    max_retries: int = MAX_RETRIES,
    strict: bool = True,
) -> dict[str, Any]:
    """Build a season plan and validate it with the LLM quality gate.

    Parameters
    ----------
    config:
        Validated Stage 1 config dict.
    scraping_result:
        Stage 2 checkpoint data (for future conflict-checker integration;
        currently unused but stored in the checkpoint for traceability).
    state:
        :class:`PipelineState` managing the work directory.
    start_date / end_date:
        Season planning window.
    llm_client:
        Optional injected client (useful for testing).
    max_retries:
        Number of planning+evaluation attempts before giving up.
    strict:
        If ``True``, raise :class:`Stage3Error` when no acceptable plan is
        produced within ``max_retries``.

    Returns
    -------
    dict
        The accepted plan serialised to a JSON-compatible dict.
    """
    state.write_stage(StageName.PLANNING, {}, status=StageStatus.RUNNING)

    client = llm_client or (_make_default_client() if _LLM_AVAILABLE else None)

    roster = _build_roster(config)
    pg_config = _build_parallel_games(config)
    club_arenas = _build_club_arenas(config)

    last_plan: SeasonPlan | None = None
    last_confidence: float = 0.0
    last_reasoning: str = ""

    for attempt in range(1, max_retries + 1):
        planner = _make_planner(roster, pg_config, club_arenas)
        plan = planner.build_plan(start_date, end_date)
        last_plan = plan

        if client is None:
            # No LLM available — accept the first plan
            break

        try:
            confidence, reasoning = _evaluate_plan(
                plan=plan,
                client=client,
                start_date=start_date,
                end_date=end_date,
            )
        except LMStudioUnavailableError:
            # LM Studio offline — accept the plan as-is
            break

        last_confidence = confidence
        last_reasoning = reasoning

        if confidence >= CONFIDENCE_THRESHOLD:
            break
        # Low confidence — try again (planner is reset on next iteration)

    if last_plan is None:
        reason = "Klarte ikke å generere noen plan."
        state.mark_failed(StageName.PLANNING, error=reason)
        if strict:
            raise Stage3Error(reason, max_retries)
        return {}

    plan_dict = _plan_to_dict(last_plan)
    checkpoint: dict[str, Any] = {
        "plan": plan_dict,
        "llm_confidence": last_confidence,
        "llm_reasoning": last_reasoning,
        "attempts": min(max_retries, max_retries),  # final attempt number
        "llm_skipped": client is None,
    }

    state.write_stage(StageName.PLANNING, checkpoint, status=StageStatus.DONE)
    state.mark_done(StageName.PLANNING)
    return checkpoint


# ---------------------------------------------------------------------------
# LLM evaluation
# ---------------------------------------------------------------------------


def _evaluate_plan(
    *,
    plan: SeasonPlan,
    client: "LMStudioClient",
    start_date: datetime,
    end_date: datetime,
) -> tuple[float, str]:
    """Ask the LLM to evaluate the plan. Returns (confidence, reasoning)."""
    summary = _plan_summary_for_llm(plan)

    system = (
        "Du er en kvalitetskontroll-assistent for ishockeysesongplaner. "
        "Evaluer planen etter tre kriterier:\n"
        "1. Dekning (coverage): spiller hvert lag nok kamper?\n"
        "2. Motstandervariasjon (diversity): varierer motstanderne gjennom sesongen?\n"
        "3. Månedlig belastningsbalanse: er turneringene jevnt fordelt over månedene?\n\n"
        "Svar KUN med et JSON-objekt på formen: "
        '{"confidence": 0.0-1.0, "valid": true/false, "reasoning": "..."}'
    )

    user_msg = (
        f"Sesong: {start_date.strftime('%d.%m.%Y')} til {end_date.strftime('%d.%m.%Y')}\n\n"
        f"{summary}"
    )

    response = client.complete(system=system, user=user_msg, temperature=0.1)
    result = extract_confidence(response.text)
    return result.confidence, result.reasoning


def _plan_summary_for_llm(plan: SeasonPlan) -> str:
    """Build a concise text summary of the plan for LLM evaluation."""
    lines: list[str] = [
        f"Antall turneringer: {len(plan.tournaments)}",
        f"Diversity score: {plan.diversity_score:.2f}",
        f"Month balance score: {plan.month_balance_score:.2f}",
        f"Pairwise matchup score: {plan.pairwise_matchup_score:.2f}",
        "",
        "Turneringer:",
    ]
    for t in plan.tournaments:
        team_names = ", ".join(team.label for team in t.teams[:6])
        if len(t.teams) > 6:
            team_names += f" (+{len(t.teams) - 6})"
        lines.append(
            f"  {t.date.strftime('%d.%m.%Y')} | {t.arena} | {t.age_group} | "
            f"{len(t.teams)} lag | {len(t.games)} kamper — {team_names}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _plan_to_dict(plan: SeasonPlan) -> dict[str, Any]:
    """Convert :class:`SeasonPlan` to a JSON-serialisable dict."""

    def _game_to_dict(g: Game) -> dict[str, Any]:
        return {
            "home": g.home.label,
            "away": g.away.label,
            "parallel_slot": g.parallel_slot,
        }

    def _team_to_dict(t: Team) -> dict[str, Any]:
        return {"club": t.club, "label": t.label, "age_group": t.age_group}

    def _tournament_to_dict(t: Tournament) -> dict[str, Any]:
        return {
            "date": t.date.isoformat(),
            "arena": t.arena,
            "age_group": t.age_group,
            "host_club": t.host_club,
            "teams": [_team_to_dict(team) for team in t.teams],
            "games": [_game_to_dict(g) for g in t.games],
        }

    return {
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "diversity_score": plan.diversity_score,
        "pairwise_matchup_score": plan.pairwise_matchup_score,
        "month_balance_score": plan.month_balance_score,
        "arena_counts": plan.arena_counts,
        "tournaments": [_tournament_to_dict(t) for t in plan.tournaments],
    }


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _build_roster(config: dict[str, Any]) -> Roster:
    """Build a :class:`Roster` from the Stage 1 config."""
    teams_data = config.get("teams", [])
    teams = [
        Team(club=t["club"], label=t["label"], age_group=t["age_group"])
        for t in teams_data
        if isinstance(t, dict)
    ]
    return Roster(teams=teams)


def _build_parallel_games(config: dict[str, Any]) -> dict[str, int]:
    """Extract parallel-games mapping from config."""
    return dict(config.get("parallel_games", {}))


def _build_club_arenas(config: dict[str, Any]) -> dict[str, str]:
    """Build club→arena mapping, falling back to the global club registry."""
    # Build club→arena mapping from the global registry
    return {
        club: entry.arena
        for club, entry in CLUB_REGISTRY.items()
        if hasattr(entry, "arena") and entry.arena
    }


def _make_planner(
    roster: Roster,
    pg_config: dict[str, int],
    club_arenas: dict[str, str],
) -> SeasonPlanner:
    """Construct a fresh :class:`SeasonPlanner` (resets opponent history)."""
    from ..scheduler import TournamentScheduler
    from ..conflict_checkers.holiday_checker import HolidayConflictChecker
    from ..utils.date_parser import DateParser

    scheduler = TournamentScheduler(
        calendar_sources=[],
        conflict_checkers=[HolidayConflictChecker()],
        date_parser=DateParser(),
    )
    return SeasonPlanner(
        scheduler=scheduler,
        roster=roster,
        club_arenas=club_arenas,
        parallel_games_for_age_group=pg_config or None,
    )


def _make_default_client() -> "LMStudioClient":
    from ..llm.lm_studio_client import LMStudioClient

    return LMStudioClient()


# ---------------------------------------------------------------------------
# CLI entry point — supports: python3 -m tournament_scheduler.pipeline.stage3_planning
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 3: season planning with LLM evaluation")
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    cli_args = parser.parse_args()

    from .state import PipelineState, StageName  # noqa: E402
    from datetime import datetime as _dt

    _state = PipelineState(cli_args.work_dir)
    _cfg = _state.read_stage(StageName.CONFIG)
    if not _cfg:
        print("Stage 1 checkpoint not found — run Stage 1 first.", file=sys.stderr)
        sys.exit(1)

    _scraping = _state.read_stage(StageName.SCRAPING)
    _start = _dt.strptime(_cfg["start_date"], "%Y-%m-%d")
    _end = _dt.strptime(_cfg["end_date"], "%Y-%m-%d")

    try:
        _result = run(_cfg, _scraping, _state, _start, _end)
        plan = _result.get("plan", {})
        n = len(plan.get("tournaments", []))
        conf = _result.get("llm_confidence", None)
        print(f"Stage 3 OK — {n} turneringer planlagt, LLM confidence: {conf}")
        sys.exit(0)
    except Stage3Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
