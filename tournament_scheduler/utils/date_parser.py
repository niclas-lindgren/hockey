"""Centralized date parsing utility - Single source of truth for all date parsing."""

from datetime import datetime, date
from typing import Optional, Any


class DateParser:
    """Handles all date parsing with consistent format support."""

    SUPPORTED_FORMATS = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']

    @staticmethod
    def parse(date_str: str) -> Optional[datetime]:
        """Parse date string using all supported formats.

        Args:
            date_str: Date string in any supported format

        Returns:
            datetime object if parsing succeeds, None otherwise
        """
        if not date_str or not isinstance(date_str, str):
            return None

        date_str = date_str.strip()
        if not date_str:
            return None

        for date_format in DateParser.SUPPORTED_FORMATS:
            try:
                return datetime.strptime(date_str, date_format)
            except (ValueError, AttributeError):
                continue

        return None

    @staticmethod
    def parse_datetime_cell(cell: Any) -> Optional[datetime]:
        """Parse datetime from Excel cell value.

        Args:
            cell: Excel cell value (can be datetime object or string)

        Returns:
            datetime object if parsing succeeds, None otherwise
        """
        if isinstance(cell, datetime):
            return cell
        elif isinstance(cell, date):
            return datetime.combine(cell, datetime.min.time())
        elif isinstance(cell, str):
            return DateParser.parse(cell)
        return None
