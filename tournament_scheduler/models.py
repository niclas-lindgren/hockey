"""Data models for tournament scheduling."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Set, Optional, Tuple


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
