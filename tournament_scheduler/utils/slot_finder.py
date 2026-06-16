"""Reusable per-arena time-slot finding.

Generalizes the slot-finding logic that originally lived in
``TimeSlotChecker._find_available_slots`` so it can be reused outside the
conflict-checker pipeline (e.g. by the season planner when looking for
hour-level free slots on a candidate arena/date that fit a tournament's
total computed duration).

The core entry point is :func:`find_available_slots`, parameterized by
*required_minutes* (rather than a fixed ``min_duration_hours``) so callers
can pass ``Tournament.duration_minutes(round_length)`` directly.
"""

from __future__ import annotations

from datetime import date, time
from typing import List, Tuple

from tournament_scheduler.utils.date_parser import DateParser


def parse_time(time_str: str) -> time:
    """Parse a ``HH:MM`` string into a :class:`datetime.time`."""
    hour, minute = map(int, time_str.split(':'))
    return time(hour, minute)


def format_time(t: time) -> str:
    """Format a :class:`datetime.time` as ``HH:MM``."""
    return f"{t.hour:02d}:{t.minute:02d}"


def minutes_to_time(minutes: int) -> str:
    """Convert minutes-since-midnight to a ``HH:MM`` string."""
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"


def find_available_slots(
    events: List,
    check_date: date,
    required_minutes: int,
    earliest_start: str = "10:00",
    latest_start: str = "15:30",
) -> List[Tuple[str, str]]:
    """Find available time slots on *check_date* that fit *required_minutes*.

    Args:
        events: Calendar events to check against (objects with ``date``,
            ``datetime`` and ``duration_hours`` attributes, e.g.
            :class:`tournament_scheduler.models.CalendarEvent`).
        check_date: Date to check.
        required_minutes: Minimum contiguous free duration required, in
            minutes.
        earliest_start: Earliest acceptable start time (``HH:MM``).
        latest_start: Latest acceptable start time (``HH:MM``).

    Returns:
        List of ``(start_time, end_time)`` tuples in ``HH:MM`` format,
        each representing a slot of exactly *required_minutes* starting at
        the earliest possible time within a free gap.
    """
    earliest = parse_time(earliest_start)
    latest = parse_time(latest_start)

    # Get all events on this date that have a parseable time-of-day.
    events_today = []
    for event in events:
        parsed = DateParser.parse(event.date)
        if parsed and parsed.date() == check_date:
            if hasattr(event.datetime, 'hour'):
                events_today.append(event)

    # Build list of busy time ranges (in minutes since midnight).
    busy_ranges = []
    for event in events_today:
        if event.duration_hours > 0:
            start_minutes = event.datetime.hour * 60 + event.datetime.minute
            end_minutes = start_minutes + int(event.duration_hours * 60)
            busy_ranges.append((start_minutes, end_minutes))

    busy_ranges.sort()

    available_slots: List[Tuple[str, str]] = []
    earliest_minutes = earliest.hour * 60 + earliest.minute
    latest_start_minutes = latest.hour * 60 + latest.minute
    min_duration_minutes = required_minutes

    if busy_ranges:
        # Check if we can fit a slot before the first event.
        first_busy_start = busy_ranges[0][0]
        if first_busy_start >= earliest_minutes + min_duration_minutes:
            slot_start = max(earliest_minutes, 0)
            slot_end = first_busy_start
            if slot_start <= latest_start_minutes and slot_end - slot_start >= min_duration_minutes:
                available_slots.append((
                    minutes_to_time(slot_start),
                    minutes_to_time(slot_start + min_duration_minutes)
                ))

        # Check gaps between consecutive events.
        for i in range(len(busy_ranges) - 1):
            gap_start = busy_ranges[i][1]
            gap_end = busy_ranges[i + 1][0]

            earliest_possible_start = max(gap_start, earliest_minutes)
            latest_possible_start = min(gap_end - min_duration_minutes, latest_start_minutes)

            if earliest_possible_start <= latest_possible_start:
                available_slots.append((
                    minutes_to_time(earliest_possible_start),
                    minutes_to_time(earliest_possible_start + min_duration_minutes)
                ))

        # Check after the last event.
        last_busy_end = busy_ranges[-1][1]
        earliest_possible_start = max(last_busy_end, earliest_minutes)

        if earliest_possible_start <= latest_start_minutes:
            available_slots.append((
                minutes_to_time(earliest_possible_start),
                minutes_to_time(earliest_possible_start + min_duration_minutes)
            ))
    else:
        # No events - entire window is available.
        available_slots.append((
            format_time(earliest),
            minutes_to_time(earliest_minutes + min_duration_minutes)
        ))

    return available_slots
