"""Participant-selection helpers for `SeasonPlanner`."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Set

from tournament_scheduler.models import Team, overlapping_age_groups
from tournament_scheduler.season_config import DEFAULT_PARALLEL_GAMES

DEFAULT_TARGET_TOURNAMENT_COUNT = 6
MIN_TEAMS_PER_TOURNAMENT = 3


def default_target_count(num_free_dates: int) -> int:
    """Fallback when no age-group-specific target is available."""
    return max(1, min(DEFAULT_TARGET_TOURNAMENT_COUNT, num_free_dates))


def pick_spread_dates(
    planner,
    free_dates: Sequence[date],
    window_start: date,
    window_end: date,
    age_groups: Sequence[str] = (),
    scheduled_age_groups_by_date: Optional[Dict[date, List[str]]] = None,
    target_count: Optional[int] = None,
) -> List[date]:
    """Pick free dates for one age group, spread across the season window."""
    if not free_dates:
        return []

    scheduled_age_groups_by_date = scheduled_age_groups_by_date or {}

    target_count = target_count or default_target_count(len(free_dates))
    target_count = max(1, min(target_count, len(free_dates)))

    total_days = (window_end - window_start).days
    if total_days <= 0 or target_count == 1:
        return list(free_dates[:target_count])

    expected_per_month = planner._expected_monthly_load(window_start, window_end, target_count)

    bucket_span = total_days / target_count
    chosen: List[date] = []
    used: Set[date] = set()

    ag_index = 0
    scheduled_by_date: Dict[date, List[str]] = {}

    for i in range(target_count):
        bucket_start = window_start + timedelta(days=int(i * bucket_span))
        bucket_end = window_start + timedelta(days=int((i + 1) * bucket_span))
        bucket_center = bucket_start + (bucket_end - bucket_start) / 2
        half_span_days = max(1.0, (bucket_end - bucket_start).days / 2)

        candidates = [d for d in free_dates if bucket_start <= d <= bucket_end and d not in used]
        if not candidates:
            candidates = [d for d in free_dates if d not in used]
        if not candidates:
            continue

        if age_groups:
            predicted_age_group = planner._next_age_group(
                age_groups, ag_index, bucket_center, scheduled_by_date
            )
            predicted_participants = planner._select_participants(predicted_age_group)

            def combined_score(d: date) -> float:
                spread_penalty = abs((d - bucket_center).days) / half_span_days
                diversity_penalty = planner._score_candidate_date(
                    d, predicted_age_group, predicted_participants, expected_per_month
                )
                same_day_penalty = len(scheduled_age_groups_by_date.get(d, [])) * 50.0
                overlap_penalty = 0.0
                for existing in scheduled_age_groups_by_date.get(d, []):
                    if (
                        predicted_age_group in overlapping_age_groups(existing)
                        or existing in overlapping_age_groups(predicted_age_group)
                    ):
                        overlap_penalty += 100.0
                return spread_penalty + diversity_penalty + same_day_penalty + overlap_penalty

            best = min(candidates, key=combined_score)

            ag_index = (age_groups.index(predicted_age_group) + 1) % len(age_groups)
            scheduled_by_date.setdefault(best, []).append(predicted_age_group)
        else:
            best = min(candidates, key=lambda d: abs((d - bucket_center).days))

        chosen.append(best)
        used.add(best)

    return sorted(chosen)


def target_tournaments_for_age_group(planner, age_group: str) -> int:
    """Return the number of tournaments to aim for in `age_group`."""
    teams = planner.roster.by_age_group(age_group)
    if len(teams) < MIN_TEAMS_PER_TOURNAMENT:
        return 0

    total_target = sum(
        (t.target_tournament_count or planner.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT)
        for t in teams
    )
    capacity = min(len(teams), max_teams_for(planner, age_group))
    return max(1, math.ceil(total_target / capacity))


def next_age_group(
    planner,
    age_groups: Sequence[str],
    start_index: int,
    tournament_date: date,
    scheduled_by_date: Dict[date, List[str]],
) -> str:
    """Pick the next age group to schedule, round-robin from `start_index`."""
    already_on_date = scheduled_by_date.get(tournament_date, [])

    for offset in range(len(age_groups)):
        candidate = age_groups[(start_index + offset) % len(age_groups)]
        overlaps_existing = any(
            candidate in overlapping_age_groups(existing) or existing in overlapping_age_groups(candidate)
            for existing in already_on_date
        )
        if not overlaps_existing:
            return candidate

    return age_groups[start_index % len(age_groups)]


def select_participants(planner, age_group: str) -> List[Team]:
    """Select the teams to invite to a tournament for the given age group."""
    candidates = planner.roster.by_age_group(age_group)
    if not candidates:
        return []

    candidates = [t for t in candidates if not planner._team_at_target(t)]
    if not candidates:
        return []

    max_teams = participant_limit_for(planner, age_group, len(candidates))
    if len(candidates) <= max_teams:
        return cap_per_club_deficit_aware(planner, candidates, age_group)

    return pick_least_recently_grouped(planner, candidates, max_teams, age_group)


def cap_per_club_deficit_aware(planner, teams: Sequence[Team], age_group: str) -> List[Team]:
    """Filter `teams` by per-club caps, with a deficit override."""
    result: List[Team] = []
    club_counts: Dict[str, int] = {}
    remaining = list(teams)

    for index, team in enumerate(remaining):
        club_count = club_counts.get(team.club, 0)
        max_club = max_club_teams_for(planner, age_group, team.club)
        if club_count < max_club:
            club_counts[team.club] = club_count + 1
            result.append(team)
            continue

        pending_under_cap_deficits = [
            deficit_score(planner, t, age_group)
            for t in remaining[index + 1 :]
            if club_counts.get(t.club, 0) < max_club_teams_for(planner, age_group, t.club)
        ]
        this_deficit = deficit_score(planner, team, age_group)
        if pending_under_cap_deficits and max(pending_under_cap_deficits) >= this_deficit:
            continue

        club_counts[team.club] = club_count + 1
        result.append(team)
        planner._club_cap_overrides += 1

    return result


def participant_limit_for(planner, age_group: str, team_count: int) -> int:
    """Return the max teams that fit a tournament for `team_count` rosters."""
    base_capacity = max_teams_for(planner, age_group)
    return min(base_capacity, team_count)


def max_teams_for(planner, age_group: str) -> int:
    """Return the largest tournament size for `age_group`."""
    return base_team_capacity(planner, age_group)


def max_club_teams_for(planner, age_group: str, club: str) -> int:
    """Return how many teams from `club` may play in one `age_group` tournament."""
    teams_in_age_group = planner.roster.by_age_group(age_group)
    total = len(teams_in_age_group)
    if total == 0:
        return planner.max_club_teams_per_tournament
    club_team_count = sum(1 for t in teams_in_age_group if t.club == club)
    if club_team_count == 0:
        return planner.max_club_teams_per_tournament

    max_teams = max_teams_for(planner, age_group)
    proportional = math.ceil(club_team_count / total * max_teams)

    deficit_spread = age_group_deficit_spread(planner, age_group, teams_in_age_group)
    if deficit_spread > planner.max_game_count_spread:
        proportional = min(proportional + planner.deficit_cap_expansion, max_teams)

    return max(planner.max_club_teams_per_tournament, min(proportional, max_teams))


def age_group_deficit_spread(
    planner,
    age_group: str,
    teams_in_age_group: Optional[List[Team]] = None,
) -> float:
    """Return the deficit spread (max - min deficit) across `age_group`."""
    if teams_in_age_group is None:
        teams_in_age_group = planner.roster.by_age_group(age_group)
    if not teams_in_age_group:
        return 0.0
    if not any(planner._running_game_counts.get(planner._team_key(t), 0) for t in teams_in_age_group):
        return 0.0
    deficits = [deficit_score(planner, t, age_group) for t in teams_in_age_group]
    if not deficits:
        return 0.0
    return max(deficits) - min(deficits)


def expected_average_for(planner, age_group: str) -> float:
    """Return the current running average game count for `age_group`."""
    teams = planner.roster.by_age_group(age_group)
    if not teams:
        return 0.0
    counts = [planner._running_game_counts.get(planner._team_key(team), 0) for team in teams]
    return sum(counts) / len(counts)


def deficit_score(planner, team: Team, age_group: str) -> float:
    """Return how far below the fairness target `team` is."""
    if planner._team_at_target(team):
        return -1.0
    age_group_teams = planner.roster.by_age_group(age_group)
    if not age_group_teams:
        return 0.0
    key = planner._team_key(team)
    target = planner.fairness_model.planning_target_games_for_team(
        team,
        age_group_teams,
        planner._running_game_counts,
    )
    return target - planner._running_game_counts.get(key, 0)


def normalized_invite_count(planner, team: Team) -> float:
    """Return `team`'s invite count, normalized by club-size-in-age-group."""
    key = planner._team_key(team)
    sibling_count = planner._club_age_group_team_counts.get(key, 1)
    return planner._invite_counts.get(key, 0) * sibling_count


