"""Stage 2 — scraping with LLM quality gate and raw-HTML fallback.

For each configured calendar source:
  1. Run the appropriate scraper (Playwright/Outlook, iCal, Google Calendar).
  2. For Playwright/Outlook sources, pass the scraped events to the LLM for a
     confidence check.  If confidence is low *or* zero events were returned,
     attempt LLM-based extraction from the raw HTML.
  3. iCal and Google Calendar sources skip the LLM path entirely.
  4. If both the scraper and LLM fallback return zero events, block with a
     clear Norwegian-language error message rather than proceeding silently.

Results are written per-source to the Stage 2 checkpoint.

Source config format (inside the validated Stage 1 config or provided directly)::

    "sources": [
        {
            "name": "Kongsberg ishall",
            "type": "outlook",   // "outlook" | "ical" | "google"
            "url": "https://kongsberghallen.no/webkalender/ishall/"
        },
        ...
    ]

If no ``sources`` key is present in the Stage 1 config, the stage writes an
empty ``sources`` list to the checkpoint (useful for tests / partial runs).
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime
from typing import Any

from ..models import CalendarEvent
from .state import PipelineState, StageName, StageStatus

# LLM client — optional dependency; if unavailable the quality gate is skipped
try:
    from ..llm.lm_studio_client import (
        LMStudioClient,
        LMStudioUnavailableError,
        extract_confidence,
    )

    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

# ---------------------------------------------------------------------------
# Source type constants
# ---------------------------------------------------------------------------

SOURCE_OUTLOOK = "outlook"
SOURCE_ICAL = "ical"
SOURCE_GOOGLE = "google"

# Sources that skip the LLM quality gate
_ICAL_SOURCE_TYPES = {SOURCE_ICAL, SOURCE_GOOGLE}

# Confidence threshold below which the LLM fallback is attempted
_CONFIDENCE_THRESHOLD = 0.6

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
    llm_client: "LMStudioClient | None" = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Run Stage 2 scraping for all sources listed in *config*.

    Parameters
    ----------
    config:
        Validated Stage 1 config dict (from :func:`stage1_config.run`).
    state:
        :class:`PipelineState` managing the work directory.
    start_date / end_date:
        Date range for scraping.
    llm_client:
        Optional :class:`LMStudioClient` to inject (useful for testing).
        If ``None``, a default client is used when available.
    strict:
        If ``True``, raise :class:`Stage2Error` when any source is blocked.

    Returns
    -------
    dict
        Checkpoint data with per-source results.
    """
    state.write_stage(StageName.SCRAPING, {}, status=StageStatus.RUNNING)

    sources: list[dict[str, Any]] = config.get("sources", [])

    if not sources:
        # No sources configured — write empty checkpoint and continue
        result: dict[str, Any] = {"sources": [], "blocked": []}
        state.write_stage(StageName.SCRAPING, result, status=StageStatus.DONE)
        state.mark_done(StageName.SCRAPING)
        return result

    client = llm_client or (_make_default_client() if _LLM_AVAILABLE else None)

    source_results: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for source_cfg in sources:
        source_result = _scrape_source(
            source_cfg,
            start_date=start_date,
            end_date=end_date,
            llm_client=client,
        )
        source_results.append(source_result)
        if source_result.get("blocked"):
            blocked.append({"name": source_cfg.get("name", "?"), **source_result})

    checkpoint: dict[str, Any] = {
        "sources": source_results,
        "blocked": [b["name"] for b in blocked],
    }

    if blocked and strict:
        state.write_stage(StageName.SCRAPING, checkpoint, status=StageStatus.FAILED)
        state.mark_failed(
            StageName.SCRAPING,
            error="; ".join(b["name"] for b in blocked),
        )
        raise Stage2Error(blocked)

    status = StageStatus.DONE if not blocked else StageStatus.FAILED
    state.write_stage(StageName.SCRAPING, checkpoint, status=status)
    if not blocked:
        state.mark_done(StageName.SCRAPING)
    return checkpoint


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scrape_source(
    source_cfg: dict[str, Any],
    *,
    start_date: datetime,
    end_date: datetime,
    llm_client: "LMStudioClient | None",
) -> dict[str, Any]:
    """Scrape a single source and return a per-source result dict."""
    name = source_cfg.get("name", "ukjent kilde")
    url = source_cfg.get("url", "")
    source_type = source_cfg.get("type", SOURCE_OUTLOOK).lower()

    result: dict[str, Any] = {
        "name": name,
        "url": url,
        "type": source_type,
        "events": [],
        "event_count": 0,
        "llm_skipped": source_type in _ICAL_SOURCE_TYPES,
        "llm_confidence": None,
        "llm_fallback_used": False,
        "blocked": False,
        "block_reason": "",
    }

    # --- Step 1: Run the scraper ---
    events: list[CalendarEvent] = []
    raw_html: str = ""
    scraper_error: str = ""

    try:
        if source_type == SOURCE_OUTLOOK:
            events, raw_html = _run_outlook_scraper(url, name, start_date, end_date)
        elif source_type in _ICAL_SOURCE_TYPES:
            events = _run_ical_scraper(url, name, start_date, end_date, source_type)
        else:
            scraper_error = f"Ukjent kildetype '{source_type}'."
    except Exception as exc:  # noqa: BLE001
        scraper_error = str(exc)

    if scraper_error:
        result["scraper_error"] = scraper_error

    # --- Step 2: LLM quality gate (Playwright sources only) ---
    if source_type not in _ICAL_SOURCE_TYPES and llm_client is not None:
        try:
            llm_result = _llm_quality_gate(
                events=events,
                raw_html=raw_html,
                source_name=name,
                start_date=start_date,
                end_date=end_date,
                client=llm_client,
            )
            result["llm_confidence"] = llm_result["confidence"]
            if llm_result.get("fallback_used"):
                result["llm_fallback_used"] = True
                events = llm_result.get("events", events)
        except LMStudioUnavailableError:
            # LM Studio offline — skip the gate but log it
            result["llm_skipped"] = True
            result["llm_skip_reason"] = "LM Studio utilgjengelig"

    # --- Step 3: Block check ---
    if not events:
        block_reason = (
            f"Kilde '{name}' returnerte 0 hendelser — "
            "skraper ødelagt eller hallen er stengt?"
        )
        result["blocked"] = True
        result["block_reason"] = block_reason

    result["events"] = _events_to_dicts(events)
    result["event_count"] = len(events)
    return result


