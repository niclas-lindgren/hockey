"""Fairness scoring helpers for `SeasonPlanner`."""

from __future__ import annotations

from typing import Dict, List

from tournament_scheduler.club_distances import compute_team_travel_distances
from tournament_scheduler.models import SeasonPlan

DEFAULT_FAIRNESS_THRESHOLDS = {
    "max_game_count_spread": 2,
    "max_hosting_deviation": 1,
    "max_team_travel_km": 700,
    "min_diversity_score": 0.75,
    "min_pairwise_matchup_score": 0.25,
    "min_month_balance_score": 0.75,
    "max_same_weekend_club_load": 3,
}


def build_fairness_gate(planner, plan: SeasonPlan) -> Dict[str, object]:
    """Return a structured pass/warn/fail summary for key fairness metrics."""
    thresholds = planner.fairness_thresholds
    metrics: List[Dict[str, object]] = []

    def add_metric(
        key: str,
        label: str,
        value: float | int,
        threshold: float | int,
        *,
        direction: str,
        severity: str,
        detail: str,
        unit: str = "",
    ) -> None:
        if threshold is None:
            threshold_value = 0.0
        else:
            threshold_value = float(threshold)
        value_float = float(value)
        if direction == "max":
            within = value_float <= threshold_value
            if threshold_value <= 0:
                score = 100 if value_float <= 0 else 0
            elif within:
                score = 100
            else:
                score = max(0, int(round(100 * max(0.0, 2 - (value_float / threshold_value)))))
        else:
            within = value_float >= threshold_value
            if threshold_value <= 0:
                score = 100 if value_float > 0 else 0
            elif within:
                score = 100
            else:
                score = max(0, int(round(100 * max(0.0, value_float / threshold_value))))
        status = "pass" if within else ("fail" if severity == "fail" else "warn")
        metrics.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "threshold": threshold,
                "direction": direction,
                "severity": severity,
                "status": status,
                "score": score,
                "unit": unit,
                "detail": detail,
            }
        )

    team_travel = compute_team_travel_distances(plan)
    max_team_travel = max(team_travel.values()) if team_travel else 0

    hosting_breakdown = planner._hosting_fairness_breakdown(plan)
    hosting_deviation = float(hosting_breakdown.get("max_deviation", 0.0))
    hosting_detail = str(hosting_breakdown.get("detail", ""))

    same_weekend_load = 0
    weekend_loads: Dict[tuple[int, int], Dict[str, int]] = {}
    for tournament in plan.tournaments:
        iso_year, iso_week, _ = tournament.date.isocalendar()
        bucket = weekend_loads.setdefault((iso_year, iso_week), {})
        host_club = tournament.host_club or ""
        if host_club:
            bucket[host_club] = bucket.get(host_club, 0) + 1
    for loads in weekend_loads.values():
        if loads:
            same_weekend_load = max(same_weekend_load, max(loads.values()))
    weekend_detail = f"maks {same_weekend_load} turneringer fra samme klubb i samme uke"

    age_group_spreads: List[float] = []
    skipped_age_groups_set = {entry["age_group"] for entry in plan.skipped_age_groups}
    teams_by_age_group: Dict[str, List] = {}
    for team in planner.roster.teams:
        teams_by_age_group.setdefault(team.age_group, []).append(team)
    for age_group, teams in teams_by_age_group.items():
        if age_group in skipped_age_groups_set:
            continue
        counts = [planner._team_game_counts.get(planner._team_key(team), 0) for team in teams]
        if counts:
            average = sum(counts) / len(counts)
            spread = max(counts) - min(counts)
            normalized = spread / max(average, 1.0)
            age_group_spreads.append(min(normalized, 1.0))
    normalized_game_count_spread = max(age_group_spreads) if age_group_spreads else float(plan.game_count_spread)

    add_metric(
        "game_count_spread",
        "Kamper per lag",
        round(normalized_game_count_spread, 3),
        thresholds.get("max_game_count_spread", planner.max_game_count_spread),
        direction="max",
        severity="fail",
        detail=f"Normalisert spredning per aldersgruppe er {normalized_game_count_spread:.3f} (rå spredning: {plan.game_count_spread} kamper, tak på [0, 1]).",
    )
    add_metric(
        "hosting_deviation",
        "Hjemmebanebelastning",
        hosting_deviation,
        thresholds.get("max_hosting_deviation", planner.max_hosting_deviation),
        direction="max",
        severity="fail",
        detail=hosting_detail or "Aldersgruppevis vertskapsfordeling ligger innenfor terskelen.",
    )
    if metrics and metrics[-1].get("key") == "hosting_deviation":
        metrics[-1]["age_group_breakdown"] = hosting_breakdown.get("age_group_breakdown", [])
    add_metric(
        "travel_distance",
        "Reisebelastning",
        max_team_travel,
        thresholds.get("max_team_travel_km", DEFAULT_FAIRNESS_THRESHOLDS["max_team_travel_km"]),
        direction="max",
        severity="warn",
        detail=f"Lengst reisende lag har {max_team_travel} km total reise.",
        unit="km",
    )
    add_metric(
        "opponent_diversity",
        "Motstandervariasjon",
        plan.diversity_score,
        thresholds.get("min_diversity_score", DEFAULT_FAIRNESS_THRESHOLDS["min_diversity_score"]),
        direction="min",
        severity="warn",
        detail=f"Snittet av unik motstanderdekning er {plan.diversity_score:.3f}.",
    )
    add_metric(
        "pairwise_matchups",
        "Nye matchups",
        plan.pairwise_matchup_score,
        thresholds.get("min_pairwise_matchup_score", DEFAULT_FAIRNESS_THRESHOLDS["min_pairwise_matchup_score"]),
        direction="min",
        severity="warn",
        detail=f"Andel nye kampoppsett er {plan.pairwise_matchup_score:.3f}.",
    )
    add_metric(
        "month_balance",
        "Månedsbalanse",
        plan.month_balance_score,
        thresholds.get("min_month_balance_score", DEFAULT_FAIRNESS_THRESHOLDS["min_month_balance_score"]),
        direction="min",
        severity="warn",
        detail=f"Månedsbalansen er {plan.month_balance_score:.3f}.",
    )
    add_metric(
        "same_weekend_club_load",
        "Klubblast per helg",
        same_weekend_load,
        thresholds.get("max_same_weekend_club_load", DEFAULT_FAIRNESS_THRESHOLDS["max_same_weekend_club_load"]),
        direction="max",
        severity="warn",
        detail=weekend_detail,
    )

    statuses = [str(m["status"]) for m in metrics]
    if "fail" in statuses:
        overall_status = "fail"
    elif "warn" in statuses:
        overall_status = "warn"
    else:
        overall_status = "pass"
    overall_score = int(round(sum(float(m["score"]) for m in metrics) / len(metrics))) if metrics else 100
    return {
        "status": overall_status,
        "score": overall_score,
        "metrics": metrics,
        "thresholds": dict(thresholds),
    }
