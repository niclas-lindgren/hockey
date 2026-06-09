"""
Cache manager — unified scraped data cache with timestamps and TTL.

Aggregates all scraped calendar data from the Stage 2 checkpoint into a
single JSON file at ``.pipeline/cache/scraped_data.json``, recording:
  - per-source event lists
  - scrape timestamps (ISO 8601)
  - source URL for reference links
  - TTL for cache staleness detection

The HTML calendar viewer reads from this cache.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


CACHE_DIR = "cache"
CACHE_FILE = "scraped_data.json"
DEFAULT_TTL_HOURS = 6


# ---------------------------------------------------------------------------
# Cache entry types
# ---------------------------------------------------------------------------


class ScrapedDataCache:
    """Unified cache of all scraped calendar data per source.

    Reads from the Stage 2 checkpoint and writes a merged cache file.
    """

    def __init__(self, work_dir: str = ".pipeline", ttl_hours: int = DEFAULT_TTL_HOURS) -> None:
        self.cache_path = Path(work_dir) / CACHE_DIR / CACHE_FILE
        self.ttl = timedelta(hours=ttl_hours)

    # ------------------------------------------------------------------
    # Read / write
    # ------------------------------------------------------------------

    def read(self) -> dict[str, Any]:
        """Read the current cache. Returns empty dict if missing or stale."""
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def write(self, data: dict[str, Any]) -> None:
        """Write cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        tmp.replace(self.cache_path)

    # ------------------------------------------------------------------
    # Build cache from Stage 2 checkpoint
    # ------------------------------------------------------------------

    def build_from_checkpoint(self, config: dict[str, Any], scraping_result: dict[str, Any]) -> dict[str, Any]:
        """Read the Stage 2 checkpoint and build/update the unified cache.

        Parameters
        ----------
        config:
            Stage 1 config (for source URLs and date range).
        scraping_result:
            Stage 2 checkpoint data with per-source results.

        Returns
        -------
        dict
            The updated cache data.
        """
        now = datetime.now().isoformat()
        cache = self.read()

        # Copy over global metadata
        cache["_meta"] = {
            "updated_at": now,
            "ttl_hours": self.ttl.total_seconds() / 3600,
            "start_date": config.get("start_date", ""),
            "end_date": config.get("end_date", ""),
        }

        sources_config = config.get("sources", [])
        source_map: dict[str, dict[str, Any]] = {
            s["name"]: s for s in sources_config
        }

        sources_data: dict[str, Any] = {}

        for source_result in scraping_result.get("sources", []):
            name: str = source_result.get("name", "ukjent")
            url: str = source_result.get("url", "")
            events: list[dict[str, Any]] = source_result.get("events", [])
            blocked: bool = source_result.get("blocked", False)

            entry = {
                "name": name,
                "url": url,
                "scrape_timestamp": now,
                "ttl_hours": self.ttl.total_seconds() / 3600,
                "event_count": len(events),
                "blocked": blocked,
                "events": events,
            }

            # Merge with any existing cached data (preserve previous scrape if current is empty)
            if not events:
                existing = cache.get("sources", {}).get(name, {})
                if existing.get("events"):
                    entry["events"] = existing["events"]
                    entry["event_count"] = existing["event_count"]
                    entry["scrape_timestamp"] = existing["scrape_timestamp"]
                    entry["note"] = "bruker tidligere cache (ny skraping ga 0 hendelser)"

            sources_data[name] = entry

        # Add sources that are in the cache but not in the current scrape
        # (e.g. clubs scraped by the extension's ScraperAgent)
        cached_sources = cache.get("sources", {})
        for cached_name, cached_entry in cached_sources.items():
            if cached_name not in sources_data:
                sources_data[cached_name] = cached_entry

        cache["sources"] = sources_data
        cache["source_count"] = len(sources_data)
        cache["total_events"] = sum(
            s.get("event_count", 0) for s in sources_data.values()
        )

        self.write(cache)
        return cache

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_stale(self, source_name: str) -> bool:
        """Check if a source's cache entry is older than TTL."""
        cache = self.read()
        entry = cache.get("sources", {}).get(source_name)
        if not entry:
            return True
        ts = entry.get("scrape_timestamp", "")
        if not ts:
            return True
        try:
            scraped_at = datetime.fromisoformat(ts)
            return datetime.now() - scraped_at > self.ttl
        except (ValueError, TypeError):
            return True

    def get_source_events(self, source_name: str) -> list[dict[str, Any]]:
        """Get cached events for a single source."""
        cache = self.read()
        entry = cache.get("sources", {}).get(source_name)
        if entry:
            return entry.get("events", [])
        return []

    def get_all_events(self) -> list[dict[str, Any]]:
        """Get all events from all sources with source metadata attached."""
        cache = self.read()
        all_events: list[dict[str, Any]] = []
        for name, entry in cache.get("sources", {}).items():
            for event in entry.get("events", []):
                all_events.append({
                    **event,
                    "_source": name,
                    "_source_url": entry.get("url", ""),
                })
        return all_events

    def clear(self) -> None:
        """Delete the cache file."""
        if self.cache_path.exists():
            self.cache_path.unlink()

    def force_refresh(self) -> bool:
        """Mark all cache entries as stale (forces re-scrape)."""
        cache = self.read()
        old_time = (datetime.now() - self.ttl - timedelta(hours=1)).isoformat()
        for entry in cache.get("sources", {}).values():
            entry["scrape_timestamp"] = old_time
        self.write(cache)
        return True
