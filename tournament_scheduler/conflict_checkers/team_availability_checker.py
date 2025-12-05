"""Team availability conflict checker - KEY for rescheduling feature."""

from datetime import date
from typing import List, Set
from tournament_scheduler.interfaces import ConflictChecker
from tournament_scheduler.models import ConflictContext, ConflictResult, CalendarEvent
from tournament_scheduler.utils.date_parser import DateParser


class TeamAvailabilityChecker(ConflictChecker):
    """Checks if specific teams are available on dates."""

    def __init__(self, calendar_events: List[CalendarEvent]):
        """Initialize team availability checker.

        Args:
            calendar_events: All calendar events to check against
        """
        self.calendar_events = calendar_events

    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check team availability on dates.

        Args:
            dates: Dates to check
            context: Context with team names to check

        Returns:
            ConflictResult with dates where teams are unavailable
        """
        excluded_dates = set()
        reasons = {}

        # If no teams specified, pass all dates
        if not context.team_names:
            return ConflictResult(
                excluded_dates=set(),
                reasons={},
                checker_name=self.get_checker_name()
            )

        print(f"\nChecking availability for {len(context.team_names)} teams against {len(self.calendar_events)} calendar events...")

        # Check each date for team conflicts
        conflicts_found = []
        for check_date in dates:
            conflicts = self._check_team_conflicts_on_date(check_date, context.team_names)
            if conflicts:
                excluded_dates.add(check_date)
                team_conflicts = ', '.join([f"{team}" for team, _ in conflicts[:2]])
                if len(conflicts) > 2:
                    team_conflicts += f" and {len(conflicts) - 2} more"
                reasons[check_date] = f"Team conflict: {team_conflicts}"
                conflicts_found.append((check_date, conflicts))

        if conflicts_found:
            print(f"\n⚠️  TEAM CONFLICTS FOUND ({len(conflicts_found)} dates blocked):")
            for check_date, conflicts in conflicts_found[:10]:  # Show first 10
                for team, event in conflicts[:2]:  # Show first 2 conflicts per date
                    print(f"  - {check_date.strftime('%Y-%m-%d')}: {team} has '{event[:60]}'")
            if len(conflicts_found) > 10:
                print(f"  ... and {len(conflicts_found) - 10} more dates with conflicts")
        else:
            print(f"  ✓ All {len(dates)} dates are free for all teams")

        return ConflictResult(
            excluded_dates=excluded_dates,
            reasons=reasons,
            checker_name=self.get_checker_name()
        )

    def get_checker_name(self) -> str:
        """Get checker name.

        Returns:
            'team_conflict'
        """
        return 'team_conflict'

    def _check_team_conflicts_on_date(self, check_date: date, team_names: List[str]) -> List[tuple]:
        """Check if any teams have conflicts on a specific date.

        Args:
            check_date: Date to check
            team_names: Team names to check for

        Returns:
            List of (team_name, event_name) tuples for conflicting teams
        """
        conflicts = []

        for event in self.calendar_events:
            parsed = DateParser.parse(event.date)
            if parsed and parsed.date() == check_date:
                event_name_lower = event.name.lower()
                for team in team_names:
                    # Flexible matching - normalize spaces and check words
                    team_lower = team.lower().strip()
                    team_normalized = team_lower.replace(' ', '').replace('-', '')
                    event_normalized = event_name_lower.replace(' ', '').replace('-', '').replace('/', '')

                    # Check if team name (or normalized version) appears in event
                    if (team_lower in event_name_lower or
                        team_normalized in event_normalized or
                        any(word in event_name_lower for word in team_lower.split() if len(word) > 3)):
                        conflicts.append((team, event.name))
                        break  # Don't count same team twice for same event

        return conflicts
