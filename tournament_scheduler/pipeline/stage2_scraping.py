"""Stage 2 — scraping with LLM-guided agentic navigation for JS-rendered SPAs.

For each configured calendar source:
  1. ``outlook`` / ``html`` sources use the :class:`LLMGuidedScraper` agent
     loop — the LLM examines the DOM snapshot, decides what Playwright action
     to take (click a button, select a dropdown, etc.), and loops until
     calendar events are extracted or the iteration limit is hit.
  2. ``ical`` / ``google`` sources use the deterministic ICAL scraper (no LLM).
  3. If the agent returns zero events, block with a Norwegian-language error
     message rather than proceeding silently.

Source config format (inside the validated Stage 1 config or provided directly)::

    "sources": [
        {
            "name": "Kongsberg ishall",
            "type": "outlook",   // "outlook" | "html" | "ical" | "google"
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

# LLM client — optional; quality gate is skipped when unavailable
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
SOURCE_HTML = "html"
SOURCE_ICAL = "ical"
SOURCE_GOOGLE = "google"

# Agentic-scraper source types (LLM-guided Playwright navigation)
_AGENTIC_SOURCE_TYPES = {SOURCE_OUTLOOK, SOURCE_HTML}

# Sources that skip the LLM path entirely
_ICAL_SOURCE_TYPES = {SOURCE_ICAL, SOURCE_GOOGLE}

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
    llm_endpoint: str | None = None,
    max_iterations: int | None = None,
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
    strict:
        If ``True``, raise :class:`Stage2Error` when any source is blocked.
    llm_endpoint:
        Optional LLM endpoint URL. If not provided, falls back to the
        ``llm_endpoint`` key from *config* (input.json), then the default.
    max_iterations:
        Optional max agent iterations. Falls back to the
        ``scraper_max_iterations`` key from *config*, then the default (20).

    Returns
    -------
    dict
        Checkpoint data with per-source results.
    """
    # Resolve llm_endpoint: CLI arg > config > default
    _llm_endpoint = llm_endpoint or config.get("llm_endpoint")
    # Resolve max_iterations: CLI arg > config > default
    _max_iterations = max_iterations or config.get("scraper_max_iterations") or 20
    state.write_stage(StageName.SCRAPING, {}, status=StageStatus.RUNNING)

    sources: list[dict[str, Any]] = config.get("sources", [])

    if not sources:
        # No sources configured — we cannot scrape anything
        reason = "Ingen kalenderkilder er konfigurert. Legg til en 'sources'-seksjon i input.json " \
                  "for a hente kalenderdata (f.eks. Kongsberg ishall, Skien o.l.). Uten kalenderdata " \
                  "kan ikke pipelinen planlegge rundt faktiske bookinger og vil foresla fantasidatoer."
        if strict:
            state.write_stage(StageName.SCRAPING, {}, status=StageStatus.FAILED)
            state.mark_failed(StageName.SCRAPING, error=reason)
            raise Stage2Error([{"name": "(ingen kilder)", "reason": reason}])
        # Non-strict: write empty checkpoint and continue (for tests)
        result: dict[str, Any] = {"sources": [], "blocked": [], "warning": reason}
        state.write_stage(StageName.SCRAPING, result, status=StageStatus.DONE)
        state.mark_done(StageName.SCRAPING)
        return result

    source_results: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for source_cfg in sources:
        source_result = _scrape_source(
            source_cfg,
            start_date=start_date,
            end_date=end_date,
            llm_endpoint=_llm_endpoint,
            max_iterations=_max_iterations,
        )
        source_results.append(source_result)
        if source_result.get("blocked"):
            blocked.append({"name": source_cfg.get("name", "?"), **source_result})

    checkpoint: dict[str, Any] = {
        "sources": source_results,
        "blocked": [b["name"] for b in blocked],
    }

    if blocked and strict:
        # Do not persist a checkpoint when the pipeline is blocking — callers
        # should not see a partial/failed Stage 2 artefact on disk.
        checkpoint_file = state.checkpoint_path(StageName.SCRAPING)
        if checkpoint_file.exists():
            checkpoint_file.unlink()
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
    llm_endpoint: str | None = None,
    max_iterations: int = 20,
) -> dict[str, Any]:
    """Scrape a single source and return a per-source result dict.

    For ``outlook`` / ``html`` sources the :class:`LLMGuidedScraper` agent
    loop is used -- the LLM examines the DOM snapshot, decides what Playwright
    action to take, and loops until events are extracted or the iteration
    limit is hit.  ``ical`` / ``google`` sources use the deterministic iCal
    scraper directly.
    """
    from .llm_scraper import LLMGuidedScraper

    name = source_cfg.get("name", "ukjent kilde")
    url = source_cfg.get("url", "")
    source_type = source_cfg.get("type", SOURCE_OUTLOOK).lower()

    result: dict[str, Any] = {
        "name": name,
        "url": url,
        "type": source_type,
        "events": [],
        "event_count": 0,
        "blocked": False,
        "block_reason": "",
    }

    events: list[CalendarEvent] = []
    scraper_error: str = ""

    try:
        if source_type in _AGENTIC_SOURCE_TYPES:
            # LLM-guided agentic scraper for JS-rendered calendars
            kwargs = {}
            if llm_endpoint:
                kwargs["llm_endpoint"] = llm_endpoint
            scraper = LLMGuidedScraper(max_iterations=max_iterations, **kwargs)
            events = scraper.run(
                url=url,
                name=name,
                start_date=start_date,
                end_date=end_date,
            )
        elif source_type in _ICAL_SOURCE_TYPES:
            events = _run_ical_scraper(url, name, start_date, end_date, source_type)
        else:
            scraper_error = f"Ukjent kildetype '{source_type}'."
    except Exception as exc:  # noqa: BLE001
        scraper_error = str(exc)

    if scraper_error:
        result["scraper_error"] = scraper_error

    # --- Block check ---
    if not events:
        block_reason = (
            f"Kilde '{name}' returnerte 0 hendelser -- "
            "skraper odelagt eller hallen er stengt?"
        )
        result["blocked"] = True
        result["block_reason"] = block_reason

    result["events"] = _events_to_dicts(events)
    result["event_count"] = len(events)
    return result





