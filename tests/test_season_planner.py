"""Tests for SeasonPlanner (season planning/optimization engine)."""

from datetime import date, datetime, timedelta

import pytest

from tournament_scheduler.models import (
    AGE_GROUP_OVERLAP,
    Roster,
    SchedulingResult,
    Team,
    overlapping_age_groups,
)
from tournament_scheduler.season_planner import SeasonPlanner, MIN_TOURNAMENTS, MAX_TOURNAMENTS


class FakeScheduler:
    """Stand-in for TournamentScheduler that returns a fixed set of free weekend dates
    without scraping any calendars (keeps the test fast, deterministic, and offline)."""

    def __init__(self, free_dates):
        self.free_dates = free_dates

    def find_available_dates(self, start_date, end_date, **kwargs):
        return SchedulingResult(
            available_dates=list(self.free_dates),
            excluded_dates=[],
            exclusion_breakdown={},
            detailed_exclusions=[],
            total_weekends_checked=len(self.free_dates),
        )


def _all_weekend_dates(start, end):
    dates = []
    d = start.date()
    while d <= end.date():
        if d.weekday() in (5, 6):
            dates.append(d)
        d += timedelta(days=1)
    return dates


def _build_roster(clubs, age_groups, teams_per_club_per_age_group=1):
    teams = []
    for club in clubs:
        for age_group in age_groups:
            for i in range(1, teams_per_club_per_age_group + 1):
                label = f"{club} {age_group}-{i}" if teams_per_club_per_age_group > 1 else f"{club} {age_group}"
                teams.append(Team(club=club, label=label, age_group=age_group))
    return Roster(teams=teams)


@pytest.fixture
def season_window():
    return datetime(2026, 10, 1), datetime(2027, 4, 30)


@pytest.fixture
def planner_and_plan(season_window):
    start, end = season_window
    free_dates = _all_weekend_dates(start, end)

    clubs = ["Jar", "Holmen", "Kongsberg", "Skien", "Jutul", "Ringerike"]
    age_groups = ["U10", "U11", "JU11", "U7"]
    roster = _build_roster(clubs, age_groups)
    club_arenas = {club: f"{club}hallen" for club in clubs}

    planner = SeasonPlanner(
        scheduler=FakeScheduler(free_dates),
        roster=roster,
        club_arenas=club_arenas,
        parallel_games_for_age_group={"U10": 3, "U7": 4},
    )
    plan = planner.build_plan(start, end)
    return planner, plan, roster, clubs, club_arenas


class TestSeasonPlanner:
    """Test suite for SeasonPlanner.build_plan."""

    def test_proposes_between_min_and_max_tournaments(self, planner_and_plan):
        _, plan, *_ = planner_and_plan
        assert MIN_TOURNAMENTS <= len(plan.tournaments) <= MAX_TOURNAMENTS

    def test_tournament_dates_are_spread_across_the_season_window(self, planner_and_plan, season_window):
        _, plan, *_ = planner_and_plan
        start, end = season_window

        dates = sorted(t.date for t in plan.tournaments)
        assert dates[0] >= start.date()
        assert dates[-1] <= end.date()

        # No two tournaments should land on exactly the same date in this scenario
        # (there are far more free weekend dates than tournaments to schedule).
        assert len(dates) == len(set(dates))

        # Roughly even spacing: gaps between consecutive tournament dates should
        # not vary wildly (sanity bound, not a strict uniformity requirement).
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        assert max(gaps) <= 3 * (sum(gaps) / len(gaps))

    def test_every_arena_hosts_at_least_one_tournament_before_any_repeats(self, planner_and_plan):
        _, plan, roster, clubs, club_arenas = planner_and_plan

        host_order = [t.host_club for t in sorted(plan.tournaments, key=lambda t: t.date)]
        first_occurrence = {}
        for index, host in enumerate(host_order):
            first_occurrence.setdefault(host, index)

        # Every club should have hosted at least once.
        assert set(first_occurrence) == set(clubs)

        # No club's *second* hosting should occur before every club has hosted once,
        # i.e. the max "first occurrence index" should be less than the index of any
        # repeat hosting.
        last_first_occurrence = max(first_occurrence.values())
        seen_once = set()
        for index, host in enumerate(host_order):
            if host in seen_once:
                assert index > last_first_occurrence, (
                    "a club hosted a second tournament before every club hosted once"
                )
            seen_once.add(host)

        # Every arena recorded in plan metadata corresponds to a real club arena.
        for arena in plan.arena_counts:
            if arena.startswith("_"):
                continue
            assert arena in club_arenas.values()

    def test_no_team_is_invited_disproportionately_more_than_others(self, planner_and_plan):
        _, plan, roster, *_ = planner_and_plan

        invite_counts = {team.label: 0 for team in roster.teams}
        for tournament in plan.tournaments:
            for team in tournament.teams:
                invite_counts[team.label] += 1

        # Compare invite counts only within the same age group (groups may differ
        # in how many tournaments they get scheduled overall).
        by_age_group = {}
        for team in roster.teams:
            by_age_group.setdefault(team.age_group, []).append(invite_counts[team.label])

        for age_group, counts in by_age_group.items():
            if not counts or max(counts) == 0:
                continue
            assert max(counts) - min(counts) <= 2, (
                f"{age_group}: invite counts too uneven: {counts}"
            )

    def test_avoids_avoidable_overlap_collisions_between_age_groups(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        by_date = {}
        for tournament in plan.tournaments:
            by_date.setdefault(tournament.date, []).append(tournament.age_group)

        unavoidable_collisions = []
        for tournament_date, age_groups_on_date in by_date.items():
            for i, ag in enumerate(age_groups_on_date):
                for other in age_groups_on_date[i + 1:]:
                    if other in overlapping_age_groups(ag) or ag in overlapping_age_groups(other):
                        unavoidable_collisions.append((tournament_date, ag, other))

        # In this scenario there are far more free dates than tournaments, so
        # every collision should have been avoidable — the planner should not
        # have produced any.
        assert unavoidable_collisions == [], f"unexpected collisions: {unavoidable_collisions}"
        assert plan.arena_counts.get("_age_group_overlap_collisions", 0) == 0
        assert planner_and_plan[0].collisions == []

    def test_each_tournament_is_single_age_group_with_round_robin_games(self, planner_and_plan):
        _, plan, *_ = planner_and_plan
        for tournament in plan.tournaments:
            assert tournament.teams, "tournament should have participants"
            assert all(team.age_group == tournament.age_group for team in tournament.teams)

            n = len(tournament.teams)
            expected_games = n * (n - 1) // 2
            assert len(tournament.games) == expected_games
