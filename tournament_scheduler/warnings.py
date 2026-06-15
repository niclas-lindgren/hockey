"""Warning-scanner helpers for `SeasonPlanner`."""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Optional, Sequence, Set

from tournament_scheduler.models import SeasonPlan, Team, Tournament


def compute_game_counts(planner, tournaments: Sequence[Tournament]) -> None:
    """Compute per-team round-robin game counts and last-game dates."""
    planner._team_game_counts = {}
    planner._team_last_date = {}
    for tournament in tournaments:
        for game in tournament.games:
            for team in (game.home, game.away):
                if team is None:
                    continue
                key = planner._team_key(team)
                planner._team_game_counts[key] = planner._team_game_counts.get(key, 0) + 1
                last = planner._team_last_date.get(key)
                if last is None or tournament.date > last:
                    planner._team_last_date[key] = tournament.date


def scan_game_count_warnings(
    planner,
    window_start: Optional[date],
    window_end: Optional[date],
) -> None:
    """Scan computed game counts for spread and early-finish violations."""
    planner._game_count_warnings = []

    if not planner._team_game_counts:
        return

    max_count = max(planner._team_game_counts.values())
    min_count = min(planner._team_game_counts.values())
    spread = max_count - min_count

    if spread > planner.max_game_count_spread:
        for key, count in planner._team_game_counts.items():
            if count == max_count or count == min_count:
                planner._game_count_warnings.append((key, count, spread, "spread"))

    if window_end is not None and planner._team_last_date:
        for key, last_date in planner._team_last_date.items():
            gap = (window_end - last_date).days
            if gap > planner.max_early_finish_gap_days:
                planner._game_count_warnings.append(
                    (key, planner._team_game_counts.get(key, 0), gap, "early_finish")
                )


def scan_per_team_share_warnings(
    planner,
    skipped_age_groups: Optional[List[Dict[str, object]]] = None,
) -> None:
    """Scan computed game counts for per-club/per-age-group skew."""
    planner._per_team_share_warnings = []

    skipped_set: Set[str] = set()
    if skipped_age_groups:
        skipped_set = {entry["age_group"] for entry in skipped_age_groups}

    teams_by_age_group: Dict[str, List[Team]] = {}
    for team in planner.roster.teams:
        if team.age_group in skipped_set:
            continue
        teams_by_age_group.setdefault(team.age_group, []).append(team)

    for age_group, teams in teams_by_age_group.items():
        if not teams:
            continue
        expected_by_team = planner.fairness_model.targets_for_age_group(
            teams,
            planner._team_game_counts,
        )
        for team in teams:
            key = planner._team_key(team)
            actual = planner._team_game_counts.get(key, 0)
            expected = expected_by_team.get(key, 0.0)
            if abs(actual - expected) > planner.max_game_count_spread:
                planner._per_team_share_warnings.append(
                    (key, team.club, age_group, actual, expected)
                )


def scan_feasibility_warnings(planner, free_dates: Sequence[date]) -> None:
    """Check each age group's participation target against free-date capacity."""
    from tournament_scheduler.participant_selection import MIN_TEAMS_PER_TOURNAMENT, DEFAULT_TARGET_TOURNAMENT_COUNT

    planner._feasibility_warnings = []

    for age_group in planner.roster.age_groups():
        teams = planner.roster.by_age_group(age_group)
        if len(teams) < MIN_TEAMS_PER_TOURNAMENT:
            planner._feasibility_warnings.append(
                f"{age_group}: kun {len(teams)} lag — "
                f"minimum {MIN_TEAMS_PER_TOURNAMENT} lag kreves for å arrangere turnering. "
                f"Aldersgruppen hoppes over."
            )
            continue

        capacity = min(len(teams), planner._max_teams_for(age_group))
        total_target = sum(
            (t.target_tournament_count or planner.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT)
            for t in teams
        )
        target_count = max(1, math.ceil(total_target / capacity))

        targets = [
            t.target_tournament_count or planner.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT
            for t in teams
        ]
        min_target = min(targets)
        max_target = max(targets)

        if target_count > len(free_dates):
            target_desc = f"{min_target}" if min_target == max_target else f"{min_target}–{max_target}"
            planner._feasibility_warnings.append(
                f"{age_group}: målet på ~{target_desc} deltakelser per lag "
                f"({target_count} turneringer) kan neppe nås — det er bare "
                f"{len(free_dates)} ledige helger i sesongvinduet. "
                f"Planleggeren justerer ned automatisk."
            )