def _run_ical_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
    source_type: str,
) -> list[CalendarEvent]:
    """Run the appropriate iCal scraper.

    Both ``ical`` and ``google`` source types use :class:`ICalScraper`
    (HTTP-fetched iCal feeds). The ``url`` may be a full feed URL
    (https://ics.teamup.com/...) or a Google Calendar email-style ID
    (``name@gmail.com``) which ``ICalScraper`` expands into the public
    Google Calendar iCal feed URL automatically.

    ``GoogleCalendarScraper`` (Playwright-based) is NOT used here because
    the pipeline sources are feed URLs / calendar IDs, not web pages
    containing embedded iframes.
    """
    from ..data_sources.ical_scraper import ICalScraper

    scraper = ICalScraper(url)
    return scraper.scrape_calendar(url, name, start_date, end_date)


# ---------------------------------------------------------------------------
# LLM-guided month navigation
# ---------------------------------------------------------------------------


def _llm_navigate_month(
    *,
    page_html: str,
    current_date: datetime,
    target_month: int,
    target_year: int,
    source_name: str,
    client: LMStudioClient,
) -> dict[str, Any]:
    """Ask the LLM to analyze the calendar HTML and provide navigation instructions.

    The LLM reads the current page's HTML and determines:
    - What month/year is currently displayed
    - What CSS selector or button label to use to go forward/backward
    - Whether we need to go forward or backward to reach the target month

    Returns a dict with:
    - ``current_month`` (int) — the month currently displayed
    - ``current_year`` (int) — the year currently displayed
    - ``next_button_selector`` (str) — CSS selector or aria-label for next-btn
    - ``prev_button_selector`` (str) — CSS selector or aria-label for prev-btn
    - ``on_target`` (bool) — whether we're already on the target month
    """
    from ..llm.lm_studio_client import extract_confidence

    system = (
        "Du er en ekspert på å lese HTML-kode fra Outlook Web Calendar. "
        "Analyser HTML-en og finn ut:\n"
        "1. Hvilken måned og år som vises (se etter overskrifter som 'January 2026')\n"
        "2. Hvilken knapp/lenke som går til neste måned (se etter aria-label som 'Go to next month')\n"
        "3. Hvilken knapp/lenke som går til forrige måned (se etter aria-label som 'Go to previous month')\n\n"
        "Svar KUN med et JSON-objekt på formen:\n"
        '{\n'
        '  "current_month": 1,\n'
        '  "current_year": 2026,\n'
        '  "next_button_selector": "button[aria-label=\'Go to next month\']",\n'
        '  "prev_button_selector": "button[aria-label=\'Go to previous month\']",\n'
        '  "on_target": false\n'
        '}\n\n'
        "current_month er månedsnummer (1-12). current_year er f.eks. 2026. "
        "on_target er true hvis current_month/year matcher target."
    )

    # Truncate HTML to avoid token limits
    truncated_html = page_html[:12_000]

    user_msg = (
        f"Kilde: {source_name}\n"
        f"Mål: {target_month}/{target_year}\n\n"
        f"HTML:\n{truncated_html}"
    )

    response = client.complete(system=system, user=user_msg, temperature=0.1)
    text = response.text.strip()

    # Parse JSON (strip markdown fences)
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            break

    import json as _json
    try:
        data = _json.loads(text)
    except _json.JSONDecodeError:
        # Fallback: guess from current_date
        return {
            "current_month": current_date.month,
            "current_year": current_date.year,
            "next_button_selector": 'button[aria-label*="next month"]',
            "prev_button_selector": 'button[aria-label*="previous month"]',
            "on_target": (
                current_date.month == target_month
                and current_date.year == target_year
            ),
        }

    return {
        "current_month": int(data.get("current_month", current_date.month)),
        "current_year": int(data.get("current_year", current_date.year)),
        "next_button_selector": str(data.get(
            "next_button_selector",
            'button[aria-label*="next month"]',
        )),
        "prev_button_selector": str(data.get(
            "prev_button_selector",
            'button[aria-label*="previous month"]',
        )),
        "on_target": bool(data.get("on_target", False)),
    }


