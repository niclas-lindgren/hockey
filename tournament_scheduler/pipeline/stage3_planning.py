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

from ..fairness_scoring import build_fairness_gate as _build_fairness_gate
from ..models import CalendarEvent, Game, Roster, SeasonPlan, Team, Tournament
from ..season_planner import SeasonPlanner
from ..roster_loader import RosterLoader
from ..club_registry import CLUB_REGISTRY
from .fingerprints import stable_payload_sha256
from .state import PipelineState, StageName, StageStatus
from .stage3_helpers import (_build_club_arenas, _build_events_by_club, _build_parallel_games, _build_roster, _build_round_length, _find_team, _make_planner, _plan_to_dict)

# ---------------------------------------------------------------------------
# Candidate reproducibility and ranking
# ---------------------------------------------------------------------------

# Bump only when the planner's search algorithm changes in a way that could
# produce a different plan from the same seed/config/source fingerprint.
PLANNER_VERSION = "1"

# Deterministic candidate ranking: a hard-constraint ("fail") status always
# loses to "warn"/"pass" regardless of aggregate score, so a good average
# score can never hide a hard-constraint violation (e.g. an arena/day
# collision). Ties within the same status are broken by aggregate score,
# then by tournament count, then by earliest attempt (stable iteration
# order) — every step here is a plain comparison, so candidate selection is
# fully deterministic for a given set of seeds.
_STATUS_RANK = {"fail": 0, "warn": 1, "pass": 2}


