"""Data models for tournament scheduling."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Set, Optional, Tuple
import uuid


@dataclass
class CalendarEvent:
    """Represents a calendar event with scheduling information."""

    date: str  # Format: DD.MM.YYYY
    name: str
    datetime: datetime
    duration_hours: float = 0.0


@dataclass
class TournamentInfo:
    """Information about a tournament extracted from Excel."""

    date: date
    name: str
    teams: List[str]
    location: Optional[str] = None


@dataclass
class ConflictContext:
    """Context containing all data needed for conflict checking."""

    start_date: datetime
    end_date: datetime
    team_names: List[str] = field(default_factory=list)
    calendar_events: List[CalendarEvent] = field(default_factory=list)
    excel_dates: Set[date] = field(default_factory=set)
    tournament_to_reschedule: Optional[date] = None


@dataclass
class ConflictResult:
    """Result of a conflict check operation."""

    excluded_dates: Set[date]
    reasons: Dict[date, str]
    checker_name: str


@dataclass
class SchedulingResult:
    """Complete result of a scheduling operation."""

    available_dates: List[date]
    excluded_dates: List[date]
    exclusion_breakdown: Dict[str, int]
    detailed_exclusions: List[Tuple[date, str]]
    total_weekends_checked: int
    tournament_info: Optional[TournamentInfo] = None


@dataclass
class Team:
    """A single team belonging to a club, in a specific age group.

    Example: Team(club="Jar", label="Jar 1", age_group="U10")
    """

    club: str
    label: str  # e.g. "Jar 1", "Jar 2"
    age_group: str  # e.g. "U10", "JU11"

    @property
    def name(self) -> str:
        """Display name for the team (defaults to its label)."""
        return self.label


@dataclass
class Roster:
    """An ordered collection of teams participating in the season plan."""

    teams: List[Team] = field(default_factory=list)

    def by_age_group(self, age_group: str) -> List[Team]:
        """Return all teams belonging to the given age group, in roster order."""
        return [team for team in self.teams if team.age_group == age_group]

    def age_groups(self) -> List[str]:
        """Return the distinct age groups present in the roster, in first-seen order."""
        seen: List[str] = []
        for team in self.teams:
            if team.age_group not in seen:
                seen.append(team.age_group)
        return seen

    def clubs(self) -> List[str]:
        """Return the distinct club names present in the roster, in first-seen order."""
        seen: List[str] = []
        for team in self.teams:
            if team.club not in seen:
                seen.append(team.club)
        return seen


@dataclass
class Game:
    """A single round-robin game within a tournament."""

    home: Team
    away: Team
    parallel_slot: int = 0  # which parallel timeslot/sheet this game is played in


@dataclass
class Tournament:
    """A single weekend tournament: one age group/gender, hosted at one arena.

    Holds the ordered list of participating teams and the round-robin game
    schedule generated for them (every participating team plays every other
    participating team once).
    """

    date: date
    arena: str  # host club's home arena, e.g. "Jarhallen"
    age_group: str  # e.g. "U10", "JU11" — one age group/gender per tournament
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    teams: List[Team] = field(default_factory=list)
    games: List[Game] = field(default_factory=list)
    host_club: Optional[str] = None


@dataclass
class SeasonPlan:
    """A full proposed season plan: an ordered sequence of tournaments plus metadata."""

    tournaments: List[Tournament] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    diversity_score: float = 0.0
    # Fraction of scheduled matchups (pairwise team-vs-team games) that are
    # first-time pairings, grounded in actual `_opponent_history` counts
    # rather than mere tournament co-attendance (1.0 = every scheduled game
    # is a fresh matchup; lower values indicate more repeat matchups).
    pairwise_matchup_score: float = 0.0
    # How evenly tournaments are spread across the season's months: 1.0
    # means every month carries exactly its expected share of the season's
    # tournament load; lower values indicate more uneven month-to-month
    # distribution (derived from `_month_counts` vs. the expected average).
    month_balance_score: float = 0.0
    # Maps arena/host-club name -> number of tournaments scheduled there
    arena_counts: Dict[str, int] = field(default_factory=dict)


# Mapping of age groups whose player pools are known to overlap (e.g. a player
# might play in both groups). The planner should avoid scheduling tournaments
# for overlapping age groups on the same weekend to prevent double-booking.
# The mapping is symmetric — each key's value list should also list the key
# back, so lookups work in either direction.
AGE_GROUP_OVERLAP: Dict[str, List[str]] = {
    "U10": ["JU11"],
    "JU11": ["U10"],
    "U11": ["JU12"],
    "JU12": ["U11"],
    "U12": ["JU13"],
    "JU13": ["U12"],
}


def overlapping_age_groups(age_group: str) -> List[str]:
    """Return the list of age groups whose player pools overlap with the given one."""
    return AGE_GROUP_OVERLAP.get(age_group, [])
