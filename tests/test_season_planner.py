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


@pytest.fixture
def small_roster_planner_and_plan():
    """A scenario with a small single-age-group roster over a long season window,
    so that repeat matchups are unavoidable — useful for exercising
    `_opponent_history` accumulation and the diversity/balance metrics that
    depend on it.
    """
    start, end = datetime(2026, 9, 1), datetime(2027, 5, 31)
    free_dates = _all_weekend_dates(start, end)

    clubs = ["Jar", "Holmen", "Kongsberg", "Skien"]
    age_groups = ["U10"]
    roster = _build_roster(clubs, age_groups)
    club_arenas = {club: f"{club}hallen" for club in clubs}

    planner = SeasonPlanner(
        scheduler=FakeScheduler(free_dates),
        roster=roster,
        club_arenas=club_arenas,
        parallel_games_for_age_group={"U10": 3},
    )
    plan = planner.build_plan(start, end)
    return planner, plan, roster, clubs, club_arenas


class TestOpponentHistoryTrackingAndScoring:
    """Tests for `_opponent_history`, `_month_counts`, scoring, and the
    pairwise-matchup / month-balance metrics derived from them."""

    def test_opponent_history_accumulates_match_counts_from_generated_games(self, planner_and_plan):
        planner, plan, *_ = planner_and_plan

        expected_counts = {}
        for tournament in plan.tournaments:
            for game in tournament.games:
                pair = frozenset((game.home.label, game.away.label))
                expected_counts[pair] = expected_counts.get(pair, 0) + 1

        assert planner._opponent_history == expected_counts
        # Sanity: every recorded pair count should be a positive integer.
        assert all(count > 0 for count in planner._opponent_history.values())

    def test_opponent_history_accumulates_across_a_full_season_with_repeats(self, small_roster_planner_and_plan):
        planner, plan, *_ = small_roster_planner_and_plan

        # With only 4 teams in a single age group over a long season window,
        # the same pairs must be scheduled to play each other more than once.
        assert planner._opponent_history, "expected opponent history to be populated"
        assert any(count > 1 for count in planner._opponent_history.values()), (
            "expected at least one repeat matchup in this small-roster scenario"
        )

        # Cross-check the recorded history against the actual generated games.
        recomputed = {}
        for tournament in plan.tournaments:
            for game in tournament.games:
                pair = frozenset((game.home.label, game.away.label))
                recomputed[pair] = recomputed.get(pair, 0) + 1
        assert planner._opponent_history == recomputed

    def test_score_candidate_date_prefers_fewer_repeat_matchups(self, planner_and_plan):
        planner, plan, roster, *_ = planner_and_plan

        teams = roster.by_age_group("U10")
        assert len(teams) >= 3
        team_a, team_b, other_team = teams[0], teams[1], teams[2]

        # Reset opponent history to a controlled state: (team_a, team_b) has
        # already played twice; every other pair (including team_a/other_team)
        # has no recorded history.
        pair = frozenset((team_a.label, team_b.label))
        planner._opponent_history = {pair: 2}

        candidate_date = plan.start_date or date(2026, 10, 3)
        expected_per_month = 1.0  # neutral month-load baseline for this comparison

        score_with_repeats = planner._score_candidate_date(
            candidate_date, "U10", [team_a, team_b], expected_per_month
        )

        # A fresh pair (no recorded history) on the same date should score
        # strictly lower (more desirable) than the pair with repeat history,
        # all else being equal.
        score_without_repeats = planner._score_candidate_date(
            candidate_date, "U10", [team_a, other_team], expected_per_month
        )

        assert score_without_repeats < score_with_repeats

    def test_pick_least_recently_grouped_prefers_subset_with_fewer_repeat_matchups(self, planner_and_plan):
        planner, plan, roster, *_ = planner_and_plan

        teams = roster.by_age_group("U10")
        assert len(teams) >= 3
        team_a, team_b, team_c = teams[0], teams[1], teams[2]

        # Reset tracking so the heuristic is driven purely by opponent history
        # for this test, and force team_a to have already played team_b twice
        # but never team_c.
        planner._invite_counts = {t.label: 0 for t in roster.teams}
        planner._grouped_with = {}
        planner._opponent_history = {frozenset((team_a.label, team_b.label)): 2}

        candidates = [team_a, team_b, team_c] + [t for t in teams if t not in (team_a, team_b, team_c)]
        selected = planner._pick_least_recently_grouped(candidates, 2)

        assert team_a in selected
        # Given a choice, the second pick should avoid repeating with team_a
        # in favour of the fresher pairing with team_c.
        assert team_c in selected
        assert team_b not in selected

    def test_month_counts_stay_within_a_reasonable_spread(self, planner_and_plan, season_window):
        planner, plan, *_ = planner_and_plan
        start, end = season_window

        assert planner._month_counts, "expected month counts to be populated"

        expected_per_month = planner._expected_monthly_load(
            start.date(), end.date(), len(plan.tournaments)
        )
        assert expected_per_month > 0

        counts = list(planner._month_counts.values())
        # No single month should be wildly out of step with the season average
        # — a generous bound since the greedy spread algorithm is heuristic,
        # not a strict optimizer.
        assert max(counts) <= expected_per_month + 2, (
            f"a month is disproportionately overloaded: {planner._month_counts}"
        )

    def test_diversity_and_month_balance_metrics_present_on_plan(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        assert isinstance(plan.diversity_score, float)
        assert isinstance(plan.pairwise_matchup_score, float)
        assert isinstance(plan.month_balance_score, float)

        assert 0.0 <= plan.diversity_score <= 1.0
        assert 0.0 <= plan.pairwise_matchup_score <= 1.0
        assert 0.0 <= plan.month_balance_score <= 1.0

        # diversity_score now delegates to the pairwise-matchup computation.
        assert plan.diversity_score == plan.pairwise_matchup_score

    def test_pairwise_matchup_score_reflects_repeat_matchups(self, small_roster_planner_and_plan):
        planner, plan, *_ = small_roster_planner_and_plan

        # We already established this scenario forces repeat matchups, so the
        # fraction of *first-time* pairings must be less than 1.0.
        assert plan.pairwise_matchup_score < 1.0
        assert 0.0 <= plan.pairwise_matchup_score <= 1.0

        # Cross-check against a from-scratch recomputation over the actual games.
        seen_pairs = set()
        novel = 0
        total = 0
        for tournament in plan.tournaments:
            for game in tournament.games:
                pair = frozenset((game.home.label, game.away.label))
                total += 1
                if pair not in seen_pairs:
                    novel += 1
                seen_pairs.add(pair)

        assert total > 0
        assert plan.pairwise_matchup_score == round(novel / total, 3)
