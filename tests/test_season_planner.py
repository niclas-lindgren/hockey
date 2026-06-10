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


class TestPerTeamGameCounts:
    """Tests for per-team game count tracking, spread validation, and early-finish detection."""

    def test_team_game_counts_match_actual_games(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        assert plan.team_game_counts, "expected team_game_counts to be populated"

        # Walk all games in the plan and recompute counts manually
        expected_counts: dict[str, int] = {}
        for tournament in plan.tournaments:
            for game in tournament.games:
                for team in (game.home, game.away):
                    if team is None:
                        continue
                    expected_counts[team.label] = expected_counts.get(team.label, 0) + 1

        assert plan.team_game_counts == expected_counts

    def test_team_last_game_dates_match_latest_tournament(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        assert plan.team_last_game_dates, "expected team_last_game_dates to be populated"

        # Recompute last-game dates manually
        expected_last_dates: dict[str, date] = {}
        for tournament in plan.tournaments:
            for game in tournament.games:
                for team in (game.home, game.away):
                    if team is None:
                        continue
                    last = expected_last_dates.get(team.label)
                    if last is None or tournament.date > last:
                        expected_last_dates[team.label] = tournament.date

        assert plan.team_last_game_dates == expected_last_dates

    def test_game_count_spread_is_non_negative(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        assert isinstance(plan.game_count_spread, int)
        assert plan.game_count_spread >= 0

    def test_game_count_spread_equals_max_minus_min(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        if plan.team_game_counts:
            expected_spread = max(plan.team_game_counts.values()) - min(plan.team_game_counts.values())
            assert plan.game_count_spread == expected_spread

    def test_game_count_warnings_fired_when_spread_exceeds_threshold(self):
        """Build a planner with a tight max_game_count_spread=0 so even a spread
        of 1 triggers warnings. Uses 6 teams with max_teams=3 so subsets vary."""
        from datetime import datetime as _dt

        start, end = _dt(2026, 10, 1), _dt(2027, 4, 30)
        free_dates = _all_weekend_dates(start, end)

        clubs = ["Jar", "Holmen", "Kongsberg", "Skien", "Jutul", "Ringerike"]
        age_groups = ["U10"]
        roster = _build_roster(clubs, age_groups)
        club_arenas = {club: f"{club}hallen" for club in clubs}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_teams_per_tournament_for_age_group={"U10": 3},
            max_game_count_spread=0,  # any spread triggers a warning
        )
        planner.build_plan(start, end)

        warnings = planner.game_count_warnings
        spread_warnings = [w for w in warnings if w[3] == "spread"]
        # With 6 teams and max 3 per tournament, subsets will vary over
        # ~12 tournaments, creating a spread in game counts.
        assert len(spread_warnings) >= 1, (
            f"expected at least one spread warning with max_game_count_spread=0, "
            f"got: {warnings}"
        )

    def test_no_game_count_warnings_when_spread_within_threshold(self):
        """With a single age group and lenient threshold, no spread warnings should fire."""
        from datetime import datetime as _dt

        start, end = _dt(2026, 10, 1), _dt(2027, 4, 30)
        free_dates = _all_weekend_dates(start, end)

        clubs = ["Jar", "Holmen", "Kongsberg", "Skien", "Jutul"]
        age_groups = ["U10"]
        roster = _build_roster(clubs, age_groups)
        club_arenas = {club: f"{club}hallen" for club in clubs}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_game_count_spread=10,  # very lenient threshold
        )
        plan = planner.build_plan(start, end)

        warnings = planner.game_count_warnings
        spread_warnings = [w for w in warnings if w[3] == "spread"]

        # With a very lenient threshold of 10, spread warnings should not fire
        # for a single-age-group scenario where all teams get equal invites.
        assert len(spread_warnings) == 0, (
            f"unexpected spread warnings with max_game_count_spread=10: {spread_warnings}"
        )

    def test_early_finish_warnings_with_tight_threshold(self):
        """Build a planner with a tiny max_early_finish_gap_days.

        Uses 6 teams with max_teams=3 so some teams skip late tournaments
        while others participate, creating an early-finish spread."""
        from datetime import datetime as _dt

        start, end = _dt(2026, 10, 1), _dt(2026, 12, 31)
        free_dates = _all_weekend_dates(start, end)

        clubs = ["Jar", "Holmen", "Kongsberg", "Skien", "Jutul", "Ringerike"]
        age_groups = ["U10"]
        roster = _build_roster(clubs, age_groups)
        club_arenas = {club: f"{club}hallen" for club in clubs}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_teams_per_tournament_for_age_group={"U10": 3},
            max_early_finish_gap_days=0,  # any gap triggers a warning
        )
        planner.build_plan(start, end)

        warnings = planner.game_count_warnings
        early_warnings = [w for w in warnings if w[3] == "early_finish"]
        # With 6 teams and max 3 per tournament, some teams will miss
        # later tournaments, causing early-finish alerts.
        assert len(early_warnings) >= 1, (
            f"expected at least one early-finish warning with max_early_finish_gap_days=0, "
            f"got: {warnings}"
        )

    def test_team_game_counts_fields_present_on_season_plan(self, planner_and_plan):
        _, plan, *_ = planner_and_plan

        assert isinstance(plan.team_game_counts, dict)
        assert isinstance(plan.team_last_game_dates, dict)
        assert isinstance(plan.game_count_spread, int)

    def test_team_game_counts_includes_invited_teams(self, planner_and_plan):
        _, plan, roster, *_ = planner_and_plan

        # Every team that was invited to at least one tournament should have
        # a game count entry.
        invited_labels = set()
        for tournament in plan.tournaments:
            for team in tournament.teams:
                invited_labels.add(team.label)

        counted_labels = set(plan.team_game_counts.keys())
        assert invited_labels.issubset(counted_labels), (
            f"not all invited teams appear in team_game_counts: "
            f"{invited_labels - counted_labels}"
        )
        # Every team that appears in team_game_counts must have a non-zero count.
        for label, count in plan.team_game_counts.items():
            assert count > 0, f"team {label} has zero game count but appears in team_game_counts"

    def test_game_count_warnings_property_returns_list(self, planner_and_plan):
        planner, *_ = planner_and_plan

        warnings = planner.game_count_warnings
        assert isinstance(warnings, list)
        for w in warnings:
            assert len(w) == 4  # (label, count, threshold/gap, type)
            assert w[3] in ("spread", "early_finish")


class TestSkillLevelDivisions:
    """Tests for skill-level-based participant selection."""

    @pytest.fixture
    def skill_roster(self):
        """8 teams in U10 from distinct clubs, 4 low-skill (1-2) and 4 high-skill (8-10).

        Each team has its own club so the hard max-1-per-club constraint does not
        interfere with skill-level adjacency testing.
        """
        return Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10", skill_level=1),
            Team(club="Holmen", label="Holmen 1", age_group="U10", skill_level=2),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10", skill_level=1),
            Team(club="Skien", label="Skien 1", age_group="U10", skill_level=2),
            Team(club="Jutul", label="Jutul 1", age_group="U10", skill_level=9),
            Team(club="Ringerike", label="Ringerike 1", age_group="U10", skill_level=10),
            Team(club="Tønsberg", label="Tønsberg 1", age_group="U10", skill_level=8),
            Team(club="Sandefjord", label="Sandefjord 1", age_group="U10", skill_level=9),
        ])

    @pytest.fixture
    def free_dates(self):
        start, end = datetime(2026, 10, 1), datetime(2027, 4, 30)
        return _all_weekend_dates(start, end)

    @pytest.fixture
    def skill_planner(self, skill_roster, free_dates):
        club_arenas = {t.club: f"{t.club}hallen" for t in skill_roster.teams}
        return SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=skill_roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_teams_per_tournament_for_age_group={"U10": 4},
            division_skill_band=2,
        )

    def test_teams_without_skill_level_are_grouped_normally(self, free_dates):
        """Plain strings with no skill_level produce identical behaviour."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Holmen", label="Holmen 1", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
            Team(club="Skien", label="Skien 1", age_group="U10"),
            Team(club="Jutul", label="Jutul 1", age_group="U10"),
            Team(club="Ringerike", label="Ringerike 1", age_group="U10"),
            Team(club="Tønsberg", label="Tønsberg 1", age_group="U10"),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}
        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_teams_per_tournament_for_age_group={"U10": 4},
            division_skill_band=2,
        )
        plan = planner.build_plan(datetime(2026, 10, 1), datetime(2027, 4, 30))
        assert len(plan.tournaments) > 0
        # All teams have skill_level=None so _team_skill_levels should be empty
        assert planner._team_skill_levels == {}

    def test_teams_with_skill_level_prefer_adjacent_levels(self, skill_planner):
        """With balanced high/low groups, first tournaments should stay within band."""
        plan = skill_planner.build_plan(datetime(2026, 10, 1), datetime(2027, 4, 30))
        assert len(plan.tournaments) >= 4

        # The first tournament should clearly contain only low- or only high-skill teams
        first_levels = [t.skill_level for t in plan.tournaments[0].teams if t.skill_level is not None]
        assert len(first_levels) == 4
        # All within band-2 of each other: max - min should be <= 2
        assert max(first_levels) - min(first_levels) <= 2, (
            f"first tournament levels too spread: {first_levels}"
        )

        # The second tournament should have the complementary skill group
        second_levels = [t.skill_level for t in plan.tournaments[1].teams if t.skill_level is not None]
        assert len(second_levels) == 4
        assert max(second_levels) - min(second_levels) <= 2, (
            f"second tournament levels too spread: {second_levels}"
        )

        # The two groups should be distinct (one high, one low)
        assert set(first_levels).isdisjoint(set(second_levels)) or (
            max(first_levels) <= 2 and max(second_levels) <= 2
        ), f"groups not cleanly separated: {first_levels} / {second_levels}"

    def test_skill_penalty_is_soft_not_hard(self):
        """When one band has too few teams, teams from other bands are selected."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10", skill_level=1),
            Team(club="Jar", label="Jar 2", age_group="U10", skill_level=9),
            Team(club="Holmen", label="Holmen 1", age_group="U10", skill_level=10),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10", skill_level=8),
            Team(club="Skien", label="Skien 1", age_group="U10", skill_level=9),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}
        start, end = datetime(2026, 10, 1), datetime(2027, 4, 30)
        free_dates = _all_weekend_dates(start, end)
        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_teams_per_tournament_for_age_group={"U10": 4},
            division_skill_band=2,
        )
        plan = planner.build_plan(start, end)
        assert len(plan.tournaments) >= 1
        # With only 1 low-skill team and 4 high-skill, max_teams=4 means the
        # first tournament must include the low-skill team (soft constraint doesn't exclude)
        first_teams = plan.tournaments[0].teams
        levels = [t.skill_level for t in first_teams if t.skill_level is not None]
        assert 1 in levels, (
            f"low-skill team should have been selected (soft constraint): levels={sorted(levels)}"
        )

    def test_mixed_skill_and_unrated_teams(self):
        """Unrated teams (no skill_level) are not penalised and can be selected alongside any band."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10", skill_level=5),
            Team(club="Holmen", label="Holmen 1", age_group="U10", skill_level=6),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),  # unrated
            Team(club="Skien", label="Skien 1", age_group="U10"),  # unrated
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}
        start, end = datetime(2026, 10, 1), datetime(2027, 4, 30)
        free_dates = _all_weekend_dates(start, end)
        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            max_teams_per_tournament_for_age_group={"U10": 4},
            division_skill_band=2,
        )
        plan = planner.build_plan(start, end)
        assert len(plan.tournaments) >= 1
        # All 4 teams fit in one tournament; unrated teams must be included
        assert len(plan.tournaments[0].teams) == 4
        unrated = [t for t in plan.tournaments[0].teams if t.skill_level is None]
        assert len(unrated) == 2, f"unrated teams should be selected: {[t.label for t in plan.tournaments[0].teams]}"

    def test_division_skill_band_configurable(self):
        """A wide band (99) should effectively disable skill filtering."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10", skill_level=1),
            Team(club="Skiptvet", label="Skiptvet 1", age_group="U10", skill_level=10),
            Team(club="Holmen", label="Holmen 1", age_group="U10", skill_level=2),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10", skill_level=9),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}
        start, end = datetime(2026, 10, 1), datetime(2027, 4, 30)
        free_dates = _all_weekend_dates(start, end)
        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 2},
            division_skill_band=99,  # effectively infinite
        )
        plan = planner.build_plan(start, end)
        assert len(plan.tournaments) >= 1
        # With a huge band, level 1 and 10 can coexist
        first_levels = sorted([t.skill_level for t in plan.tournaments[0].teams if t.skill_level is not None])
        assert 1 in first_levels and 10 in first_levels, (
            f"wide band should allow all levels together: {first_levels}"
        )


