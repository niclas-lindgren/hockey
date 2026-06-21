"""Stage 2 — deterministic calendar scraping.

For each configured calendar source:
  1. ``outlook`` / ``html`` sources use Playwright to load the page and extract
     events from the Outlook Web Calendar iframe (if present).
  2. ``ical`` / ``google`` sources use the deterministic ICAL scraper.
  3. If a source returns zero events, block with a Norwegian-language error
     message rather than proceeding silently.

Source config format (inside the validated Stage 1 config)::

    "sources": [
        {
            "name": "Kongsberg ishall",
            "type": "outlook",
            "url": "https://kongsberghallen.no/webkalender/ishall/"
        },
        ...
    ]

If no ``sources`` key is present in the Stage 1 config, the stage writes an
empty ``sources`` list to the checkpoint (useful for tests / partial runs).
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from ..club_registry import club_for_source_name, CLUB_REGISTRY
from ..models import CalendarEvent
from .cache_manager import ScrapedDataCache
from ..utils.calendar_cache import CalendarCache

from .scraper_strategies import get_strategy, requires_credentials, needs_llm_agent, get_deterministic_scraper_type
from .state import PipelineState, StageName, StageStatus
from .scraper_constants import (
    SOURCE_OUTLOOK, SOURCE_HTML, SOURCE_ICAL, SOURCE_GOOGLE,
    _BROWSER_SOURCE_TYPES, _ICAL_SOURCE_TYPES,
)
from .scraper_bookup import _run_bookup_scraper, _bookup_navigate_to_date, _parse_bookup_timegrid
from .scraper_credentialed import _credentialed_scrape_months, _run_credentialed_bookup_or_outlook, _try_credentialed_scrape
from .scraper_event_helpers import _events_to_dicts, _group_events_by_club
from .scraper_ical import _run_ical_scraper
from .scraper_outlook import _run_outlook_scraper, _parse_date_param_calendar, _parse_outlook_calendar
from .scraper_recovery import _blocked_sources_warning, _recovery_hint_for_source
from .scraper_styledcalendar import _run_styledcalendar_scraper

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_source_result(
    name: str,
    url: str,
    source_type: str,
    events: list,
    event_count: int,
    blocked: bool,
    block_reason: str,
    llm_fallback: bool,
    *,
    skipped: bool = False,
    skip_reason: str | None = None,
    scraper_error: str | None = None,
    from_cache: bool = False,
) -> dict[str, Any]:
    """Build the canonical source-result dict used throughout stage 2.

    All callers (skipped sources, executor exception handler, and
    :func:`_scrape_source`) must go through this helper so the dict shape
    stays consistent.
    """
    result: dict[str, Any] = {
        "name": name,
        "url": url,
        "type": source_type,
        "events": events,
        "event_count": event_count,
        "blocked": blocked,
        "block_reason": block_reason,
        "llm_fallback": llm_fallback,
    }
    if skipped:
        result["skipped"] = True
    if skip_reason is not None:
        result["skip_reason"] = skip_reason
    if scraper_error is not None:
        result["scraper_error"] = scraper_error
    if from_cache:
        result["from_cache"] = True
    return result


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Stage2Error(RuntimeError):
    """Raised when one or more sources block the pipeline."""

    def __init__(self, blocked: list[dict[str, Any]]) -> None:
        self.blocked = blocked
        names = ", ".join(b["name"] for b in blocked)
        super().__init__(f"Stage 2 blokkert: {names}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run(
    config: dict[str, Any],
    state: PipelineState,
    start_date: datetime,
    end_date: datetime,
    *,
    strict: bool = True,
    allow_missing_sources: bool = False,
    max_workers: int = 4,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Run Stage 2 scraping for all sources listed in *config*.

    Sources are scraped in parallel via :class:`~concurrent.futures.ThreadPoolExecutor`
    because each source creates its own Playwright browser context (or uses HTTP-only
    iCal feeds) — there is no shared browser state.

    Before scraping, each source is checked against the unified
    :class:`~tournament_scheduler.pipeline.cache_manager.ScrapedDataCache`. If a
    source has a fresh (non-stale), non-blocked, non-empty cache entry for the
    same date range, the cached events are reused instead of re-scraping. After
    scraping, fresh results are written back to the cache so subsequent runs can
    benefit.

    Parameters
    ----------
    config:
        Validated Stage 1 config dict (from :func:`stage1_config.run`).
    state:
        :class:`PipelineState` managing the work directory.
    start_date / end_date:
        Date range for scraping.
    strict:
        If ``True``, raise :class:`Stage2Error` when any source is blocked.
    allow_missing_sources:
        If ``True``, keep partial scrape results as a successful checkpoint and
        continue downstream even when some sources are blocked.
    max_workers:
        Number of worker threads for the executor. Default 4.
    force_refresh:
        If ``True``, ignore the cache and re-scrape every source.

    Returns
    -------
    dict
        Checkpoint data with per-source results.
    """
    state._set_status(StageName.SCRAPING, StageStatus.RUNNING)

    sources: list[dict[str, Any]] = config.get("sources", [])

    if not sources:
        reason = (
            "Ingen kalenderkilder er konfigurert. Legg til kilder i input.xlsx-arket 'Kilder' "
            "for a hente kalenderdata (f.eks. Kongsberg ishall, Skien o.l.). Uten kalenderdata "
            "kan ikke pipelinen planlegge rundt faktiske bookinger og vil foresla fantasidatoer."
        )
        if strict:
            state.write_stage(StageName.SCRAPING, {}, status=StageStatus.FAILED)
            raise Stage2Error([{"name": "(ingen kilder)", "reason": reason}])
        result: dict[str, Any] = {
            "sources": [],
            "blocked": [],
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "warning": reason,
        }
        state.write_stage(StageName.SCRAPING, result, status=StageStatus.DONE)
        return result

    # --- Split sources into cache hits and sources that need (re-)scraping ---
    cache = ScrapedDataCache(work_dir=state.work_dir)
    calendar_cache = CalendarCache(work_dir=state.work_dir)
    cache_data = cache.read()
    cache_meta = cache_data.get("_meta", {})
    cache_sources = cache_data.get("sources", {})
    date_range_matches = (
        cache_meta.get("start_date") == config.get("start_date")
        and cache_meta.get("end_date") == config.get("end_date")
    )

    sources_to_scrape: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    cached_names: list[str] = []

    for source_cfg in sources:
        name = source_cfg.get("name", "ukjent kilde")
        url = source_cfg.get("url", "").strip()
        if not url:
            source_results.append(_make_source_result(
                name=name,
                url="",
                source_type=source_cfg.get("type", SOURCE_OUTLOOK).lower(),
                events=[],
                event_count=0,
                blocked=False,
                block_reason="",
                llm_fallback=False,
                skipped=True,
                skip_reason="Tom URL — kilden er deaktivert i input.xlsx.",
            ))
            continue
        entry = cache_sources.get(name)
        if (
            not force_refresh
            and date_range_matches
            and entry
            and entry.get("events")
            and not entry.get("blocked")
            and not cache.is_stale(name)
        ):
            _cached_events = entry.get("events", [])
            source_results.append(_make_source_result(
                name=name,
                url=source_cfg.get("url", entry.get("url", "")),
                source_type=source_cfg.get("type", SOURCE_OUTLOOK).lower(),
                events=_cached_events,
                event_count=entry.get("event_count", len(_cached_events)),
                blocked=False,
                block_reason="",
                llm_fallback=False,
                from_cache=True,
            ))
            cached_names.append(name)
        else:
            sources_to_scrape.append(source_cfg)

    blocked: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(
                _scrape_source,
                source_cfg,
                start_date=start_date,
                end_date=end_date,
                calendar_cache=calendar_cache,
            ): source_cfg
            for source_cfg in sources_to_scrape
        }
        for future in as_completed(future_to_source):
            source_cfg = future_to_source[future]
            try:
                source_result = future.result()
            except Exception as exc:
                source_result = _make_source_result(
                    name=source_cfg.get("name", "ukjent kilde"),
                    url=source_cfg.get("url", ""),
                    source_type=source_cfg.get("type", SOURCE_OUTLOOK),
                    events=[],
                    event_count=0,
                    blocked=True,
                    block_reason=f"Scraper krasjet: {exc}",
                    llm_fallback=False,
                    scraper_error=str(exc),
                )
            source_results.append(source_result)
            if source_result.get("blocked"):
                blocked.append({"name": source_cfg.get("name", "?"), **source_result})

    checkpoint: dict[str, Any] = {
        "sources": source_results,
        "events_by_club": _group_events_by_club(source_results),
        "blocked": [b["name"] for b in blocked],
        "cached": cached_names,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }

    status = StageStatus.DONE if (not blocked or allow_missing_sources) else StageStatus.FAILED
    checkpoint["checkpoint_path"] = str(state.checkpoint_path(StageName.SCRAPING))
    if blocked:
        checkpoint["warning"] = _blocked_sources_warning(
            blocked,
            state,
            allow_missing_sources=allow_missing_sources,
        )

    state.write_stage(StageName.SCRAPING, checkpoint, status=status)

    # Persist freshly-scraped results to the unified cache for future runs
    cache.build_from_checkpoint(config, checkpoint)

    if blocked and strict and not allow_missing_sources:
        raise Stage2Error(blocked)

    return checkpoint


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scrape_source(
    source_cfg: dict[str, Any],
    *,
    start_date: datetime,
    end_date: datetime,
    calendar_cache: CalendarCache | None = None,
) -> dict[str, Any]:
    """Scrape a single source deterministically.

    Dispatch is driven by the :class:`~scraper_strategies.CalendarEngine`
    declared in ``STRATEGIES`` via :func:`~scraper_strategies.get_deterministic_scraper_type`:

    * ``"styledcalendar"`` (e.g. Bærum/Jutul) — calls ``_run_styledcalendar_scraper``
    * ``"bookup"``         (e.g. Tønsberg, Sandefjord) — calls ``_run_bookup_scraper``
    * sources not in ``STRATEGIES`` fall back to ``source_type``-based routing:

      * ``outlook`` / ``html`` — Playwright Outlook-iframe scraper
      * ``ical`` / ``google``  — HTTP iCal scraper

    If the deterministic scrape returns zero events and the source strategy
    requires credentials, the function automatically retries with environment-
    variable credentials injected via Playwright login.

    If that also fails, the result is marked with ``llm_fallback=True`` so the
    caller can attempt LLM-driven scraping via browser_worker.
    """
    name = source_cfg.get("name", "ukjent kilde")
    url = source_cfg.get("url", "")
    source_type = source_cfg.get("type", SOURCE_OUTLOOK).lower()

    result: dict[str, Any] = _make_source_result(
        name=name,
        url=url,
        source_type=source_type,
        events=[],
        event_count=0,
        blocked=False,
        block_reason="",
        llm_fallback=False,
    )

    # --- Run the deterministic scraper ---
    events: list[CalendarEvent] = []
    scraper_error: str = ""
    deterministic_raised: bool = False

    try:
        # Dispatch is driven by the CalendarEngine declared in scraper_strategies.
        # get_deterministic_scraper_type() returns a string token for sources
        # registered in STRATEGIES, or None for sources that only appear in
        # the generic _BROWSER_SOURCE_TYPES / _ICAL_SOURCE_TYPES fallbacks.
        _strategy = get_strategy(name)
        _scraper_type = get_deterministic_scraper_type(_strategy) if _strategy is not None else None

        if _scraper_type == "styledcalendar":
            events, _ = _run_styledcalendar_scraper(name, start_date, end_date)
        elif _scraper_type == "bookup":
            events, _ = _run_bookup_scraper(url, name, start_date, end_date)
        elif source_type in _BROWSER_SOURCE_TYPES:
            events, _ = _run_outlook_scraper(url, name, start_date, end_date, calendar_cache)
        elif source_type in _ICAL_SOURCE_TYPES:
            # Look up any per-source location filter registered in CLUB_REGISTRY
            _club_name = club_for_source_name(name)
            _location_filter = (
                CLUB_REGISTRY[_club_name].location_filter
                if _club_name and _club_name in CLUB_REGISTRY
                else None
            )
            events = _run_ical_scraper(url, name, start_date, end_date, source_type, calendar_cache, location_filter=_location_filter)
        else:
            scraper_error = f"Ukjent kildetype '{source_type}'."
            deterministic_raised = True
    except Exception as exc:  # noqa: BLE001
        scraper_error = str(exc)
        deterministic_raised = True

    if scraper_error:
        result["scraper_error"] = scraper_error

    # --- If deterministic succeeded but returned 0 events, try credentialed fallback ---
    # Do NOT fall through to credentialed scrape when the deterministic scraper raised an
    # exception (e.g. network error, Playwright crash) — an exception means we don't know
    # whether the source has events; only a clean zero-event return warrants the fallback.
    if not events and not deterministic_raised:
        events, cred_error = _try_credentialed_scrape(
            name, url, start_date, end_date, calendar_cache
        )
        if cred_error:
            scraper_error = scraper_error or cred_error

    # --- If still no events, assess LLM fallback viability ---
    if not events:
        strategy = get_strategy(name)
        block_reason = (
            f"Kilde '{name}' returnerte 0 hendelser -- "
            "skraper odelagt eller hallen er stengt?"
        )
        recovery_hint = _recovery_hint_for_source(name)
        result["blocked"] = True
        result["block_reason"] = f"{block_reason} {recovery_hint}".strip()
        result["recovery_hint"] = recovery_hint

        # Mark for LLM fallback if the source has a strategy that needs it
        if strategy and needs_llm_agent(strategy):
            result["llm_fallback"] = True
            result["llm_strategy"] = {
                "engine": strategy.engine.value,
                "url": strategy.url,
                "initial_navigation": strategy.initial_navigation,
                "credential_env_vars": strategy.credential_env_vars,
                "month_selector": strategy.month_selector,
                "event_pattern": strategy.event_pattern,
            }

    result["events"] = _events_to_dicts(events)
    result["event_count"] = len(events)
    return result



# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Stage 2: deterministic calendar scraping"
    )
    parser.add_argument(
        "--work-dir", default=".pipeline", help="Pipeline work directory"
    )
    parser.add_argument(
        "--non-strict", action="store_true",
        help="Don't raise on blocked sources — write checkpoint anyway"
    )
    parser.add_argument(
        "--allow-missing-sources", action="store_true",
        help="Mark blocked sources as an operator-approved skip and keep partial results"
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Ignore the unified scrape cache and re-scrape every source"
    )
    cli_args = parser.parse_args()

    from .state import PipelineState, StageName  # noqa: E402
    from .stage1_config import load_effective_config  # noqa: E402
    from datetime import datetime as _dt  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    _cfg = load_effective_config(_state)
    if not _cfg:
        print("Stage 1 checkpoint not found -- run Stage 1 first.", file=sys.stderr)
        sys.exit(1)

    _start = _dt.strptime(_cfg["start_date"], "%Y-%m-%d")
    _end = _dt.strptime(_cfg["end_date"], "%Y-%m-%d")

    try:
        _result = run(
            _cfg, _state, _start, _end,
            strict=not cli_args.non_strict,
            allow_missing_sources=cli_args.allow_missing_sources,
            force_refresh=cli_args.force_refresh,
        )
        n_sources = len(_result.get("sources", []))
        blocked = _result.get("blocked", [])
        cached = _result.get("cached", [])
        print(f"Stage 2 OK -- {n_sources} kilder skannet, {len(cached)} fra cache, {len(blocked)} blokkert")
        if _result.get("warning"):
            print(_result["warning"])
        sys.exit(0)
    except Stage2Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
