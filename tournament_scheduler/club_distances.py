"""Approximate driving distances between RVV club arenas (kilometres).

Provides static distance lookups for the nine Region Viken Vest clubs:

    Kongsberg, Jar, Holmen, Ringerike, Skien, Jutul, Frisk Asker,
    Tønsberg, Sandefjord Penguins

Distances are approximate driving estimates by road between the clubs' home
arenas. They are not precise geodesic distances — they reflect typical travel
times for youth hockey teams driving between halls on a weekend.

Usage::

    from tournament_scheduler.club_distances import distance, furthest_traveling_team
    from tournament_scheduler.models import Tournament

    km = distance("Kongsberg", "Jar")       # -> ~80
    result = furthest_traveling_team(tournament)  # -> (Team, km) or None
"""

from typing import Dict, Optional, Tuple

from tournament_scheduler.models import SeasonPlan, Tournament, Team

# ---------------------------------------------------------------------------
# Club-to-club distance matrix (driving km)
#
# Keyed by (from_club, to_club). Only the upper triangle is stored; lookups
# normalise by sorting the club names so (A, B) and (B, A) resolve the same
# entry.  Unknown pairs default to 0 km (treated as host / data gap).
# ---------------------------------------------------------------------------

_DISTANCE_MATRIX: Dict[Tuple[str, str], int] = {
    # Keys stored in alphabetical order for correct _normalise_key lookup
    # Frisk Asker <-> others
    ("Frisk Asker", "Holmen"): 25,
    ("Frisk Asker", "Jar"): 20,
    ("Frisk Asker", "Jutul"): 20,
    ("Frisk Asker", "Kongsberg"): 60,
    ("Frisk Asker", "Ringerike"): 55,
    ("Frisk Asker", "Sandefjord Penguins"): 100,
    ("Frisk Asker", "Skien"): 100,
    ("Frisk Asker", "Tønsberg"): 80,
    # Holmen <-> others
    ("Holmen", "Jar"): 15,
    ("Holmen", "Jutul"): 15,
    ("Holmen", "Kongsberg"): 85,
    ("Holmen", "Ringerike"): 55,
    ("Holmen", "Sandefjord Penguins"): 125,
    ("Holmen", "Skien"): 130,
    ("Holmen", "Tønsberg"): 105,
    # Jar <-> others (Jar is in Bærum, close to Jutul/Asker/Holmen)
    ("Jar", "Jutul"): 5,
    ("Jar", "Kongsberg"): 80,
    ("Jar", "Ringerike"): 50,
    ("Jar", "Sandefjord Penguins"): 120,
    ("Jar", "Skien"): 120,
    ("Jar", "Tønsberg"): 100,
    # Jutul <-> others (Bærum, very close to Jar)
    ("Jutul", "Kongsberg"): 80,
    ("Jutul", "Ringerike"): 50,
    ("Jutul", "Sandefjord Penguins"): 120,
    ("Jutul", "Skien"): 120,
    ("Jutul", "Tønsberg"): 100,
    # Kongsberg <-> others
    ("Kongsberg", "Ringerike"): 45,
    ("Kongsberg", "Sandefjord Penguins"): 95,
    ("Kongsberg", "Skien"): 65,
    ("Kongsberg", "Tønsberg"): 75,
    # Ringerike <-> others
    ("Ringerike", "Sandefjord Penguins"): 140,
    ("Ringerike", "Skien"): 150,
    ("Ringerike", "Tønsberg"): 120,
    # Skien <-> Sandefjord
    ("Sandefjord Penguins", "Skien"): 35,
    # Tønsberg <-> Sandefjord
    ("Sandefjord Penguins", "Tønsberg"): 15,
    # Skien <-> Tønsberg
    ("Skien", "Tønsberg"): 30,
}

# ---------------------------------------------------------------------------
# Arena-to-club reverse mapping
#
# Maps arena names (e.g. "Kongsberghallen") back to the club name they
# belong to, so we can resolve which club a team's travel endpoint is.
# ---------------------------------------------------------------------------

_ARENA_TO_CLUB: Dict[str, str] = {
    "Kongsberghallen": "Kongsberg",
    "Jarhallen": "Jar",
    "Holmenkollen ishall": "Holmen",
    "Ringerikshallen": "Ringerike",
    "Skien ishall": "Skien",
    "Bærum ishall": "Jutul",
    "Varner Arena": "Frisk Asker",
    "Tønsberghallen": "Tønsberg",
    "Sandefjord ishall": "Sandefjord Penguins",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def distance(club_a: str, club_b: str) -> int:
    """Return the approximate driving distance in km between two clubs' arenas.

    The lookup is symmetric — the order of arguments does not matter.
    Returns 0 when the distance for a given pair is unknown (e.g. one of
    the clubs is not in the RVV region).
    """
    key = _normalise_key(club_a, club_b)
    return _DISTANCE_MATRIX.get(key, 0)


def arena_to_club(arena: str) -> Optional[str]:
    """Return the club name that owns *arena*, or ``None`` if unknown."""
    return _ARENA_TO_CLUB.get(arena)


def furthest_traveling_team(
    tournament: Tournament,
) -> Optional[Tuple[Team, int]]:
    """Return the team in *tournament* with the longest estimated travel to
    the host arena, along with the distance in km.

    Returns ``(team, distance_km)`` when there is at least one participating
    team from a different club than the host, and the host arena can be
    mapped back to a club. Returns ``None`` when the tournament has no
    participants, the host is unknown, or all participants are local
    (distance 0).
    """
    if not tournament.teams or not tournament.arena:
        return None

    host_club_name = arena_to_club(tournament.arena)
    if host_club_name is None:
        # If we can't map the arena to a known club, try using host_club
        # directly (some tournaments set host_club instead).
        host_club_name = tournament.host_club
    if host_club_name is None:
        return None

    best: Optional[Tuple[Team, int]] = None

    for team in tournament.teams:
        team_club = team.club
        if team_club == host_club_name:
            # Local team — distance 0, skip unless all are local.
            continue
        km = distance(team_club, host_club_name)
        if km > 0 and (best is None or km > best[1]):
            best = (team, km)

    return best


def compute_team_travel_distances(plan: SeasonPlan) -> dict[str, int]:
    """Return a dict mapping each team label to its total travel distance
    (km) across all *away* tournaments in the season plan.

    An *away* tournament is one where the host club differs from the team's
    club.  Cancelled tournaments are skipped.  Teams that never travel to an
    away tournament still appear in the dict with a value of 0.
    """
    totals: dict[str, int] = {}

    for tournament in plan.tournaments:
        if tournament.cancelled:
            continue

        # Resolve host club — same pattern as furthest_traveling_team
        host_club = arena_to_club(tournament.arena)
        if host_club is None:
            host_club = tournament.host_club

        for team in tournament.teams:
            # Ensure every team appears in the dict at least once
            if team.label not in totals:
                totals[team.label] = 0

            if host_club is None:
                # Unknown host — can't compute travel, but team is registered
                continue

            team_club = team.club
            if team_club == host_club:
                # Local tournament — no travel distance added
                continue

            km = distance(team_club, host_club)
            totals[team.label] += km

    return totals


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_key(club_a: str, club_b: str) -> Tuple[str, str]:
    """Normalise a club pair so lookups are symmetric."""
    return (club_a, club_b) if club_a <= club_b else (club_b, club_a)
