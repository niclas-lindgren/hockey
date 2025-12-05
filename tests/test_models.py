"""Tests for data models."""

from datetime import datetime, date
from tournament_scheduler.models import (
    CalendarEvent,
    TournamentInfo,
    ConflictContext,
    ConflictResult,
    SchedulingResult
)


class TestModels:
    """Test suite for data models."""

    def test_calendar_event_creation(self):
        """Test CalendarEvent creation."""
        event = CalendarEvent(
            date='17.01.2026',
            name='Test Tournament',
            datetime=datetime(2026, 1, 17, 14, 0),
            duration_hours=3.5
        )
        assert event.date == '17.01.2026'
        assert event.name == 'Test Tournament'
        assert event.duration_hours == 3.5

    def test_tournament_info_creation(self):
        """Test TournamentInfo creation."""
        info = TournamentInfo(
            date=date(2026, 1, 17),
            name='Winter Cup',
            teams=['Team A', 'Team B'],
            location='Kongsberg'
        )
        assert len(info.teams) == 2
        assert info.location == 'Kongsberg'

    def test_conflict_context_defaults(self):
        """Test ConflictContext with default values."""
        context = ConflictContext(
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 6, 30)
        )
        assert context.team_names == []
        assert context.calendar_events == []
        assert context.excel_dates == set()
        assert context.tournament_to_reschedule is None

    def test_conflict_result_creation(self):
        """Test ConflictResult creation."""
        result = ConflictResult(
            excluded_dates={date(2026, 1, 17)},
            reasons={date(2026, 1, 17): 'Ice hall conflict'},
            checker_name='IceHallChecker'
        )
        assert len(result.excluded_dates) == 1
        assert result.checker_name == 'IceHallChecker'

    def test_scheduling_result_creation(self):
        """Test SchedulingResult creation."""
        result = SchedulingResult(
            available_dates=[date(2026, 2, 14), date(2026, 2, 15)],
            excluded_dates=[date(2026, 1, 17)],
            exclusion_breakdown={'ice_hall': 1, 'team_conflict': 0},
            detailed_exclusions=[(date(2026, 1, 17), 'Ice hall: Tournament X')],
            total_weekends_checked=10
        )
        assert len(result.available_dates) == 2
        assert result.total_weekends_checked == 10
