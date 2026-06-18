"""Recovery event injector — patches the unified cache with hand-fetched events.

Usage::

    from tournament_scheduler.pipeline.recovery_injector import inject_recovered_events

    events = [{"title": "...", "start": "2025-01-04", ...}, ...]
    inject_recovered_events("Sandefjord", events, work_dir=".pipeline")

After calling this function the cache entry for the named source is updated so
that a subsequent Stage 2 re-run (or a direct Stage 3 invocation with
``--allow-missing-sources``) will pick up the recovered data without
re-scraping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .cache_manager import ScrapedDataCache


def inject_recovered_events(
    source_name: str,
    events: list[dict[str, Any]],
    work_dir: str = ".pipeline",
) -> None:
    """Patch the ScrapedDataCache entry for *source_name* with *events*.

    Parameters
    ----------
    source_name:
        The canonical source name as it appears in the Stage 2 checkpoint
        ``data.sources[*].name`` (e.g. ``"Sandefjord"``).
    events:
        List of event dicts to inject.  The format matches the event dicts
        already stored in the cache (keys like ``title``, ``start``, ``end``
        and so on — whatever the existing scrapers produce).
    work_dir:
        Pipeline work directory.  Defaults to ``.pipeline``.
    """
    cache = ScrapedDataCache(work_dir=work_dir)
    data = cache.read()

    now_iso = datetime.now(timezone.utc).isoformat()

    sources: dict[str, Any] = data.get("sources", {})
    existing = sources.get(source_name, {})

    sources[source_name] = {
        **existing,
        "name": source_name,
        "scrape_timestamp": now_iso,
        "event_count": len(events),
        "blocked": False,
        "events": events,
    }
    data["sources"] = sources

    # Bump the top-level meta timestamp so is_stale() won't immediately
    # invalidate the freshly-injected entry.
    meta: dict[str, Any] = data.get("_meta", {})
    meta["updated_at"] = now_iso
    data["_meta"] = meta

    cache.write(data)