def _run_outlook_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[list[CalendarEvent], str]:
    """Run the Playwright/Outlook scraper and return (events, raw_html)."""
    from ..data_sources.calendar_scraper import CalendarScraper

    scraper = _OutlookScraperWithHtml()
    events = scraper.scrape_calendar(url, name, start_date, end_date)
    return events, scraper.last_raw_html


def _run_ical_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
    source_type: str,
) -> list[CalendarEvent]:
    """Run the appropriate iCal scraper."""
    if source_type == SOURCE_GOOGLE:
        from ..data_sources.google_calendar_scraper import GoogleCalendarScraper

        scraper = GoogleCalendarScraper()
        return scraper.scrape_calendar(url, name, start_date, end_date)
    else:
        from ..data_sources.ical_scraper import ICalScraper

        scraper = ICalScraper()
        return scraper.scrape_calendar(url, name, start_date, end_date)


def _llm_quality_gate(
    *,
    events: list[CalendarEvent],
    raw_html: str,
    source_name: str,
    start_date: datetime,
    end_date: datetime,
    client: "LMStudioClient",
) -> dict[str, Any]:
    """Ask the LLM to validate scraped events; attempt fallback if needed.

    Returns a dict with keys:
    - ``confidence`` (float)
    - ``fallback_used`` (bool)
    - ``events`` (list[CalendarEvent], only set when fallback extracts events)
    """
    system = (
        "Du er en kvalitetskontroll-assistent for ishockeyhall-bookinger. "
        "Evaluer om de gitte hendelsene ser ut som gyldige ishall-bookinger "
        "i den oppgitte datoperioden. "
        "Svar KUN med et JSON-objekt på formen: "
        '{"confidence": 0.0-1.0, "valid": true/false, "reasoning": "..."}'
    )

    date_range_str = (
        f"{start_date.strftime('%d.%m.%Y')} til {end_date.strftime('%d.%m.%Y')}"
    )

    if events:
        events_summary = "\n".join(
            f"- {e.date} {e.name} ({e.duration_hours:.1f}t)" for e in events[:20]
        )
        user_msg = (
            f"Kilde: {source_name}\n"
            f"Periode: {date_range_str}\n"
            f"Antall hendelser: {len(events)}\n\n"
            f"Hendelser (første 20):\n{events_summary}"
        )
    else:
        user_msg = (
            f"Kilde: {source_name}\n"
            f"Periode: {date_range_str}\n"
            "Antall hendelser: 0 — ingen hendelser ble funnet av skraperen."
        )

    response = client.complete(system=system, user=user_msg, temperature=0.1)
    confidence_result = extract_confidence(response.text)

    if confidence_result.confidence >= _CONFIDENCE_THRESHOLD and events:
        return {"confidence": confidence_result.confidence, "fallback_used": False}

    # Low confidence or zero events — attempt LLM extraction from raw HTML
    if raw_html:
        fallback_events = _llm_html_fallback(
            raw_html=raw_html,
            source_name=source_name,
            start_date=start_date,
            end_date=end_date,
            client=client,
        )
        if fallback_events:
            return {
                "confidence": confidence_result.confidence,
                "fallback_used": True,
                "events": fallback_events,
            }

    return {"confidence": confidence_result.confidence, "fallback_used": False}


