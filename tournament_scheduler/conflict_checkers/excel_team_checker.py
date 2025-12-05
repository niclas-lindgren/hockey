"""Excel team conflict checker - checks if teams have other games in Excel."""

from datetime import date, timedelta
from typing import List, Set, Dict, Tuple
from tournament_scheduler.interfaces import ConflictChecker
from tournament_scheduler.models import ConflictContext, ConflictResult
from tournament_scheduler.utils.date_parser import DateParser
import openpyxl


class ExcelTeamConflictChecker(ConflictChecker):
    """Checks if teams have other games scheduled in the Excel file."""

    def __init__(self, excel_file: str, tournament_teams: List[str], date_parser: DateParser):
        """Initialize Excel team conflict checker.

        Args:
            excel_file: Path to Excel file with schedule
            tournament_teams: List of team names to check for
            date_parser: DateParser instance
        """
        self.excel_file = excel_file
        self.tournament_teams = tournament_teams
        self.date_parser = date_parser
        self.weekend_warnings = {}  # Store weekend conflict warnings

    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check for team conflicts in Excel file.

        Args:
            dates: Dates to check
            context: Context with additional info

        Returns:
            ConflictResult with dates where teams have other games on same date (blocked)
            Weekend conflicts are stored as warnings but don't block dates
        """
        excluded_dates = set()
        reasons = {}
        self.weekend_warnings = {}

        if not self.tournament_teams:
            return ConflictResult(
                excluded_dates=set(),
                reasons={},
                checker_name=self.get_checker_name()
            )

        print(f"\nChecking Excel file for team conflicts ({len(self.tournament_teams)} teams)...")

        # Scan Excel file for team mentions with event details
        team_events = self._find_team_events_in_excel()

        same_day_conflicts = []
        weekend_conflicts = []

        for check_date in dates:
            # Check for same-day conflicts (these block the date)
            conflicting_teams = []
            for team in self.tournament_teams:
                if check_date in team_events.get(team, {}):
                    conflicting_teams.append(team)

            if conflicting_teams:
                excluded_dates.add(check_date)
                team_list = ', '.join(conflicting_teams[:2])
                if len(conflicting_teams) > 2:
                    team_list += f" and {len(conflicting_teams) - 2} more"
                reasons[check_date] = f"Excel: {team_list} have other games"
                same_day_conflicts.append((check_date, conflicting_teams))
            else:
                # Check for same-weekend conflicts (these warn but don't block)
                weekend_date = self._get_weekend_pair(check_date)
                if weekend_date:
                    warning_teams = []
                    for team in self.tournament_teams:
                        if weekend_date in team_events.get(team, {}):
                            event_name = team_events[team][weekend_date]
                            warning_teams.append((team, event_name, weekend_date))

                    if warning_teams:
                        self.weekend_warnings[check_date] = warning_teams
                        weekend_conflicts.append((check_date, warning_teams))

        if same_day_conflicts:
            print(f"\n⚠️  EXCEL SAME-DAY CONFLICTS ({len(same_day_conflicts)} dates blocked):")
            for check_date, teams in same_day_conflicts[:10]:
                teams_str = ', '.join(teams[:3])
                if len(teams) > 3:
                    teams_str += f" +{len(teams) - 3} more"
                print(f"  - {check_date.strftime('%Y-%m-%d')}: {teams_str}")
            if len(same_day_conflicts) > 10:
                print(f"  ... and {len(same_day_conflicts) - 10} more dates")

        if weekend_conflicts:
            print(f"\n⚠️  WEEKEND CONFLICTS (same weekend, different day - {len(weekend_conflicts)} warnings):")
            for check_date, warning_teams in weekend_conflicts[:10]:
                for team, event, conflict_date in warning_teams[:2]:
                    print(f"  - {check_date.strftime('%Y-%m-%d')}: {team} plays {conflict_date.strftime('%Y-%m-%d')} - {event[:50]}")
            if len(weekend_conflicts) > 10:
                print(f"  ... and {len(weekend_conflicts) - 10} more warnings")

        if not same_day_conflicts and not weekend_conflicts:
            print(f"  ✓ No team conflicts found in Excel file")

        return ConflictResult(
            excluded_dates=excluded_dates,
            reasons=reasons,
            checker_name=self.get_checker_name()
        )

    def get_checker_name(self) -> str:
        """Get checker name.

        Returns:
            'excel_team_conflict'
        """
        return 'excel_team_conflict'

    def _find_team_events_in_excel(self) -> Dict[str, Dict[date, str]]:
        """Find all dates where each team appears in the Excel file with event names.

        Returns:
            Dict mapping team name to dict of (date -> event_name)
        """
        team_events = {team: {} for team in self.tournament_teams}

        try:
            wb = openpyxl.load_workbook(self.excel_file, data_only=True)
            ws = wb.active

            # Scan all cells for dates and team names
            current_date = None
            current_event = "Unknown event"

            for row_idx, row in enumerate(ws.iter_rows(min_row=1, values_only=True), start=1):
                # Check for dates in this row
                date_found = False
                for cell in row:
                    parsed = self.date_parser.parse_datetime_cell(cell)
                    if parsed:
                        current_date = parsed.date()
                        date_found = True
                        # Try to find event name in the same row
                        for other_cell in row:
                            if other_cell and isinstance(other_cell, str) and len(str(other_cell).strip()) > 5:
                                potential_event = str(other_cell).strip()
                                # Look for location/venue info
                                if any(keyword in potential_event.lower() for keyword in ['hall', 'arena', 'forum', 'turnering', 'tournament']):
                                    current_event = potential_event
                                    break
                        break

                # Check for team names in this row
                if current_date:
                    for cell in row:
                        if cell and isinstance(cell, str):
                            cell_str = str(cell).strip()

                            # Check each team
                            for team in self.tournament_teams:
                                if self._team_matches(team, cell_str):
                                    # Store event name with the date
                                    if current_date not in team_events[team]:
                                        team_events[team][current_date] = current_event

            wb.close()

        except Exception as e:
            print(f"  Warning: Could not scan Excel file for team events: {e}")

        return team_events

    def _get_weekend_pair(self, check_date: date) -> date:
        """Get the other day of the same weekend.

        Args:
            check_date: Date to find weekend pair for

        Returns:
            The other weekend date (Saturday if input is Sunday, Sunday if input is Saturday)
            None if not a weekend day
        """
        weekday = check_date.weekday()

        if weekday == 5:  # Saturday
            return check_date + timedelta(days=1)  # Sunday
        elif weekday == 6:  # Sunday
            return check_date - timedelta(days=1)  # Saturday
        else:
            return None

    def _team_matches(self, team: str, text: str) -> bool:
        """Check if a team name matches text.

        Args:
            team: Team name to look for
            text: Text to search in

        Returns:
            True if team matches
        """
        team_lower = team.lower().strip()
        text_lower = text.lower().strip()

        # Exact match
        if team_lower == text_lower:
            return True

        # Normalize spaces and hyphens
        team_normalized = team_lower.replace(' ', '').replace('-', '')
        text_normalized = text_lower.replace(' ', '').replace('-', '').replace('/', '')

        # Check normalized match
        if team_normalized == text_normalized:
            return True

        # Check if team appears as a word in the text
        # But be more strict - need at least 2 significant words to match
        team_words = [w for w in team_lower.split() if len(w) > 2]
        text_words = set(text_lower.split())

        if len(team_words) >= 2:
            # Need at least 2 words to match
            matches = sum(1 for word in team_words if word in text_words)
            if matches >= 2:
                return True

        # For single-word teams or short teams, require exact substring match
        if team_lower in text_lower:
            return True

        return False
