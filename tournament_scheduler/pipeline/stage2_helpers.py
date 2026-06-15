"""Stage 2 scraping helpers — backward-compat re-export facade.

All helpers have been split into focused modules:
  - :mod:`scraper_cache`          — ``_cached_source_result``
  - :mod:`scraper_recovery`       — ``_recovery_hint_for_source``, ``_blocked_sources_warning``
  - :mod:`scraper_credentialed`   — ``_try_credentialed_scrape``, ``_run_credentialed_bookup_or_outlook``, ``_credentialed_scrape_months``
  - :mod:`scraper_ical`           — ``_run_ical_scraper``
  - :mod:`scraper_event_helpers`  — ``_events_to_dicts``, ``_group_events_by_club``
  - :mod:`scraper_outlook`        — ``_run_outlook_scraper``, ``_parse_outlook_calendar``, ``_parse_date_param_calendar``
  - :mod:`scraper_bookup`         — ``_run_bookup_scraper``, ``_bookup_navigate_to_date``, ``_parse_bookup_timegrid``
  - :mod:`scraper_styledcalendar` — ``_run_styledcalendar_scraper``
"""

from __future__ import annotations

from .scraper_bookup import (
    _bookup_navigate_to_date,
    _parse_bookup_timegrid,
    _run_bookup_scraper,
)
from .scraper_cache import _cached_source_result
from .scraper_credentialed import (
    _credentialed_scrape_months,
    _run_credentialed_bookup_or_outlook,
    _try_credentialed_scrape,
)
from .scraper_event_helpers import _events_to_dicts, _group_events_by_club
from .scraper_ical import _run_ical_scraper
from .scraper_outlook import (
    _parse_date_param_calendar,
    _parse_outlook_calendar,
    _run_outlook_scraper,
)
from .scraper_recovery import _blocked_sources_warning, _recovery_hint_for_source
from .scraper_styledcalendar import _run_styledcalendar_scraper

__all__ = [
    "_blocked_sources_warning",
    "_bookup_navigate_to_date",
    "_cached_source_result",
    "_credentialed_scrape_months",
    "_events_to_dicts",
    "_group_events_by_club",
    "_parse_bookup_timegrid",
    "_parse_date_param_calendar",
    "_parse_outlook_calendar",
    "_recovery_hint_for_source",
    "_run_bookup_scraper",
    "_run_credentialed_bookup_or_outlook",
    "_run_ical_scraper",
    "_run_outlook_scraper",
    "_run_styledcalendar_scraper",
    "_try_credentialed_scrape",
]
