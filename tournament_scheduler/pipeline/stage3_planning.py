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

from ..models import CalendarEvent, Game, Roster, SeasonPlan, Team, Tournament
from ..season_planner import SeasonPlanner
from ..roster_loader import RosterLoader
from ..club_registry import CLUB_REGISTRY
from .state import PipelineState, StageName, StageStatus
from .stage3_helpers import (_build_club_arenas, _build_events_by_club, _build_parallel_games, _build_roster, _build_round_length, _find_team, _make_planner, _plan_to_dict, _tournament_from_dict)
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
    round_length_config = _build_round_length(config)
    club_arenas = _build_club_arenas(config)
    division_skill_band = config.get("divisionSkillBand", 2)
    max_hosting_deviation = config.get("maxHostingDeviation", 1)
    events_by_club = _build_events_by_club(scraping_result)

    planner = _make_planner(
        roster,
        pg_config,
        club_arenas,
        division_skill_band,
        max_hosting_deviation,
        round_length_config,
        events_by_club,
    )
    plan = planner.build_plan(start_date, end_date)

    if plan is None or not plan.tournaments:
        reason = "Klarte ikke å generere noen plan."
        state.mark_failed(StageName.PLANNING, error=reason)
        if strict:
            raise Stage3Error(reason)
        return {}

    plan_dict = _plan_to_dict(plan)
    rules_report = planner.rules_report()

    checkpoint: dict[str, Any] = {
        "plan": plan_dict,
        "rules_report": rules_report,
    }

    state.write_stage(StageName.PLANNING, checkpoint, status=StageStatus.DONE)
    state.mark_done(StageName.PLANNING)
    return checkpoint


# ---------------------------------------------------------------------------
# Serialisation
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
    from .stage1_config import load_effective_config  # noqa: E402
    from datetime import datetime as _dt  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    _cfg = load_effective_config(_state)
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