class TestProportionalHosting:
    """Tests for proportional home-tournament hosting."""

    @pytest.fixture
    def season_window(self):
        return datetime(2026, 10, 1), datetime(2027, 4, 30)

    @pytest.fixture
    def free_dates(self, season_window):
        start, end = season_window
        return _all_weekend_dates(start, end)

    def test_clubs_with_more_teams_host_more_tournaments(self, free_dates, season_window):
        """Jar with 3 teams should host more than Kongsberg with 1 team."""
        start, end = season_window
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Jar", label="Jar 2", age_group="U10"),
            Team(club="Jar", label="Jar 3", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
            Team(club="Skien", label="Skien 1", age_group="U11"),
            Team(club="Holmen", label="Holmen 1", age_group="U11"),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3, "U11": 3},
            max_hosting_deviation=5,  # lenient so no warnings
        )
        plan = planner.build_plan(start, end)

        # Count how many tournaments each club hosted.
        hosting_counts: dict[str, int] = {}
        for t in plan.tournaments:
            if t.host_club:
                hosting_counts[t.host_club] = hosting_counts.get(t.host_club, 0) + 1

        # Jar (3 teams) should host strictly more than Kongsberg (1 team)
        # in a season of ~10-15 tournaments.
        assert hosting_counts.get("Jar", 0) > hosting_counts.get("Kongsberg", 0), (
            f"Jar ({hosting_counts.get('Jar', 0)}) should host more than "
            f"Kongsberg ({hosting_counts.get('Kongsberg', 0)})"
        )

    def test_equal_team_counts_get_equal_hosting(self, free_dates, season_window):
        """All clubs with 1 team each should host roughly equally."""
        start, end = season_window
        clubs = ["Jar", "Holmen", "Kongsberg", "Skien", "Jutul", "Ringerike"]
        roster = _build_roster(clubs, ["U10", "U11"])
        club_arenas = {club: f"{club}hallen" for club in clubs}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3},
            max_hosting_deviation=5,
        )
        plan = planner.build_plan(start, end)

        hosting_counts: dict[str, int] = {}
        for t in plan.tournaments:
            if t.host_club:
                hosting_counts[t.host_club] = hosting_counts.get(t.host_club, 0) + 1

        # All clubs have the same number of teams — hosting counts should
        # be within 1 of each other (total / num_clubs).
        counts = list(hosting_counts.values())
        assert max(counts) - min(counts) <= 1, (
            f"equal-team clubs should host roughly equally: {hosting_counts}"
        )

    def test_every_club_hosts_at_least_once(self, free_dates, season_window):
        """Even single-team clubs host at least one tournament."""
        start, end = season_window
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Jar", label="Jar 2", age_group="U10"),
            Team(club="Jar", label="Jar 3", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
            Team(club="Skien", label="Skien 1", age_group="U11"),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3, "U11": 3},
            max_hosting_deviation=5,
        )
        plan = planner.build_plan(start, end)

        hosted_clubs = {t.host_club for t in plan.tournaments if t.host_club}
        assert "Kongsberg" in hosted_clubs, (
            f"Kongsberg (1 team) should host at least once. Hosting clubs: {hosted_clubs}"
        )
        assert "Skien" in hosted_clubs, (
            f"Skien (1 team) should host at least once. Hosting clubs: {hosted_clubs}"
        )

    def test_hosting_warnings_fire_on_deviation(self, free_dates, season_window):
        """With max_hosting_deviation=0, even a small imbalance triggers warnings."""
        start, end = season_window
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Jar", label="Jar 2", age_group="U10"),
            Team(club="Jar", label="Jar 3", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3},
            max_hosting_deviation=0,  # any deviation triggers warnings
        )
        plan = planner.build_plan(start, end)
        # Force build_plan to run
        assert len(plan.tournaments) > 0

        warnings = planner.hosting_warnings
        # With 3 Jar teams vs 1 Kongsberg team over ~10-15 tournaments,
        # the proportional target won't be perfectly integer-achievable,
        # so warnings should fire with deviation=0.
        # (Jar should host ~75% of tournaments, Kongsberg ~25%)
        assert len(warnings) >= 1, (
            f"expected hosting warnings with max_hosting_deviation=0, "
            f"plan has {len(plan.tournaments)} tournaments, got: {warnings}"
        )

    def test_hosting_warnings_empty_with_lenient_threshold(self, free_dates, season_window):
        """With max_hosting_deviation=99, no warnings should fire."""
        start, end = season_window
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Jar", label="Jar 2", age_group="U10"),
            Team(club="Jar", label="Jar 3", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
            Team(club="Skien", label="Skien 1", age_group="U10"),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3},
            max_hosting_deviation=99,  # effectively unlimited
        )
        plan = planner.build_plan(start, end)
        assert len(plan.tournaments) > 0

        warnings = planner.hosting_warnings
        assert len(warnings) == 0, (
            f"expected no hosting warnings with max_hosting_deviation=99, "
            f"got: {warnings}"
        )

    def test_hosting_warnings_property_returns_list(self, free_dates, season_window):
        """hosting_warnings should always return a list."""
        start, end = season_window
        roster = Roster(teams=[
            Team(club="Jar", label="Jar 1", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
        ])
        club_arenas = {t.club: f"{t.club}hallen" for t in roster.teams}

        planner = SeasonPlanner(
            scheduler=FakeScheduler(free_dates),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3},
        )
        plan = planner.build_plan(start, end)
        assert len(plan.tournaments) > 0

        warnings = planner.hosting_warnings
        assert isinstance(warnings, list)