# ---------------------------------------------------------------------------
# LLM quality gate (informational confidence log)
# ---------------------------------------------------------------------------


def _llm_quality_gate(
    *,
    events: list[CalendarEvent],
    source_name: str,
    start_date: datetime,
    end_date: datetime,
    client: LMStudioClient,
) -> dict[str, Any]:
    """Ask the LLM to validate scraped events (informational only).

    The LLM confidence score is recorded in the checkpoint for
    informational/debugging purposes. It NEVER replaces scraped data
    or triggers fallback extraction — the deterministic scraper output
    is always authoritative.

    Returns a dict with ``confidence`` (float).
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

    return {"confidence": confidence_result.confidence}


# ---------------------------------------------------------------------------
# HTML fallback — LLM extracts events from raw HTML when scraper fails
# ---------------------------------------------------------------------------


def _llm_html_fallback(
    *,
    raw_html: str,
    source_name: str,
    start_date: datetime,
    end_date: datetime,
    client: LMStudioClient,
) -> list[CalendarEvent]:
    """Ask the LLM to extract events directly from the raw HTML.

    Used when the deterministic scraper returns zero events. The LLM
    receives all captured HTML and attempts to extract valid events.

    Returns a list of :class:`CalendarEvent` objects (possibly empty).
    """
    import json as _json

    system = (
        "Du er en ekspert på å trekke ut ishall-bookingsdata fra Outlook "
        "Web Calendar HTML. Finn alle bookinger/hendelser i den gitte HTML-en "
        "for den angitte perioden.\n\n"
        "Se etter:\n"
        "- aria-label-attributter som inneholder hendelsesnavn og tid\n"
        "- Dato-overskrifter i kalenderen\n"
        "- Gjentakende hendelser\n\n"
        "Svar KUN med et JSON-array på formen:\n"
        '[{"date": "DD.MM.ÅÅÅÅ", "name": "...", "duration_hours": 1.5}, ...]\n\n'
        "Hvis ingen hendelser finnes, svar med en tom array []."
    )

    # Truncate HTML to avoid token limits (~16K chars ~ 4K tokens)
    truncated_html = raw_html[:16_000]
    date_range_str = (
        f"{start_date.strftime('%d.%m.%Y')} til {end_date.strftime('%d.%m.%Y')}"
    )
    user_msg = (
        f"Kilde: {source_name}\n"
        f"Periode: {date_range_str}\n\n"
        f"HTML:\n{truncated_html}"
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


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


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


def _make_default_client() -> LMStudioClient:
    from ..llm.lm_studio_client import LMStudioClient

    return LMStudioClient()


# ---------------------------------------------------------------------------
def _run_outlook_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[list[CalendarEvent], str]:
    """Run the Playwright/Outlook scraper with LLM-guided month navigation.

    For each month in the requested date range:
      1. Get the iframe content (raw HTML)
      2. Ask the LLM to analyze the HTML and confirm:
         - Which month/year is currently displayed
         - Which CSS selector or aria-label navigates to next/prev month
      3. Parse events from the current month using the regex parser
      4. Navigate to the next month based on LLM instructions

    Returns (events, raw_html) where raw_html is all HTML accumulated
    across months (used for LLM fallback if scraper returns zero events).
    """
    import re
    from playwright.sync_api import sync_playwright
    from ..data_sources.calendar_scraper import OutlookCalendarScraper

    events: list[CalendarEvent] = []
    raw_html: str = ""
    norwegian_months = OutlookCalendarScraper().norwegian_months

    start_month = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_month = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months_to_scrape = (
        (end_month.year - start_month.year) * 12
        + (end_month.month - start_month.month)
        + 1
    )

    # Month markers to verify against (list of (month, year) tuples)
    target_months: list[tuple[int, int]] = []
    y, m = start_month.year, start_month.month
    for _ in range(months_to_scrape):
        target_months.append((m, y))
        m += 1
        if m > 12:
            m = 1
            y += 1

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(2000)

            iframe_element = page.query_selector("iframe")
            if not iframe_element:
                browser.close()
                return events, raw_html

            iframe = iframe_element.content_frame()
            if not iframe:
                browser.close()
                return events, raw_html

            iframe.wait_for_timeout(3000)

            for month_idx, (tgt_month, tgt_year) in enumerate(target_months):
                iframe.wait_for_timeout(1000)
                page_content = iframe.content()
                raw_html += page_content

                # LLM guidance: verify current month and get navigation selectors
                if _LLM_AVAILABLE:
                    try:
                        client = _make_default_client()
                        nav_info = _llm_navigate_month(
                            page_html=page_content,
                            current_date=start_date,
                            target_month=tgt_month,
                            target_year=tgt_year,
                            source_name=name,
                            client=client,
                        )
                        next_sel = nav_info.get(
                            "next_button_selector",
                            'button[aria-label*="next month"]',
                        )
                    except LMStudioUnavailableError:
                        next_sel = 'button[aria-label*="next month"]'
                else:
                    next_sel = 'button[aria-label*="next month"]'

                # Parse events from current month
                month_events = _parse_outlook_calendar(
                    page_content, norwegian_months,
                )
                events.extend(month_events)

                # Navigate to next month
                if month_idx < len(target_months) - 1:
                    try:
                        next_btn = iframe.query_selector(next_sel)
                        if next_btn:
                            next_btn.click()
                            iframe.wait_for_timeout(1500)
                        else:
                            # Fallback to the generic selector
                            fallback_btn = iframe.query_selector(
                                'button[aria-label*="next month"]',
                            )
                            if fallback_btn:
                                fallback_btn.click()
                                iframe.wait_for_timeout(1500)
                    except Exception:
                        pass

            browser.close()
    except Exception:
        pass

    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique: list[CalendarEvent] = []
    for ev in events:
        key = (ev.date, ev.name)
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    return unique, raw_html


def _parse_outlook_calendar(
    html: str,
    norwegian_months: dict[str, int],
) -> list[CalendarEvent]:
    """Parse events from a single month's Outlook calendar HTML.

    Uses the same regex-based approach as
    :class:`OutlookCalendarScraper._parse_outlook_calendar`.
    """
    import re
    from datetime import datetime as _dt

    events: list[CalendarEvent] = []
    aria_pattern = r'aria-label="([^"]+)"'
    matches = re.findall(aria_pattern, html)

    for aria_label in matches:
        if "Go to" in aria_label or "Print" in aria_label or "Month" in aria_label:
            continue

        parts = [p.strip() for p in aria_label.split(",")]
        if len(parts) < 4:
            continue

        event_name = parts[0]
        time_part = parts[1] if len(parts) > 1 else ""

        start_time: float | None = None
        duration_hours = 0.0

        # AM/PM format
        time_match = re.search(
            r"(\d{1,2}):(\d{2})\s*(AM|PM)\s+to\s+(\d{1,2}):(\d{2})\s*(AM|PM)",
            time_part,
            re.IGNORECASE,
        )
        if time_match:
            sh, sm, sp, eh, em, ep = time_match.groups()
            sh, sm, eh, em = map(int, [sh, sm, eh, em])
            if sp.upper() == "PM" and sh != 12:
                sh += 12
            if sp.upper() == "AM" and sh == 12:
                sh = 0
            if ep.upper() == "PM" and eh != 12:
                eh += 12
            if ep.upper() == "AM" and eh == 12:
                eh = 0
            start_time = sh + sm / 60.0
            end_time = eh + em / 60.0
            if end_time < start_time:
                end_time += 24
            duration_hours = end_time - start_time
        else:
            # 24-hour format
            time_match = re.search(
                r"(\d{1,2}):(\d{2})\s+to\s+(\d{1,2}):(\d{2})", time_part,
            )
            if time_match:
                sh, sm, eh, em = map(int, time_match.groups())
                start_time = sh + sm / 60.0
                end_time = eh + em / 60.0
                if end_time < start_time:
                    end_time += 24
                duration_hours = end_time - start_time

        # Parse date from aria-label parts
        found_date = None
        for i, part in enumerate(parts):
            for month_name, month_num in norwegian_months.items():
                if month_name in part.lower():
                    day_match = re.search(r"\b(\d{1,2})\b", part)
                    year_match = None
                    for j in range(i, min(i + 2, len(parts))):
                        yr = re.search(r"\b(20\d{2})\b", parts[j])
                        if yr:
                            year_match = yr
                            break
                    if day_match and year_match:
                        try:
                            found_date = _dt(
                                int(year_match.group(1)),
                                month_num,
                                int(day_match.group(1)),
                            )
                            break
                        except ValueError:
                            continue
            if found_date:
                break

        if found_date and event_name:
            event_dt = found_date
            if start_time is not None:
                hours = int(start_time)
                minutes = int((start_time - hours) * 60)
                event_dt = found_date.replace(hour=hours, minute=minutes)

            events.append(
                CalendarEvent(
                    date=found_date.strftime("%d.%m.%Y"),
                    name=event_name,
                    datetime=event_dt,
                    duration_hours=duration_hours,
                )
            )

    return events


# ---------------------------------------------------------------------------
# CLI entry point — supports: python3 -m tournament_scheduler.pipeline.stage2_scraping
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Stage 2: calendar scraping with LLM-guided agent"
    )
    parser.add_argument("--work-dir", default=".pipeline", help="Pipeline work directory")
    parser.add_argument(
        "--llm-endpoint",
        default=None,
        help="LLM API base URL (overrides config and default)",
    )
    parser.add_argument(
        "--scraper-max-iterations",
        type=int,
        default=None,
        help="Max agent iterations for LLM-guided scraping (default: 20)",
    )
    cli_args = parser.parse_args()

    from .state import PipelineState, StageName  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    _cfg = _state.read_stage(StageName.CONFIG)
    if not _cfg:
        print("Stage 1 checkpoint not found -- run Stage 1 first.", file=sys.stderr)
        sys.exit(1)

    from datetime import datetime as _dt

    _start = _dt.strptime(_cfg["start_date"], "%Y-%m-%d")
    _end = _dt.strptime(_cfg["end_date"], "%Y-%m-%d")

    try:
        _result = run(
            _cfg, _state, _start, _end,
            llm_endpoint=cli_args.llm_endpoint,
            max_iterations=cli_args.scraper_max_iterations,
        )
        n_sources = len(_result.get("sources", []))
        blocked = _result.get("blocked", [])
        print(f"Stage 2 OK -- {n_sources} kilder skannet, {len(blocked)} blokkert")
        sys.exit(0)
    except Stage2Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
