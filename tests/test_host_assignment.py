"""Tests verifying that the home team in generated games is the arena-owning club.

These tests cover:
- club_for_arena reverse-lookup in the club registry
- The host-first participant ordering in game generation
- The end-to-end invariant: game.home.club == arena owner for all rounds
"""

import pytest

from tournament_scheduler.club_registry import club_for_arena
from tournament_scheduler.models import Team
from tournament_scheduler.season_planner import SeasonPlanner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_teams(clubs, age_group="U10"):
    """Create one Team per club name."""
    return [
        Team(club=club, label=f"{club}-A", age_group=age_group)
        for club in clubs
    ]


def _host_first(participants, arena):
    """Reorder participants so the arena-owning club's team is first."""
    home_club = club_for_arena(arena)
    if home_club is None:
        return participants
    host_teams = [t for t in participants if t.club == home_club]
    other_teams = [t for t in participants if t.club != home_club]
    return (host_teams + other_teams) if host_teams else participants


# ---------------------------------------------------------------------------
# club_for_arena unit tests
# ---------------------------------------------------------------------------


class TestClubForArena:
    def test_varner_arena_maps_to_frisk_asker(self):
        assert club_for_arena("Varner Arena") == "Frisk Asker"

    def test_kongsberghallen_maps_to_kongsberg(self):
        assert club_for_arena("Kongsberghallen") == "Kongsberg"

    def test_case_insensitive_match(self):
        assert club_for_arena("varner arena") == "Frisk Asker"
        assert club_for_arena("KONGSBERGHALLEN") == "Kongsberg"

    def test_unknown_arena_returns_none(self):
        assert club_for_arena("Ukjent hall") is None

    def test_whitespace_stripped(self):
        assert club_for_arena("  Varner Arena  ") == "Frisk Asker"

    def test_all_registered_arenas_resolve(self):
        """Every arena in CLUB_REGISTRY should resolve back to its club."""
        from tournament_scheduler.club_registry import CLUB_REGISTRY
        for club_name, entry in CLUB_REGISTRY.items():
            result = club_for_arena(entry.arena)
            assert result == club_name, (
                f"club_for_arena('{entry.arena}') returned {result!r}, expected {club_name!r}"
            )


# ---------------------------------------------------------------------------
# Host-first participant ordering -> game.home invariant
# ---------------------------------------------------------------------------


class TestHomeTeamIsAlwaysHostClub:
    """When the arena-owning club's team is placed first in participants,
    it must appear as game.home in every game IT PLAYS (never as away)."""

    def test_frisk_asker_is_home_in_their_games_at_varner_arena(self):
        """Frisk Asker must appear as game.home in every game they play."""
        arena = "Varner Arena"
        clubs = ["Frisk Asker", "Kongsberg", "Skien", "Ringerike"]
        participants = _make_teams(clubs)
        ordered = _host_first(participants, arena)

        games = SeasonPlanner.generate_round_robin_games(ordered, parallel_games=2)

        assert len(games) > 0, "expected at least one game"
        # Every game involving Frisk Asker: they must be home, never away
        fa_games = [
            g for g in games
            if g.home.club == "Frisk Asker" or g.away.club == "Frisk Asker"
        ]
        assert len(fa_games) > 0, "Frisk Asker should play at least one game"
        for game in fa_games:
            assert game.home.club == "Frisk Asker", (
                f"Expected Frisk Asker as home in their game, got {game.home.club!r}"
            )

    def test_kongsberg_is_home_in_their_games_at_kongsberghallen(self):
        arena = "Kongsberghallen"
        clubs = ["Kongsberg", "Frisk Asker", "Jar", "Holmen"]
        participants = _make_teams(clubs)
        ordered = _host_first(participants, arena)

        games = SeasonPlanner.generate_round_robin_games(ordered, parallel_games=2)

        assert len(games) > 0
        kg_games = [
            g for g in games
            if g.home.club == "Kongsberg" or g.away.club == "Kongsberg"
        ]
        assert len(kg_games) > 0
        for game in kg_games:
            assert game.home.club == "Kongsberg", (
                f"Expected Kongsberg as home in their games, got {game.home.club!r}"
            )

    def test_host_first_ordering_is_applied_regardless_of_input_order(self):
        """Even if the host club is last in the original list, reordering places them first."""
        arena = "Varner Arena"
        # Deliberately put Frisk Asker last
        clubs = ["Kongsberg", "Skien", "Ringerike", "Frisk Asker"]
        participants = _make_teams(clubs)
        ordered = _host_first(participants, arena)

        assert ordered[0].club == "Frisk Asker", (
            "After reordering, Frisk Asker must be first in the list"
        )
        games = SeasonPlanner.generate_round_robin_games(ordered, parallel_games=2)
        fa_games = [g for g in games if g.home.club == "Frisk Asker" or g.away.club == "Frisk Asker"]
        for game in fa_games:
            assert game.home.club == "Frisk Asker"

    def test_host_games_home_across_all_rounds(self):
        """The host-as-home invariant holds across every round, not just round 1."""
        arena = "Varner Arena"
        clubs = ["Frisk Asker", "Kongsberg", "Skien", "Ringerike", "Jar"]
        participants = _make_teams(clubs)
        ordered = _host_first(participants, arena)

        games = SeasonPlanner.generate_round_robin_games(ordered, parallel_games=2)

        round_numbers = sorted({g.round_number for g in games})
        assert len(round_numbers) > 1, "expected multiple rounds"
        for rn in round_numbers:
            round_games = [g for g in games if g.round_number == rn]
            fa_round_games = [
                g for g in round_games
                if g.home.club == "Frisk Asker" or g.away.club == "Frisk Asker"
            ]
            for game in fa_round_games:
                assert game.home.club == "Frisk Asker", (
                    f"Round {rn}: Frisk Asker must be home in their game, got {game.home.club!r}"
                )

    def test_no_host_team_in_participants_does_not_crash(self):
        """When the host club has no team in the participant list, order is unchanged."""
        arena = "Varner Arena"
        clubs = ["Kongsberg", "Skien", "Ringerike"]
        participants = _make_teams(clubs)
        ordered = _host_first(participants, arena)

        # Order unchanged — no Frisk Asker team present
        assert [t.club for t in ordered] == [t.club for t in participants]
        games = SeasonPlanner.generate_round_robin_games(ordered, parallel_games=2)
        assert len(games) > 0
