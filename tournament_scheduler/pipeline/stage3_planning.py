"""Stage 3 — deterministic season planning.

Calls :class:`~tournament_scheduler.season_planner.SeasonPlanner` to produce a
:class:`~tournament_scheduler.models.SeasonPlan` with built-in deterministic
quality scores (diversity, balance, pairwise-matchup).

The accepted plan is written to the Stage 3 checkpoint as JSON.
LLM-based quality gates are handled by the pi extension, not by this module.

Minimal usage::

    from tournament_scheduler.pipeline.stage3_planning import run
    from tournament_scheduler.pipeline.state import PipelineState

    state = PipelineState(".pipeline")
    result = run(config=stage1_data, scraping_result=stage2_data, state=state,
                 start_date=..., end_date=...)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..models import Game, Roster, SeasonPlan, Team, Tournament
from ..season_planner import SeasonPlanner
from ..roster_loader import RosterLoader
from ..club_registry import CLUB_REGISTRY
from .state import PipelineState, StageName, StageStatus

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Stage3Error(RuntimeError):
    """Raised when Stage 3 cannot produce a plan."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Stage 3 feilet: {reason}")


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
    strict: bool = True,
) -> dict[str, Any]:
    """Build a season plan using the deterministic Python algorithm.

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
    strict:
        If ``True``, raise :class:`Stage3Error` when no plan can be built.

    Returns
    -------
    dict
        The plan serialised to a JSON-compatible dict.
    """
    state.write_stage(StageName.PLANNING, {}, status=StageStatus.RUNNING)

    roster = _build_roster(config)
    pg_config = _build_parallel_games(config)
    club_arenas = _build_club_arenas(config)

    planner = _make_planner(roster, pg_config, club_arenas)
    plan = planner.build_plan(start_date, end_date)

    if plan is None or not plan.tournaments:
        reason = "Klarte ikke å generere noen plan."
        state.mark_failed(StageName.PLANNING, error=reason)
        if strict:
            raise Stage3Error(reason)
        return {}

    plan_dict = _plan_to_dict(plan)

    checkpoint: dict[str, Any] = {
        "plan": plan_dict,
    }

    state.write_stage(StageName.PLANNING, checkpoint, status=StageStatus.DONE)
    state.mark_done(StageName.PLANNING)
    return checkpoint


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
            "id": t.id,
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
    """Construct a :class:`SeasonPlanner`."""
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


def _tournament_from_dict(data: dict[str, Any]) -> Tournament:
    """Reconstruct a :class:`Tournament` from a serialised dict."""
    teams = [
        Team(club=t["club"], label=t["label"], age_group=t["age_group"])
        for t in data.get("teams", [])
    ]
    games = [
        Game(
            home=_find_team(teams, g["home"]),
            away=_find_team(teams, g["away"]),
            parallel_slot=g.get("parallel_slot", 0),
            round_number=g.get("round_number", 0),
        )
        for g in data.get("games", [])
    ]
    return Tournament(
        id=data.get("id", ""),
        date=date.fromisoformat(data["date"]),
        arena=data["arena"],
        age_group=data["age_group"],
        host_club=data.get("host_club"),
        teams=teams,
        games=games,
    )


def _find_team(teams: list[Team], label: str) -> Team:
    """Find a Team by label; return a placeholder if missing."""
    for t in teams:
        if t.label == label:
            return t
    return Team(club="", label=label, age_group="")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Stage 3: deterministic season planning"
    )
    parser.add_argument(
        "--work-dir", default=".pipeline", help="Pipeline work directory"
    )
    cli_args = parser.parse_args()

    from .state import PipelineState, StageName  # noqa: E402
    from datetime import datetime as _dt  # noqa: E402

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
        print(f"Stage 3 OK — {n} turneringer planlagt")
        sys.exit(0)
    except Stage3Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
