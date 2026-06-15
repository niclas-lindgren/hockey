"""Cache helpers for Stage 2 scraping.

Provides :func:`_cached_source_result` which builds a source-result dict from
a fresh unified-cache entry so the (slow) scrape can be skipped.
"""

from __future__ import annotations

from typing import Any

from .scraper_constants import SOURCE_OUTLOOK


def _cached_source_result(source_cfg: dict[str, Any], cache_entry: dict[str, Any]) -> dict[str, Any]:
    """Build a source result dict from a fresh unified-cache entry.

    Used when the caller decides a source's cached events are still within
    TTL and the date range matches, so the (slow) scrape can be skipped.
    """
    name = source_cfg.get("name", "ukjent kilde")
    events = cache_entry.get("events", [])
    return {
        "name": name,
        "url": source_cfg.get("url", cache_entry.get("url", "")),
        "type": source_cfg.get("type", SOURCE_OUTLOOK).lower(),
        "events": events,
        "event_count": cache_entry.get("event_count", len(events)),
        "blocked": False,
        "block_reason": "",
        "llm_fallback": False,
        "from_cache": True,
    }