def _candidate_rank(status: str, score: int, tournament_count: int) -> tuple[int, int, int]:
    return (_STATUS_RANK.get(status, 1), score, tournament_count)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Stage3Error(RuntimeError):
    """Raised when Stage 3 cannot produce a plan."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Stage 3 feilet: {reason}")


def _extract_planning_critic_hints(config: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, float] | None]:
    """Return structured planning critic metadata and flat planner penalties.

    ``penalty_hints`` remains backwards compatible as a flat mapping.  New
    pre-export critic loops may instead pass ``planning_critic_hints`` with a
    nested ``penalty_hints`` mapping plus metadata such as source, tone, and
    issues; Stage 3 persists that metadata while sending only the numeric
    penalties into ``SeasonPlanner``.
    """
    structured = config.get("planning_critic_hints")
    raw_penalties: Any = config.get("penalty_hints")

    if structured is None and isinstance(raw_penalties, dict) and "penalty_hints" in raw_penalties:
        structured = raw_penalties

    if isinstance(structured, dict):
        nested = structured.get("penalty_hints")
        if isinstance(nested, dict):
            raw_penalties = nested

    if not isinstance(raw_penalties, dict):
        return structured if isinstance(structured, dict) else None, None

    penalties: dict[str, float] = {}
    for key, value in raw_penalties.items():
        try:
            penalties[str(key)] = float(value)
        except (TypeError, ValueError):
            continue

    return structured if isinstance(structured, dict) else None, penalties or None


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
    iterations: int = 1,
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
    iterations:
        Number of planning attempts to run with different random seeds.
        The attempt with the highest composite fairness score is kept.
        When ``1`` (default), behaviour is identical to the original
        deterministic single-pass run (seed=None).

    Returns
    -------
    dict
        The plan serialised to a JSON-compatible dict.
    """
    existing_checkpoint = state.read_stage(StageName.PLANNING) or {}
    existing_manual_adjustments = dict(
        existing_checkpoint.get("plan", {}).get("manual_adjustments", {})
        or existing_checkpoint.get("manual_adjustments", {})
    )

    state.write_stage(StageName.PLANNING, {}, status=StageStatus.RUNNING)

    roster = _build_roster(config)
    pg_config = _build_parallel_games(config)
    round_length_config = _build_round_length(config)
    club_arenas = _build_club_arenas(config)
    max_hosting_deviation = config.get("maxHostingDeviation", 1)
    events_by_club = _build_events_by_club(scraping_result)
    fairness_thresholds = config.get("fairness_thresholds", {})
    target_tournament_count = config.get("target_tournament_count")
    max_hosting_days_per_month = config.get("max_hosting_days_per_month")
    target_tournament_counts_by_age_group = config.get("target_tournament_counts_by_age_group")
    planning_critic_hints, penalty_hints = _extract_planning_critic_hints(config)

    config_fingerprint = stable_payload_sha256(config)
    source_fingerprint = stable_payload_sha256(scraping_result)

    best_plan: SeasonPlan | None = None
    best_planner: SeasonPlanner | None = None
    best_rank: tuple[int, int, int] | None = None
    best_attempt: int | None = None
    candidates: list[dict[str, Any]] = []

    n_iters = max(1, iterations)
    seeds: list[int | None] = [None] if n_iters == 1 else list(range(n_iters))

    for idx, seed in enumerate(seeds, start=1):
        print(f"[plan] Forsøk {idx}/{n_iters} (seed={seed if seed is not None else 'default'})", flush=True)
        candidate: dict[str, Any] = {
            "attempt": idx,
            "seed": seed,
            "planner_version": PLANNER_VERSION,
            "config_fingerprint": config_fingerprint,
            "source_fingerprint": source_fingerprint,
            "penalty_hints": dict(penalty_hints) if penalty_hints else {},
        }
        planner = _make_planner(
            roster,
            pg_config,
            club_arenas,
            max_hosting_deviation,
            round_length_config,
            events_by_club,
            fairness_thresholds,
            target_tournament_count,
            target_tournament_counts_by_age_group,
            seed=seed,
            max_hosting_days_per_month=max_hosting_days_per_month,
            penalty_hints=penalty_hints,
        )
        plan = planner.build_plan(start_date, end_date)
        if plan is None or not plan.tournaments:
            print(f"[plan] Forsøk {idx}/{n_iters}: ingen plan kunne bygges", flush=True)
            candidate.update({"status": "failed", "score": None, "tournament_count": 0, "rank": None})
            candidates.append(candidate)
            continue

        gate = _build_fairness_gate(planner, plan)
        status = str(gate.get("status", "pass"))
        score = int(gate.get("score", 0))
        tournament_count = len(plan.tournaments)
        rank = _candidate_rank(status, score, tournament_count)
        candidate.update({
            "status": status,
            "score": score,
            "tournament_count": tournament_count,
            "rank": list(rank),
            "metrics": gate.get("metrics", []),
        })
        candidates.append(candidate)

        print(f"[plan] Forsøk {idx}/{n_iters}: fairness score={score} (status={status})", flush=True)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_plan = plan
            best_planner = planner
            best_attempt = idx

    if best_plan is None or best_planner is None:
        reason = "Klarte ikke å generere noen plan."
        state.write_stage(StageName.PLANNING, {"candidates": candidates}, status=StageStatus.FAILED)
        if strict:
            raise Stage3Error(reason)
        return {}

    if existing_manual_adjustments:
        best_plan.manual_adjustments = dict(existing_manual_adjustments)
    plan_dict = _plan_to_dict(best_plan)
    rules_report = best_planner.rules_report()

    checkpoint: dict[str, Any] = {
        "plan": plan_dict,
        "rules_report": rules_report,
        "candidates": candidates,
        "selected_candidate_attempt": best_attempt,
    }
    if planning_critic_hints is not None:
        checkpoint["planning_critic_hints"] = planning_critic_hints
    elif penalty_hints:
        checkpoint["planning_critic_hints"] = {
            "source": "penalty_hints",
            "penalty_hints": penalty_hints,
        }

    state.write_stage(StageName.PLANNING, checkpoint, status=StageStatus.DONE)
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
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        metavar="N",
        help="Run the planner N times with different random seeds and keep the best plan (default: 1)",
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
        _result = run(_cfg, _scraping, _state, _start, _end, iterations=cli_args.iterations)
        plan = _result.get("plan", {})
        n = len(plan.get("tournaments", []))
        print(f"Stage 3 OK — {n} turneringer planlagt")
        sys.exit(0)
    except Stage3Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
