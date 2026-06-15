"""Stage 4 export helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import Game, SeasonPlan, Team, Tournament

def _dict_to_plan(d: dict[str, Any]) -> SeasonPlan:
    """Reconstruct a :class:`SeasonPlan` from the checkpoint dict."""
    tournaments: list[Tournament] = []

    for t_dict in d.get("tournaments", []):
        teams = [
            Team(
                club=tm["club"],
                label=tm["label"],
                age_group=tm["age_group"],
                target_tournament_count=tm.get("target_tournament_count"),
            )
            for tm in t_dict.get("teams", [])
        ]
        team_by_label = {t.label: t for t in teams}

        games = []
        for g_dict in t_dict.get("games", []):
            home = team_by_label.get(g_dict.get("home", ""))
            away = team_by_label.get(g_dict.get("away", ""))
            if home and away:
                games.append(
                    Game(
                        home=home,
                        away=away,
                        parallel_slot=int(g_dict.get("parallel_slot", 0)),
                        round_number=int(g_dict.get("round_number", 0)),
                    )
                )

        date_str = t_dict.get("date", "")
        tournament_date = date.fromisoformat(date_str) if date_str else date.today()

        tournaments.append(
            Tournament(
                date=tournament_date,
                arena=t_dict.get("arena", ""),
                age_group=t_dict.get("age_group", ""),
                teams=teams,
                games=games,
                host_club=t_dict.get("host_club"),
                cancelled=bool(t_dict.get("cancelled", False)),
                cancellation_reason=t_dict.get("cancellation_reason"),
                start_time=t_dict.get("start_time"),
            )
        )

    start_str = d.get("start_date")
    end_str = d.get("end_date")

    return SeasonPlan(
        tournaments=tournaments,
        start_date=date.fromisoformat(start_str) if start_str else None,
        end_date=date.fromisoformat(end_str) if end_str else None,
        diversity_score=float(d.get("diversity_score", 0.0)),
        pairwise_matchup_score=float(d.get("pairwise_matchup_score", 0.0)),
        month_balance_score=float(d.get("month_balance_score", 0.0)),
        arena_counts=dict(d.get("arena_counts", {})),
        team_game_counts=dict(d.get("team_game_counts", {})),
        game_count_spread=int(d.get("game_count_spread", 0)),
        fairness_gate=dict(d.get("fairness_gate", {})),
        skipped_age_groups=list(d.get("skipped_age_groups", [])),
        team_last_game_dates={
            k: date.fromisoformat(v) for k, v in d.get("team_last_game_dates", {}).items()
        },
        manual_adjustments=dict(d.get("manual_adjustments", {})),
    )


# ---------------------------------------------------------------------------