class TestRulesReport:
    """Tests for the rules-and-decisions transparency report."""

    def test_returns_nonempty_list_with_required_keys(self):
        """rules_report() returns a non-empty list; every entry has regel, forklaring, kategori."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar U10", age_group="U10", skill_level=5),
            Team(club="Kongsberg", label="Kongsberg U10", age_group="U10", skill_level=6),
        ])
        club_arenas = {"Jar": "Jarhallen", "Kongsberg": "Kongsberghallen"}
        planner = SeasonPlanner(
            scheduler=FakeScheduler([]),
            roster=roster,
            club_arenas=club_arenas,
        )
        report = planner.rules_report()

        assert isinstance(report, list)
        assert len(report) >= 8, f"expected at least 8 rules, got {len(report)}"

        for entry in report:
            assert isinstance(entry, dict), f"each entry must be a dict, got {type(entry)}"
            assert "regel" in entry, f"missing 'regel' key in {entry}"
            assert "forklaring" in entry, f"missing 'forklaring' key in {entry}"
            assert "kategori" in entry, f"missing 'kategori' key in {entry}"
            assert entry["kategori"] in {"Hard krav", "Automatisk avgjørelse", "Anbefaling"}, (
                f"unexpected kategori: {entry['kategori']}"
            )

    def test_parallel_games_appear_in_report(self):
        """When parallel_games_for_age_group is configured, it shows in the report."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar U10", age_group="U10"),
            Team(club="Kongsberg", label="Kongsberg U10", age_group="U10"),
            Team(club="Jar", label="Jar U12", age_group="U12"),
        ])
        club_arenas = {"Jar": "Jarhallen", "Kongsberg": "Kongsberghallen"}
        planner = SeasonPlanner(
            scheduler=FakeScheduler([]),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 3, "U12": 2},
        )
        report = planner.rules_report()

        u10_found = any("U10" in r["regel"] and "3" in r["regel"] for r in report)
        u12_found = any("U12" in r["regel"] and "2" in r["regel"] for r in report)
        assert u10_found, f"U10 parallel games not found in report"
        assert u12_found, f"U12 parallel games not found in report"

    def test_hard_constraints_have_correct_category(self):
        """Rules with kategori='Hard krav' cover club limit, skill band, parallel games."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar U10", age_group="U10", skill_level=5),
            Team(club="Kongsberg", label="Kongsberg U10", age_group="U10", skill_level=6),
        ])
        club_arenas = {"Jar": "Jarhallen", "Kongsberg": "Kongsberghallen"}
        planner = SeasonPlanner(
            scheduler=FakeScheduler([]),
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group={"U10": 4},
            division_skill_band=3,
        )
        report = planner.rules_report()

        hard = [r for r in report if r["kategori"] == "Hard krav"]
        assert len(hard) >= 3, f"expected at least 3 hard constraints, got {len(hard)}"

        # Check that key hard constraints are present
        regel_texts = " ".join(r["regel"] for r in hard)
        assert "lag per klubb" in regel_texts.lower(), "missing club limit constraint"
        assert "ferdighet" in regel_texts.lower(), "missing skill band constraint"

    def test_works_before_build_plan(self):
        """rules_report() does not require build_plan() to have been called."""
        roster = Roster(teams=[
            Team(club="Jar", label="Jar U10", age_group="U10"),
        ])
        club_arenas = {"Jar": "Jarhallen"}
        planner = SeasonPlanner(
            scheduler=FakeScheduler([]),
            roster=roster,
            club_arenas=club_arenas,
        )
        # No build_plan() call — should still work
        report = planner.rules_report()
        assert len(report) > 0, "rules_report should work before build_plan"
