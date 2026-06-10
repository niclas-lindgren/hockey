"""Tests for club_distances — distance lookups and furthest-traveling-team logic."""

from tournament_scheduler.models import Team, Tournament
from tournament_scheduler.club_distances import (
    distance,
    arena_to_club,
    furthest_traveling_team,
)


class TestDistanceLookup:
    """Tests for the static club-to-club distance matrix."""

    def test_known_pair_returns_positive_distance(self):
        assert distance("Kongsberg", "Jar") > 50

    def test_lookup_is_symmetric(self):
        assert distance("Kongsberg", "Jar") == distance("Jar", "Kongsberg")

    def test_same_club_returns_zero(self):
        assert distance("Kongsberg", "Kongsberg") == 0

    def test_unknown_club_returns_zero(self):
        assert distance("Kongsberg", "UnknownClub") == 0
        assert distance("UnknownClub", "Jar") == 0

    def test_all_rvv_clubs_have_known_distances(self):
        """Every pair of distinct RVV clubs should have a recorded distance."""
        clubs = [
            "Kongsberg", "Jar", "Holmen", "Ringerike",
            "Skien", "Jutul", "Frisk Asker", "Tønsberg",
            "Sandefjord Penguins",
        ]
        for i, a in enumerate(clubs):
            for b in clubs[i + 1:]:
                assert distance(a, b) > 0, f"missing distance: {a} <-> {b}"


class TestArenaToClub:
    """Tests for arena name → club name resolution."""

    def test_known_arena_returns_club(self):
        assert arena_to_club("Kongsberghallen") == "Kongsberg"
        assert arena_to_club("Jarhallen") == "Jar"

    def test_unknown_arena_returns_none(self):
        assert arena_to_club("Unknown Arena") is None
        assert arena_to_club("") is None


class TestFurthestTravelingTeam:
    """Tests for furthest_traveling_team logic."""

    def test_empty_tournament_returns_none(self):
        t = Tournament(date=None, arena="Kongsberghallen", age_group="U10")
        assert furthest_traveling_team(t) is None

    def test_single_local_team_returns_none(self):
        """A tournament with only the host's own team should return None (no travel)."""
        t = Tournament(
            date=None,
            arena="Kongsberghallen",
            age_group="U10",
            teams=[Team(club="Kongsberg", label="Kongsberg U10", age_group="U10")],
        )
        assert furthest_traveling_team(t) is None

    def test_prefers_farthest_team(self):
        """Jar should be identified as farthest from Kongsberg when
        Jar and Kongsberg are both participants hosted at Kongsberghallen."""
        t = Tournament(
            date=None,
            arena="Kongsberghallen",
            age_group="U10",
            host_club="Kongsberg",
            teams=[
                Team(club="Kongsberg", label="Kongsberg U10", age_group="U10"),
                Team(club="Jar", label="Jar 1", age_group="U10"),
                Team(club="Holmen", label="Holmen U10", age_group="U10"),
            ],
        )
        result = furthest_traveling_team(t)
        assert result is not None
        team, km = result
        # Holmen (~85 km) is slightly farther than Jar (~80 km) from Kongsberg
        assert team.label == "Holmen U10"
        assert km > 50

    def test_unknown_arena_returns_none(self):
        """When the arena is not in the registry, fall back to host_club."""
        t = Tournament(
            date=None,
            arena="Unknown Arena",
            age_group="U10",
            host_club="Kongsberg",
            teams=[
                Team(club="Jar", label="Jar 1", age_group="U10"),
            ],
        )
        result = furthest_traveling_team(t)
        assert result is not None
        team, km = result
        assert team.label == "Jar 1"
        assert km > 50

    def test_no_host_club_and_unknown_arena_returns_none(self):
        """When neither arena nor host_club is known, return None."""
        t = Tournament(
            date=None,
            arena="Unknown Arena",
            age_group="U10",
            host_club=None,
            teams=[
                Team(club="Jar", label="Jar 1", age_group="U10"),
            ],
        )
        assert furthest_traveling_team(t) is None
