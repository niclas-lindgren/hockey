"""Tests for the central club/calendar-source registry (club_registry.py)."""

import pytest

from tournament_scheduler.club_registry import (
    CLUB_REGISTRY,
    CalendarSourceKind,
    build_data_source,
    get_club,
    known_clubs,
    missing_clubs,
)
from tournament_scheduler.data_sources.ice_hall_calendar import IceHallCalendar

ALL_NINE_CLUBS = [
    "Ringerike", "Tønsberg", "Frisk Asker", "Sandefjord Penguins",
    "Jar", "Holmen", "Skien", "Jutul", "Kongsberg",
]

CLUBS_WITH_KNOWN_SOURCES = ["Kongsberg", "Skien", "Jutul", "Jar", "Ringerike"]
CLUBS_PENDING_URLS = ["Holmen", "Frisk Asker", "Tønsberg", "Sandefjord Penguins"]


class TestClubRegistry:
    """Test suite for the RVV club calendar-source registry."""

    def test_registry_covers_all_nine_rvv_clubs(self):
        assert len(CLUB_REGISTRY) == 9
        for club in ALL_NINE_CLUBS:
            assert club in CLUB_REGISTRY

    def test_get_club_returns_entry_for_each_known_name(self):
        for club in ALL_NINE_CLUBS:
            entry = get_club(club)
            assert entry.club == club
            assert entry.arena  # every entry records a home arena

    def test_get_club_raises_helpful_error_for_unknown_club(self):
        with pytest.raises(KeyError):
            get_club("Not A Real Club")

    def test_clubs_with_known_sources_build_a_usable_data_source(self):
        for club in CLUBS_WITH_KNOWN_SOURCES:
            entry = get_club(club)
            assert entry.is_known, f"{club} should have a known source"
            assert entry.kind in (CalendarSourceKind.OUTLOOK, CalendarSourceKind.ICAL)

            source = build_data_source(entry)
            assert source is not None, f"{club} should produce a constructible CalendarDataSource"
            assert isinstance(source, IceHallCalendar)

    def test_clubs_pending_urls_are_marked_skip_with_placeholder(self):
        for club in CLUBS_PENDING_URLS:
            entry = get_club(club)
            assert entry.skip is True
            assert entry.is_known is False
            assert entry.note  # documents that a URL is still needed
            assert build_data_source(entry) is None

    def test_known_clubs_returns_only_constructible_entries(self):
        names = {entry.club for entry in known_clubs()}
        assert names == set(CLUBS_WITH_KNOWN_SOURCES)

    def test_missing_clubs_returns_only_skip_entries(self):
        names = {entry.club for entry in missing_clubs()}
        assert names == set(CLUBS_PENDING_URLS)

    def test_known_and_missing_partition_the_registry(self):
        assert len(known_clubs()) + len(missing_clubs()) == len(CLUB_REGISTRY)
