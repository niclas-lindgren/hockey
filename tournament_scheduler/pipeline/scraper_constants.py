"""Shared source-type constants for Stage 2 scraping."""

from __future__ import annotations

SOURCE_OUTLOOK = "outlook"
SOURCE_HTML = "html"
SOURCE_ICAL = "ical"
SOURCE_GOOGLE = "google"

_BROWSER_SOURCE_TYPES = {SOURCE_OUTLOOK, SOURCE_HTML}
_ICAL_SOURCE_TYPES = {SOURCE_ICAL, SOURCE_GOOGLE}
