"""Time slot availability checker."""

from datetime import date, time, datetime, timedelta
from typing import List, Dict, Tuple
from tournament_scheduler.interfaces import ConflictChecker
from tournament_scheduler.models import ConflictContext, ConflictResult
from tournament_scheduler.utils.date_parser import DateParser


class TimeSlotChecker(ConflictChecker):
    """Checks if dates have available time slots for tournaments."""

    def __init__(
        self,
        calendar_events: List,
        min_duration_hours: float = 2.5,
        earliest_start: str = "11:00",
        latest_start: str = "15:30"
    ):
        """Initialize time slot checker.

        Args:
            calendar_events: All calendar events to check against
            min_duration_hours: Minimum hours needed for tournament
            earliest_start: Earliest acceptable start time (HH:MM)
            latest_start: Latest acceptable start time (HH:MM)
        """
        self.calendar_events = calendar_events
        self.min_duration_hours = min_duration_hours
        self.earliest_start = self._parse_time(earliest_start)
        self.latest_start = self._parse_time(latest_start)

    def check_conflicts(self, dates: List[date], context: ConflictContext) -> ConflictResult:
        """Check for time slot conflicts.

        Args:
            dates: Dates to check
            context: Context with calendar events

        Returns:
            ConflictResult with dates that don't have suitable time slots
        """
        excluded_dates = set()
        reasons = {}
        self.available_slots = {}  # Store available time slots for dates (make it instance variable)

        print(f"\nChecking time slot availability (need {self.min_duration_hours}h between {self._format_time(self.earliest_start)}-{self._format_time(self.latest_start)})...")

        conflicts_found = []
        for check_date in dates:
            slots = self._find_available_slots(check_date)
            if not slots:
                excluded_dates.add(check_date)
                reasons[check_date] = f"No {self.min_duration_hours}h time slot available"
                conflicts_found.append(check_date)
            else:
                # Store the available slots for this date
                self.available_slots[check_date] = slots

        if conflicts_found:
            print(f"\n⚠️  TIME SLOT CONFLICTS ({len(conflicts_found)} dates blocked):")
            for check_date in conflicts_found[:10]:
                booked_times = self._get_booked_times(check_date)
                if booked_times:
                    print(f"  - {check_date.strftime('%Y-%m-%d')}: Already booked {booked_times}")
                else:
                    print(f"  - {check_date.strftime('%Y-%m-%d')}: No suitable time slot")
            if len(conflicts_found) > 10:
                print(f"  ... and {len(conflicts_found) - 10} more dates")
        else:
            print(f"  ✓ All {len(dates)} dates have available time slots")

        return ConflictResult(
            excluded_dates=excluded_dates,
            reasons=reasons,
            checker_name=self.get_checker_name()
        )

    def get_suggested_slot(self, check_date: date) -> str:
        """Get suggested (earliest) time slot for a date.

        Args:
            check_date: Date to get suggested slot for

        Returns:
            Formatted time slot string (e.g., "11:00-13:30") or empty string
        """
        slots = self.available_slots.get(check_date, [])
        if slots:
            # Return the earliest slot (first one)
            return f"{slots[0][0]}-{slots[0][1]}"
        return ""

    def get_checker_name(self) -> str:
        """Get checker name."""
        return 'timeslot'

    def _find_available_slots(self, check_date: date) -> List[Tuple[str, str]]:
        """Find available time slots on a date.

        Args:
            check_date: Date to check

        Returns:
            List of (start_time, end_time) tuples in HH:MM format
        """
        # Get all events on this date
        events_today = []
        for event in self.calendar_events:
            parsed = DateParser.parse(event.date)
            if parsed and parsed.date() == check_date:
                # Only include events with times
                if hasattr(event.datetime, 'hour'):
                    events_today.append(event)

        # Build list of busy time ranges
        busy_ranges = []
        for event in events_today:
            if event.duration_hours > 0:
                start_minutes = event.datetime.hour * 60 + event.datetime.minute
                end_minutes = start_minutes + int(event.duration_hours * 60)
                busy_ranges.append((start_minutes, end_minutes))

        # Sort busy ranges
        busy_ranges.sort()

        # Find available slots
        available_slots = []
        earliest_minutes = self.earliest_start.hour * 60 + self.earliest_start.minute
        latest_start_minutes = self.latest_start.hour * 60 + self.latest_start.minute
        min_duration_minutes = int(self.min_duration_hours * 60)

        # Check if we can fit a slot before first event
        if busy_ranges:
            first_busy_start = busy_ranges[0][0]
            if first_busy_start >= earliest_minutes + min_duration_minutes:
                # Can fit before first event
                slot_start = max(earliest_minutes, 0)
                slot_end = first_busy_start
                if slot_start <= latest_start_minutes and slot_end - slot_start >= min_duration_minutes:
                    available_slots.append((
                        self._minutes_to_time(slot_start),
                        self._minutes_to_time(slot_start + min_duration_minutes)
                    ))

            # Check gaps between events
            for i in range(len(busy_ranges) - 1):
                gap_start = busy_ranges[i][1]
                gap_end = busy_ranges[i + 1][0]
                gap_duration = gap_end - gap_start

                if gap_start >= earliest_minutes and gap_start <= latest_start_minutes and gap_duration >= min_duration_minutes:
                    available_slots.append((
                        self._minutes_to_time(gap_start),
                        self._minutes_to_time(gap_start + min_duration_minutes)
                    ))

            # Check after last event
            last_busy_end = busy_ranges[-1][1]
            if last_busy_end >= earliest_minutes and last_busy_end <= latest_start_minutes:
                available_slots.append((
                    self._minutes_to_time(last_busy_end),
                    self._minutes_to_time(last_busy_end + min_duration_minutes)
                ))
        else:
            # No events - entire window is available
            available_slots.append((
                self._format_time(self.earliest_start),
                self._minutes_to_time(earliest_minutes + min_duration_minutes)
            ))

        return available_slots

    def _get_booked_times(self, check_date: date) -> str:
        """Get formatted string of booked times on a date.

        Args:
            check_date: Date to check

        Returns:
            Formatted string like "14:30-17:00, 19:00-21:00"
        """
        events_today = []
        for event in self.calendar_events:
            parsed = DateParser.parse(event.date)
            if parsed and parsed.date() == check_date:
                if hasattr(event.datetime, 'hour') and event.duration_hours > 0:
                    events_today.append(event)

        if not events_today:
            return ""

        # Format times
        time_ranges = []
        for event in sorted(events_today, key=lambda e: e.datetime):
            start_str = event.datetime.strftime('%H:%M')
            end_time = event.datetime + timedelta(hours=event.duration_hours)
            end_str = end_time.strftime('%H:%M')
            time_ranges.append(f"{start_str}-{end_str}")

        return ", ".join(time_ranges[:3])

    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object.

        Args:
            time_str: Time in HH:MM format

        Returns:
            time object
        """
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)

    def _format_time(self, t: time) -> str:
        """Format time object to string.

        Args:
            t: time object

        Returns:
            String in HH:MM format
        """
        return f"{t.hour:02d}:{t.minute:02d}"

    def _minutes_to_time(self, minutes: int) -> str:
        """Convert minutes since midnight to HH:MM string.

        Args:
            minutes: Minutes since midnight

        Returns:
            String in HH:MM format
        """
        hour = minutes // 60
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"
