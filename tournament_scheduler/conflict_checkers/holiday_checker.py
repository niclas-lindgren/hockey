"""Holiday conflict checker."""

from datetime import date, timedelta
from typing import List
import holidays
from tournament_scheduler.interfaces import ConflictChecker
from tournament_scheduler.models import ConflictContext, ConflictResult


class HolidayConflictChecker(ConflictChecker):
    """Checks for conflicts with Norwegian public holidays."""

    def __init__(self, country: str = 'NO'):
        """Initialize holiday checker.

        Args:
            country: Country code for holidays
        """
        self.country = country
        self.holidays = holidays.Norway()

    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check for holiday week conflicts and weekends before holidays.

        Args:
            dates: Dates to check
            context: Context with date range

        Returns:
            ConflictResult with excluded dates
        """
        excluded_dates = set()
        reasons = {}

        # Find all holiday weeks in date range
        holiday_weeks = self._get_holiday_weeks(context.start_date, context.end_date)

        # Find weekends before holidays
        weekends_before_holidays = self._get_weekends_before_holidays(context.start_date, context.end_date)

        for check_date in dates:
            # Check if in holiday week
            if check_date in holiday_weeks:
                excluded_dates.add(check_date)
                # Find which holiday caused this exclusion
                week_start = check_date - timedelta(days=check_date.weekday())
                for i in range(7):
                    day = week_start + timedelta(days=i)
                    if day in self.holidays:
                        holiday_name = self.holidays.get(day)
                        reasons[check_date] = f"Holiday week: {holiday_name}"
                        break
                if check_date not in reasons:
                    reasons[check_date] = "Holiday week"

            # Check if weekend before holiday
            elif check_date in weekends_before_holidays:
                excluded_dates.add(check_date)
                holiday_name = weekends_before_holidays[check_date]
                reasons[check_date] = f"Weekend before: {holiday_name}"

        return ConflictResult(
            excluded_dates=excluded_dates,
            reasons=reasons,
            checker_name=self.get_checker_name()
        )

    def get_checker_name(self) -> str:
        """Get checker name.

        Returns:
            'holiday_week'
        """
        return 'holiday_week'

    def _get_holiday_weeks(self, start_date, end_date) -> set:
        """Get all dates in weeks containing holidays.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            Set of dates in holiday weeks
        """
        holiday_weeks = set()
        current = start_date
        while current <= end_date:
            if current.date() in self.holidays:
                # Add entire week
                week_start = current - timedelta(days=current.weekday())
                for i in range(7):
                    week_day = week_start + timedelta(days=i)
                    holiday_weeks.add(week_day.date())
            current += timedelta(days=1)
        return holiday_weeks

    def _get_weekends_before_holidays(self, start_date, end_date) -> dict:
        """Get weekends that occur immediately before public holidays.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            Dict mapping weekend dates to holiday names
        """
        weekends_before = {}

        # Extend search to 10 days after end_date to catch holidays just outside range
        # This ensures we block weekends before holidays that start right after our range
        extended_end = end_date + timedelta(days=10)

        current = start_date
        while current <= extended_end:
            if current.date() in self.holidays:
                holiday_name = self.holidays.get(current.date())
                # Find the preceding Saturday and Sunday
                # If holiday is on Monday (weekday 0), preceding weekend is days -2 and -1
                # If holiday is on Tuesday (weekday 1), preceding weekend is days -3 and -2
                # etc.
                days_since_monday = current.weekday()
                if days_since_monday >= 0:  # Monday to Sunday
                    # Calculate Saturday (day -2 to -1 days before Monday)
                    saturday = current - timedelta(days=days_since_monday + 2)
                    sunday = current - timedelta(days=days_since_monday + 1)

                    # Only add weekends that fall within our ACTUAL search range
                    if saturday.weekday() == 5 and start_date.date() <= saturday.date() <= end_date.date():
                        weekends_before[saturday.date()] = holiday_name
                    if sunday.weekday() == 6 and start_date.date() <= sunday.date() <= end_date.date():
                        weekends_before[sunday.date()] = holiday_name
            current += timedelta(days=1)
        return weekends_before