def _llm_html_fallback(
    *,
    raw_html: str,
    source_name: str,
    start_date: datetime,
    end_date: datetime,
    client: "LMStudioClient",
) -> list[CalendarEvent]:
    """Ask the LLM to extract events directly from the raw HTML.

    Returns a list of :class:`CalendarEvent` objects (possibly empty).
    """
    import json as _json

    system = (
        "Du er en ekspert på å trekke ut ishall-bookingsdata fra HTML. "
        "Finn alle bookinger/hendelser i den gitte HTML-en for den angitte "
        "perioden. Svar KUN med et JSON-array på formen: "
        '[{"date": "DD.MM.ÅÅÅÅ", "name": "...", "duration_hours": 1.5}, ...]  '
        "Hvis ingen hendelser finnes, svar med en tom array []."
    )

    # Truncate HTML to avoid token limits (~16K chars ~ 4K tokens)
    truncated_html = raw_html[:16_000]
    date_range_str = (
        f"{start_date.strftime('%d.%m.%Y')} til {end_date.strftime('%d.%m.%Y')}"
    )
    user_msg = (
        f"Kilde: {source_name}\nPeriode: {date_range_str}\n\nHTML:\n{truncated_html}"
    )

    try:
        response = client.complete(system=system, user=user_msg, temperature=0.1)
        text = response.text.strip()

        # Strip markdown fences
        for fence in ("```json", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                break

        raw_events = _json.loads(text)
        if not isinstance(raw_events, list):
            return []

        events: list[CalendarEvent] = []
        for item in raw_events:
            if not isinstance(item, dict):
                continue
            date_str = item.get("date", "")
            name = item.get("name", "")
            duration = float(item.get("duration_hours", 1.0))
            if not date_str or not name:
                continue
            try:
                dt = datetime.strptime(date_str, "%d.%m.%Y")
            except ValueError:
                continue
            events.append(
                CalendarEvent(
                    date=date_str,
                    name=name,
                    datetime=dt,
                    duration_hours=duration,
                )
            )
        return events
    except Exception:  # noqa: BLE001
        return []


def _events_to_dicts(events: list[CalendarEvent]) -> list[dict[str, Any]]:
    """Serialise :class:`CalendarEvent` objects to plain dicts for JSON output."""
    result = []
    for e in events:
        result.append(
            {
                "date": e.date,
                "name": e.name,
                "datetime": e.datetime.isoformat(),
                "duration_hours": e.duration_hours,
            }
        )
    return result


def _make_default_client() -> "LMStudioClient":
    from ..llm.lm_studio_client import LMStudioClient

    return LMStudioClient()


# ---------------------------------------------------------------------------
# Outlook scraper subclass that captures raw HTML
# ---------------------------------------------------------------------------


class _OutlookScraperWithHtml:
    """Thin wrapper around :class:`CalendarScraper` that captures raw HTML.

    The base :class:`CalendarScraper` does not expose the raw HTML to callers
    because it calls ``self._parse_outlook_calendar(page_content)`` internally.
    This subclass intercepts the parse call to save the last HTML seen so
    Stage 2 can pass it to the LLM fallback.
    """

    def __init__(self) -> None:
        from ..data_sources.calendar_scraper import CalendarScraper

        self._scraper = CalendarScraper()
        self.last_raw_html: str = ""
        # Monkey-patch to intercept raw HTML
        original_parse = self._scraper._parse_outlook_calendar  # type: ignore[attr-defined]

        def _patched_parse(html: str):  # type: ignore[no-untyped-def]
            self.last_raw_html += html  # accumulate across months
            return original_parse(html)

        self._scraper._parse_outlook_calendar = _patched_parse  # type: ignore[attr-defined]

    def scrape_calendar(
        self,
        url: str,
        name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        return self._scraper.scrape_calendar(url, name, start_date, end_date)