def scan_month_load_warnings(
    planner,
    expected_per_month: float,
    start_date: Optional[date],
) -> None:
    """Scan month counts for over/under-loaded months."""
    planner._month_load_warnings = []
    if expected_per_month <= 0 or not planner._month_counts:
        return

    if start_date is None:
        return

    end_month = 4
    for (year, month), count in sorted(planner._month_counts.items()):
        if not ((month >= 10) or (month <= end_month)):
            continue

        deviation = (count - expected_per_month) / expected_per_month
        if abs(deviation) > planner.max_month_deviation_ratio:
            planner._month_load_warnings.append(
                (year, month, count, expected_per_month, deviation)
            )


def scan_club_load_warnings(planner, tournaments: Sequence[Tournament]) -> None:
    """Scan completed tournaments for club-load violations."""
    for t in tournaments:
        club_counts: Dict[str, int] = {}
        for team in t.teams:
            club_counts[team.club] = club_counts.get(team.club, 0) + 1
        for club, count in club_counts.items():
            max_club = planner._max_club_teams_for(t.age_group, club)
            if count > max_club:
                planner._club_load_warnings.append(
                    (club, t.age_group, t.date.isoformat(), count)
                )


def hosting_fairness_breakdown(planner, plan: SeasonPlan) -> Dict[str, object]:
    """Return age-group-aware expected vs actual hosting diagnostics."""
    rows: List[Dict[str, object]] = []
    max_deviation = 0.0
    max_detail = ""
    tournaments_by_age: Dict[str, List[Tournament]] = {}
    for tournament in plan.tournaments:
        tournaments_by_age.setdefault(tournament.age_group, []).append(tournament)

    for age_group in sorted(tournaments_by_age):
        tournaments = tournaments_by_age[age_group]
        age_teams = planner.roster.by_age_group(age_group)
        club_team_counts: Dict[str, int] = {}
        for team in age_teams:
            club_team_counts[team.club] = club_team_counts.get(team.club, 0) + 1
        total_age_teams = sum(club_team_counts.values()) or 1
        actual_hosting: Dict[str, int] = {}
        for tournament in tournaments:
            host = tournament.host_club
            if host:
                actual_hosting[host] = actual_hosting.get(host, 0) + 1

        for club in sorted(set(club_team_counts) | set(actual_hosting)):
            team_count = club_team_counts.get(club, 0)
            expected = team_count / total_age_teams * len(tournaments) if team_count else 0.0
            actual = actual_hosting.get(club, 0)
            deviation = abs(actual - expected)
            row = {
                "age_group": age_group,
                "club": club,
                "teams": team_count,
                "actual": actual,
                "expected": round(expected, 2),
                "deviation": round(deviation, 2),
                "tournaments": len(tournaments),
            }
            rows.append(row)
            if deviation >= max_deviation:
                max_deviation = deviation
                max_detail = (
                    f"{age_group}: {club} har {actual} hjemmeturnering(er), "
                    f"forventet ~{expected:.1f} basert på {team_count} lag i aldersgruppen."
                )

    if rows:
        examples = "; ".join(
            f"{row['age_group']} {row['club']}: {row['actual']} vs ~{float(row['expected']):.1f}"
            for row in sorted(rows, key=lambda row: float(row["deviation"]), reverse=True)[:4]
        )
        detail = f"Aldersgruppevis vertskapsfordeling: {examples}. Størst avvik: {max_detail}"
    else:
        detail = "Ingen vertskapsdata å vurdere."
    return {
        "max_deviation": max_deviation,
        "detail": detail,
        "age_group_breakdown": rows,
    }


def scan_hosting_warnings(planner, plan: SeasonPlan) -> None:
    """Scan hosting for age-group-aware proportional-imbalance violations."""
    if not plan.tournaments:
        return

    breakdown = hosting_fairness_breakdown(planner, plan)
    for row in breakdown.get("age_group_breakdown", []):
        if not isinstance(row, dict):
            continue
        deviation = float(row.get("deviation", 0.0) or 0.0)
        if deviation > planner.max_hosting_deviation:
            planner._hosting_warnings.append(
                f"{row.get('club')} har {row.get('actual')} hjemmeturnering(er) i {row.get('age_group')} "
                f"(forventet ~{float(row.get('expected', 0.0)):.1f} basert på "
                f"{row.get('teams')} lag i aldersgruppen, avvik {deviation:.1f} > "
                f"{planner.max_hosting_deviation})"
            )
