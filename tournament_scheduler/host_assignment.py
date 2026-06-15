"""Host-assignment helpers for `SeasonPlanner`."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from tournament_scheduler.models import Game


def pick_spread_dates(
    planner,
    free_dates: Sequence[date],
    window_start: date,
    window_end: date,
    age_groups: Sequence[str] = (),
    scheduled_age_groups_by_date: Optional[Dict[date, List[str]]] = None,
    target_count: Optional[int] = None,
) -> List[date]:
    """Compatibility wrapper that delegates to participant selection."""
    from tournament_scheduler.participant_selection import pick_spread_dates as _pick_spread_dates

    return _pick_spread_dates(
        planner,
        free_dates,
        window_start,
        window_end,
        age_groups=age_groups,
        scheduled_age_groups_by_date=scheduled_age_groups_by_date,
        target_count=target_count,
    )


def default_target_count(num_free_dates: int) -> int:
    """Fallback when no age-group-specific target is available."""
    from tournament_scheduler.participant_selection import DEFAULT_TARGET_TOURNAMENT_COUNT

    return max(1, min(DEFAULT_TARGET_TOURNAMENT_COUNT, num_free_dates))


def assign_hosts(planner, scheduled: Sequence[Tuple[date, str]]) -> List[str]:
    """Assign a host club to each scheduled `(date, age_group)`."""
    if not scheduled:
        return []

    age_totals: Dict[str, int] = {}
    for _, age_group in scheduled:
        age_totals[age_group] = age_totals.get(age_group, 0) + 1

    targets_by_age = {
        age_group: hosting_targets_for_age_group(planner, age_group, count)
        for age_group, count in age_totals.items()
    }
    actual_by_age: Dict[str, Dict[str, int]] = {
        age_group: {club: 0 for club in targets}
        for age_group, targets in targets_by_age.items()
    }
    last_hosted_by_age: Dict[str, Dict[str, int]] = {
        age_group: {club: -1 for club in targets}
        for age_group, targets in targets_by_age.items()
    }

    assignments: List[str] = []
    all_clubs = planner.roster.clubs()
    for i, (_, age_group) in enumerate(scheduled):
        targets = targets_by_age.get(age_group, {})
        if not targets:
            assignments.append(all_clubs[i % len(all_clubs)] if all_clubs else "")
            continue

        actual_counts = actual_by_age[age_group]
        last_hosted_index = last_hosted_by_age[age_group]
        deficit_clubs = [
            club for club in targets
            if actual_counts.get(club, 0) < targets.get(club, 0)
        ]
        if deficit_clubs:
            host = max(
                deficit_clubs,
                key=lambda club: (
                    targets.get(club, 0) - actual_counts.get(club, 0),
                    -last_hosted_index.get(club, -1),
                    targets.get(club, 0),
                ),
            )
        else:
            host = min(targets, key=lambda club: last_hosted_index.get(club, -1))

        assignments.append(host)
        actual_counts[host] = actual_counts.get(host, 0) + 1
        last_hosted_index[host] = i

    return assignments


def hosting_targets_for_age_group(planner, age_group: str, tournament_count: int) -> Dict[str, int]:
    """Return integer host targets for one age group."""
    teams = planner.roster.by_age_group(age_group)
    club_team_counts: Dict[str, int] = {}
    for team in teams:
        club_team_counts[team.club] = club_team_counts.get(team.club, 0) + 1
    return proportional_integer_targets(club_team_counts, tournament_count)


def proportional_integer_targets(weights: Dict[str, int], total: int) -> Dict[str, int]:
    """Round weighted quotas to integers that sum to `total`."""
    if total <= 0 or not weights:
        return {club: 0 for club in weights}
    weight_sum = sum(max(0, weight) for weight in weights.values()) or 1
    raw_targets = {
        club: max(0, weight) / weight_sum * total
        for club, weight in weights.items()
    }
    targets: Dict[str, int] = {}
    remainders: List[Tuple[float, str]] = []
    assigned = 0
    for club, raw in raw_targets.items():
        rounded = int(raw)
        targets[club] = rounded
        assigned += rounded
        remainders.append((raw - rounded, club))
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for _, club in remainders[: max(0, total - assigned)]:
        targets[club] += 1
    return targets


def find_slot_for_tournament(
    planner,
    tournament_date: date,
    host_club: str,
    age_group: str,
    games: List[Game],
) -> Optional[Tuple[str, str, str]]:
    """Find a time-of-day slot in the host club's own calendar."""
    if not planner.events_by_club:
        return None

    round_length = planner.round_length_for_age_group.get(age_group)
    if not round_length:
        return None

    if not games:
        return None

    max_round = max(g.round_number for g in games)
    required_minutes = round_length * max_round
    if required_minutes <= 0:
        return None

    return planner.scheduler.find_arena_slot_for_date(
        tournament_date, host_club, required_minutes, planner.events_by_club
    )
