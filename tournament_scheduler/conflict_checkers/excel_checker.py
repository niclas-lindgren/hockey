"""Excel conflict checker."""

from datetime import date
from typing import List, Set
from tournament_scheduler.interfaces import ConflictChecker
from tournament_scheduler.models import ConflictContext, ConflictResult


class ExcelConflictChecker(ConflictChecker):
    """Checks for conflicts with dates in Excel exclusion list."""

    def __init__(self, excel_dates: Set[date]):
        """Initialize Excel checker.

        Args:
            excel_dates: Set of dates to exclude from Excel
        """
        self.excel_dates = excel_dates

    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check for Excel exclusion conflicts.

        Args:
            dates: Dates to check
            context: Context (excel_dates will be used from init)

        Returns:
            ConflictResult with excluded dates
        """
        excluded_dates = set()
        reasons = {}

        for check_date in dates:
            if check_date in self.excel_dates:
                excluded_dates.add(check_date)
                reasons[check_date] = "Excel exclusion list"

        return ConflictResult(
            excluded_dates=excluded_dates,
            reasons=reasons,
            checker_name=self.get_checker_name()
        )

    def get_checker_name(self) -> str:
        """Get checker name.

        Returns:
            'excel'
        """
        return 'excel'