def club_diversity_penalty(
    planner,
    selected: Sequence[Team],
    remaining: Sequence[Team],
    team: Team,
) -> int:
    """Return a strong penalty for repeating a club before others are used.

    Clubs that are not yet represented in the current tournament get no
    penalty. Once every remaining club has been represented at least once,
    repeated clubs become feasible again and the penalty drops to a soft
    tie-breaker.
    """
    selected_clubs = {s.club for s in selected}
    if team.club not in selected_clubs:
        return 0

    remaining_new_clubs = {t.club for t in remaining if t.club not in selected_clubs}
    if not remaining_new_clubs:
        return 0

    repeated_count = sum(1 for s in selected if s.club == team.club)
    return 1000 + repeated_count * 250 + len(remaining_new_clubs) * 50


def pick_least_recently_grouped(
    planner,
    candidates: Sequence[Team],
    count: int,
    age_group: str,
) -> List[Team]:
    """Greedily build a subset that minimizes repeat matchups."""
    remaining = list(candidates)
    if not remaining:
        return []

    remaining.sort(
        key=lambda t: (
            normalized_invite_count(planner, t),
            -deficit_score(planner, t, age_group),
            candidates.index(t),
        )
    )
    selected: List[Team] = [remaining.pop(0)]

    while remaining and len(selected) < count:
        def repeat_matchup_score(team: Team) -> int:
            total = 0
            for s in selected:
                pair = frozenset((planner._team_key(team), planner._team_key(s)))
                total += planner._opponent_history.get(pair, 0)
            return total

        def overlap_score(team: Team) -> int:
            grouped_with = planner._grouped_with.get(planner._team_key(team), set())
            return sum(1 for s in selected if planner._team_key(s) in grouped_with)

        under_cap: List[Team] = [
            t for t in remaining
            if sum(1 for s in selected if s.club == t.club)
            < max_club_teams_for(planner, age_group, t.club)
        ]
        over_cap: List[Team] = [t for t in remaining if t not in under_cap]
        max_under_cap_deficit = (
            max(deficit_score(planner, t, age_group) for t in under_cap)
            if under_cap else None
        )
        eligible_over_cap = [
            t for t in over_cap
            if max_under_cap_deficit is None
            or deficit_score(planner, t, age_group) > max_under_cap_deficit
        ]
        eligible = under_cap + eligible_over_cap
        if not eligible:
            eligible = remaining

        selected_clubs = {s.club for s in selected}
        eligible_over_cap_labels = {planner._team_key(t) for t in eligible_over_cap}

        # Club-load penalty: push down candidates whose club is already
        # represented in the selected set. Repeating a club becomes a
        # fallback only after every remaining club has been used at least
        # once, while the proportional soft cap still nudges the picker
        # away from runaway same-club clustering.
        def club_penalty(team: Team) -> int:
            club_count = sum(1 for s in selected if s.club == team.club)
            max_club = max_club_teams_for(planner, age_group, team.club)
            base = club_count * 25
            if club_count < max_club:
                return base
            if planner._team_key(team) in eligible_over_cap_labels:
                return base + (club_count - max_club + 1) * 100
            return base + club_count * 250  # outweighs typical match-up scores

        def skill_penalty(team: Team) -> int:
            selected_levels = [
                planner._team_skill_levels[planner._team_key(s)]
                for s in selected
                if planner._team_key(s) in planner._team_skill_levels
            ]
            if not selected_levels:
                return 0
            if planner._team_key(team) not in planner._team_skill_levels:
                return 0
            median = sorted(selected_levels)[len(selected_levels) // 2]
            dist = abs(team.skill_level - median)
            if dist <= planner.division_skill_band:
                return 0
            return (dist - planner.division_skill_band) * 100

        eligible.sort(
            key=lambda t: (
                0 if t.club not in selected_clubs else 1,
                club_penalty(t),
                normalized_invite_count(planner, t),
                -deficit_score(planner, t, age_group) * 1000,
                repeat_matchup_score(t),
                overlap_score(t),
                skill_penalty(t),
                candidates.index(t),
            )
        )
        chosen = eligible.pop(0)
        remaining.remove(chosen)
        selected.append(chosen)

        chosen_club_count = sum(1 for s in selected if s.club == chosen.club)
        if chosen_club_count > max_club_teams_for(planner, age_group, chosen.club):
            planner._club_cap_overrides += 1

    return selected


def base_team_capacity(planner, age_group: str) -> int:
    """Return the even team-count capacity implied by parallel games."""
    parallel_games = planner.parallel_games_for_age_group.get(age_group, DEFAULT_PARALLEL_GAMES)
    return max(1, parallel_games) * 2
