"""Recovery event injector and Stage 2 checkpoint normalizer.

Usage::

    from tournament_scheduler.pipeline.recovery_injector import inject_recovered_events

    events = [{"title": "...", "start": "2025-01-04", ...}, ...]
    inject_recovered_events("Sandefjord", events, work_dir=".pipeline")

After calling this function the cache entry for the named source is updated so
that a subsequent Stage 2 re-run (or a direct Stage 3 invocation with
``--allow-missing-sources``) will pick up the recovered data without
re-scraping.

The companion :func:`normalize_stage2_checkpoint` helper rewrites the Stage 2
checkpoint from the unified cache after recovery injection so harnesses do not
need to patch checkpoint files by hand.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .cache_manager import ScrapedDataCache
from .scraper_event_helpers import _group_events_by_club, _scraped_date_range
from .state import PipelineState, StageName, StageStatus


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


def normalize_stage2_checkpoint(work_dir: str = ".pipeline") -> dict[str, Any]:
    """Rewrite the Stage 2 checkpoint using recovered cache data.

    The helper keeps the existing checkpoint structure intact, but refreshes the
    per-source event counts, unblocks sources whose recovered events are now in
    the cache, rebuilds ``events_by_club``, and recomputes the checkpoint date
    range from the event data.
    """
    state = PipelineState(work_dir)
    checkpoint_path = state.checkpoint_path(StageName.SCRAPING)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Stage 2 checkpoint not found: {checkpoint_path}")

    envelope = state.read_envelope(StageName.SCRAPING)
    data = envelope.get("data", envelope) or {}

    sources = list(data.get("sources", []))

    cache = ScrapedDataCache(work_dir=work_dir).read()
    cached_sources: dict[str, Any] = cache.get("sources", {})

    recovered_sources: list[str] = []
    normalized_sources: list[dict[str, Any]] = []

    for source in sources:
        merged = dict(source)
        name = merged.get("name", "")
        cache_entry = cached_sources.get(name, {})
        cached_events = cache_entry.get("events", []) or []

        if cached_events:
            original_event_count = int(merged.get("event_count", 0) or 0)
            merged["events"] = cached_events
            merged["event_count"] = int(cache_entry.get("event_count", len(cached_events)) or len(cached_events))
            merged["blocked"] = False
            merged.pop("scraper_error", None)
            merged["block_reason"] = None
            if original_event_count == 0 or source.get("blocked"):
                recovered_sources.append(name)

        else:
            merged["event_count"] = len(merged.get("events", []) or [])

        normalized_sources.append(merged)

    data["sources"] = normalized_sources
    data["events_by_club"] = _group_events_by_club(normalized_sources)

    blocked_sources = [
        source.get("name", "")
        for source in normalized_sources
        if source.get("blocked")
    ]
    data["blocked"] = blocked_sources

    start_date, end_date = _scraped_date_range(normalized_sources)
    if start_date is not None:
        data["start_date"] = start_date
    if end_date is not None:
        data["end_date"] = end_date

    data["checkpoint_path"] = str(state.checkpoint_path(StageName.SCRAPING))
    if blocked_sources:
        data["warning"] = (
            f"Stage 2 fortsatt blokkert: {', '.join(blocked_sources)}"
        )
        status = StageStatus.FAILED
    else:
        data.pop("warning", None)
        status = StageStatus.DONE

    state.write_stage(StageName.SCRAPING, data, status=status)

    return {
        "status": status.value,
        "work_dir": work_dir,
        "checkpoint_path": str(state.checkpoint_path(StageName.SCRAPING)),
        "source_count": len(normalized_sources),
        "event_count": sum(int(source.get("event_count", 0) or 0) for source in normalized_sources),
        "recovered_sources": recovered_sources,
        "blocked_sources": blocked_sources,
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
    }
