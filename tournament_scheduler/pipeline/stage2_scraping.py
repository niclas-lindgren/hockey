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

from ..models import CalendarEvent
from .scraper_strategies import get_strategy, requires_credentials, needs_llm_agent
from .state import PipelineState, StageName, StageStatus

# ---------------------------------------------------------------------------
# Source type constants
# ---------------------------------------------------------------------------

SOURCE_OUTLOOK = "outlook"
SOURCE_HTML = "html"
SOURCE_ICAL = "ical"
SOURCE_GOOGLE = "google"

_BROWSER_SOURCE_TYPES = {SOURCE_OUTLOOK, SOURCE_HTML}
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
    max_workers: int = 4,
) -> dict[str, Any]:
    """Run Stage 2 scraping for all sources listed in *config*.

    Sources are scraped in parallel via :class:`~concurrent.futures.ThreadPoolExecutor`
    because each source creates its own Playwright browser context (or uses HTTP-only
    iCal feeds) — there is no shared browser state.

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
    max_workers:
        Number of worker threads for the executor. Default 4.

    Returns
    -------
    dict
        Checkpoint data with per-source results.
    """
    state.write_stage(StageName.SCRAPING, {}, status=StageStatus.RUNNING)

    sources: list[dict[str, Any]] = config.get("sources", [])

    if not sources:
        reason = (
            "Ingen kalenderkilder er konfigurert. Legg til en 'sources'-seksjon i input.json "
            "for a hente kalenderdata (f.eks. Kongsberg ishall, Skien o.l.). Uten kalenderdata "
            "kan ikke pipelinen planlegge rundt faktiske bookinger og vil foresla fantasidatoer."
        )
        if strict:
            state.write_stage(StageName.SCRAPING, {}, status=StageStatus.FAILED)
            state.mark_failed(StageName.SCRAPING, error=reason)
            raise Stage2Error([{"name": "(ingen kilder)", "reason": reason}])
        result: dict[str, Any] = {"sources": [], "blocked": [], "warning": reason}
        state.write_stage(StageName.SCRAPING, result, status=StageStatus.DONE)
        state.mark_done(StageName.SCRAPING)
        return result

    source_results: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    llm_fallback: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(
                _scrape_source,
                source_cfg,
                start_date=start_date,
                end_date=end_date,
            ): source_cfg
            for source_cfg in sources
        }
        for future in as_completed(future_to_source):
            source_cfg = future_to_source[future]
            try:
                source_result = future.result()
            except Exception as exc:
                source_result = {
                    "name": source_cfg.get("name", "ukjent kilde"),
                    "url": source_cfg.get("url", ""),
                    "type": source_cfg.get("type", SOURCE_OUTLOOK),
                    "events": [],
                    "event_count": 0,
                    "blocked": True,
                    "block_reason": f"Scraper krasjet: {exc}",
                    "scraper_error": str(exc),
                    "llm_fallback": False,
                }
            source_results.append(source_result)
            if source_result.get("blocked"):
                blocked.append({"name": source_cfg.get("name", "?"), **source_result})
            if source_result.get("llm_fallback"):
                llm_fallback.append({
                    "name": source_result["name"],
                    "url": source_result.get("url", ""),
                    "llm_strategy": source_result.get("llm_strategy", {}),
                })

    checkpoint: dict[str, Any] = {
        "sources": source_results,
        "blocked": [b["name"] for b in blocked],
        "llm_fallback": llm_fallback,
    }

    status = StageStatus.DONE if not blocked else StageStatus.FAILED
    state.write_stage(StageName.SCRAPING, checkpoint, status=status)
    if not blocked:
        state.mark_done(StageName.SCRAPING)

    if blocked and strict:
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
) -> dict[str, Any]:
    """Scrape a single source deterministically.

    ``outlook`` / ``html`` sources are scraped via Playwright by loading the
    URL and extracting events from the Outlook Web Calendar iframe (if present).
    ``ical`` / ``google`` sources use the HTTP-based iCal scraper directly.

    If the deterministic scrape returns zero events and the source strategy
    requires credentials, the function automatically retries with environment-
    variable credentials injected via Playwright login.

    If that also fails, the result is marked with ``llm_fallback=True`` so the
    caller can attempt LLM-driven scraping via browser_worker.
    """
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
        "llm_fallback": False,
    }

    # --- Run the deterministic scraper ---
    events: list[CalendarEvent] = []
    scraper_error: str = ""

    try:
        # Jutul/Bærum uses StyledCalendar (FullCalendar) in a cross-origin iframe.
        # Navigate to the embed URL directly instead.
        if "baerumishall.no" in url:
            events, _ = _run_styledcalendar_scraper(name, start_date, end_date)
        elif "bookup.no" in url:
            events, _ = _run_bookup_scraper(url, name, start_date, end_date)
        elif source_type in _BROWSER_SOURCE_TYPES:
            events, _ = _run_outlook_scraper(url, name, start_date, end_date)
        elif source_type in _ICAL_SOURCE_TYPES:
            events = _run_ical_scraper(url, name, start_date, end_date, source_type)
        else:
            scraper_error = f"Ukjent kildetype '{source_type}'."
    except Exception as exc:  # noqa: BLE001
        scraper_error = str(exc)

    if scraper_error:
        result["scraper_error"] = scraper_error

    # --- If deterministic failed, try credentialed fallback ---
    if not events:
        events, cred_error = _try_credentialed_scrape(
            name, url, start_date, end_date
        )
        if cred_error:
            scraper_error = scraper_error or cred_error

    # --- If still no events, assess LLM fallback viability ---
    if not events:
        strategy = get_strategy(name)
        credential_hint = _credential_hint_for_source(name)
        block_reason = (
            f"Kilde '{name}' returnerte 0 hendelser -- "
            "skraper odelagt eller hallen er stengt?"
            + (f" {credential_hint}" if credential_hint else "")
        )
        result["blocked"] = True
        result["block_reason"] = block_reason

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


def _credential_hint_for_source(source_name: str) -> str:
    """Return a Norwegian credential hint for a source, or empty string.

    Looks up the scraper strategy and, if it requires environment-variable
    credentials, returns a message naming them so the user knows what to set.
    """
    try:
        strategy = get_strategy(source_name)
        if strategy and requires_credentials(strategy):
            vars_list = ", ".join(strategy.credential_env_vars)
            engine = strategy.engine.value.replace("_", " ")
            return (
                f"Kilden bruker {engine} og krever innlogging. "
                f"Angi miljovariablene {vars_list}, "
                f"eller kjor pipeline interaktivt for a bli spurt."
            )
    except Exception:
        pass
    return ""


def _try_credentialed_scrape(
    name: str,
    url: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[list[CalendarEvent], str]:
    """Retry scraping with environment-variable credentials.

    Checks the source's scraper strategy for ``credential_env_vars``. If all
    required env vars are set, launches Playwright, executes the strategy's
    ``initial_navigation`` login steps, then attempts standard Outlook/iframe
    scraping.

    Returns (events, error_string). Events is empty on failure; error_string
    is empty on success.
    """
    strategy = get_strategy(name)
    if not strategy or not requires_credentials(strategy):
        return [], ""

    # Check that all required env vars are available
    missing: list[str] = []
    creds: dict[str, str] = {}
    for var in strategy.credential_env_vars:
        val = os.environ.get(var, "")
        if not val:
            missing.append(var)
        else:
            creds[var] = val

    if missing:
        return [], (
            f"Kilden '{name}' krever innlogging men miljovariablene "
            f"{', '.join(missing)} er ikke satt."
        )

    if not strategy.initial_navigation:
        return [], f"Kilden '{name}' har credentials men ingen initial_navigation."

    # Execute the login flow via Playwright, then scrape
    try:
        return _run_credentialed_outlook_scraper(
            name, url, start_date, end_date, strategy, creds
        )
    except Exception as exc:
        return [], f"Credentialed scrape feilet for '{name}': {exc}"


def _run_credentialed_outlook_scraper(
    name: str,
    url: str,
    start_date: datetime,
    end_date: datetime,
    strategy: Any,
    creds: dict[str, str],
) -> tuple[list[CalendarEvent], str]:
    """Playwright scraper that logs in before scraping.

    Executes *strategy.initial_navigation* steps (with ``${VAR}`` placeholders
    replaced by *creds* values), then runs the standard Outlook/iframe month-by-
    month scraping loop.
    """
    from string import Template
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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to the calendar URL
            page.goto(url, timeout=30_000)
            page.wait_for_timeout(3_000)

            # Execute login / initial navigation steps
            for step in strategy.initial_navigation:
                cmd = step.get("cmd", "")
                selector_tmpl = step.get("selector", "")
                text_tmpl = step.get("text", "")
                wait_ms = step.get("wait_ms", 1_500)

                # Substitute env vars in selector and text
                selector = Template(selector_tmpl).safe_substitute(creds)
                text = Template(text_tmpl).safe_substitute(creds) if text_tmpl else ""

                if cmd == "click" and selector:
                    try:
                        el = page.locator(selector)
                        if el.count() > 0:
                            el.first.click()
                    except Exception:
                        pass
                elif cmd == "type" and selector:
                    try:
                        el = page.locator(selector)
                        if el.count() > 0:
                            el.first.fill(text)
                    except Exception:
                        pass
                elif cmd == "goto" and step.get("url"):
                    page.goto(step["url"], timeout=30_000)

                page.wait_for_timeout(wait_ms)

            # Now run the standard scraping loop
            _credentialed_scrape_months(
                page, events, months_to_scrape, norwegian_months
            )

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


def _credentialed_scrape_months(
    page: Any,
    events: list[CalendarEvent],
    months_to_scrape: int,
    norwegian_months: dict[str, int],
) -> None:
    """Scrape calendar months from an already-authenticated Playwright page.

    Tries iframe-based extraction first, then falls back to date-parameter
    navigation, then plain DOM text extraction.
    """
    iframe_element = page.query_selector("iframe")
    has_iframe = iframe_element is not None and iframe_element.content_frame() is not None

    if has_iframe:
        iframe = iframe_element.content_frame()
        iframe.wait_for_timeout(3_000)
        for month_idx in range(months_to_scrape):
            iframe.wait_for_timeout(1_000)
            page_content = iframe.content()
            month_events = _parse_outlook_calendar(page_content, norwegian_months)
            events.extend(month_events)
            if month_idx < months_to_scrape - 1:
                try:
                    next_btn = iframe.query_selector(
                        'button[aria-label*="next month"]'
                    )
                    if next_btn:
                        next_btn.click()
                        iframe.wait_for_timeout(1_500)
                except Exception:
                    pass
    else:
        # Try date-parameter navigation
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed = urlparse(page.url)
        query = parse_qs(parsed.query)
        current_month = datetime.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        for month_idx in range(months_to_scrape):
            date_str = current_month.strftime("%Y-%m-%d")
            q = dict(query)
            q["date"] = [date_str]
            new_query = urlencode(q, doseq=True)
            month_url = urlunparse(parsed._replace(query=new_query))
            try:
                page.goto(month_url, timeout=30_000)
                page.wait_for_timeout(3_000)
                page_content = page.content()
                month_events = _parse_date_param_calendar(
                    page_content, current_month, norwegian_months
                )
                events.extend(month_events)
            except Exception:
                pass
            if current_month.month == 12:
                current_month = current_month.replace(
                    year=current_month.year + 1, month=1
                )
            else:
                current_month = current_month.replace(month=current_month.month + 1)
    """Return a Norwegian credential hint for a source, or empty string.

    Looks up the scraper strategy and, if it requires environment-variable
    credentials, returns a message naming them so the user knows what to set.
    """
    try:
        strategy = get_strategy(source_name)
        if strategy and requires_credentials(strategy):
            vars_list = ", ".join(strategy.credential_env_vars)
            engine = strategy.engine.value.replace("_", " ")
            return (
                f"Kilden bruker {engine} og krever innlogging. "
                f"Angi miljovariablene {vars_list}, "
                f"eller kjor pipeline interaktivt for a bli spurt."
            )
    except Exception:
        pass
    return ""


def _run_ical_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
    source_type: str,
) -> list[CalendarEvent]:
    """Run the iCal scraper for ``ical`` and ``google`` source types.

    Both use :class:`ICalScraper` (HTTP-fetched iCal feeds). The ``url`` may
    be a full feed URL (https://ics.teamup.com/...) or a Google Calendar
    email-style ID (``name@gmail.com``) which ``ICalScraper`` expands into the
    public Google Calendar iCal feed URL automatically.
    """
    from ..data_sources.ical_scraper import ICalScraper

    scraper = ICalScraper(url)
    return scraper.scrape_calendar(url, name, start_date, end_date)


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


# ---------------------------------------------------------------------------
# Outlook iframe-based scraper (Playwright)
# ---------------------------------------------------------------------------


def _run_outlook_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[list[CalendarEvent], str]:
    """Playwright scraper for calendar pages.

    Supports two page layouts:
    1. **Outlook iframe** — loads the URL, finds the calendar iframe, iterates
       through each month via ``Go to next month`` button, and parses
       ``aria-label`` attributes to extract events.
    2. **Date-parameter pages** (e.g. ``?date=2026-09-01``) — when no iframe
       is found, navigates by appending/replacing the ``date`` query parameter
       with each month's start date.

    Returns (events, raw_html) where raw_html is the accumulated page content
    across all months.
    """
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(2000)

            iframe_element = page.query_selector("iframe")
            has_iframe = iframe_element is not None and iframe_element.content_frame() is not None

            if has_iframe:
                # ---- Outlook iframe approach ----
                iframe = iframe_element.content_frame()
                iframe.wait_for_timeout(3000)

                for month_idx in range(months_to_scrape):
                    iframe.wait_for_timeout(1000)
                    page_content = iframe.content()
                    raw_html += page_content

                    month_events = _parse_outlook_calendar(page_content, norwegian_months)
                    events.extend(month_events)

                    if month_idx < months_to_scrape - 1:
                        try:
                            next_btn = iframe.query_selector(
                                'button[aria-label*="next month"]'
                            )
                            if next_btn:
                                next_btn.click()
                                iframe.wait_for_timeout(1500)
                        except Exception:
                            pass
            else:
                # ---- Date-parameter approach (e.g. ?date=YYYY-MM-DD) ----
                parsed = urlparse(url)
                query = parse_qs(parsed.query)

                current_month = start_month
                for month_idx in range(months_to_scrape):
                    # Build URL with date parameter
                    date_str = current_month.strftime("%Y-%m-%d")
                    q = dict(query)
                    q["date"] = [date_str]
                    new_query = urlencode(q, doseq=True)
                    month_url = urlunparse(parsed._replace(query=new_query))

                    try:
                        page.goto(month_url, timeout=30000)
                        page.wait_for_timeout(3000)
                        page_content = page.content()
                        raw_html += page_content

                        month_events = _parse_date_param_calendar(
                            page_content, current_month, norwegian_months
                        )
                        events.extend(month_events)
                    except Exception:
                        pass

                    # Next month
                    if current_month.month == 12:
                        current_month = current_month.replace(year=current_month.year + 1, month=1)
                    else:
                        current_month = current_month.replace(month=current_month.month + 1)

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


# ---------------------------------------------------------------------------
# BookUp SPA scraper (FullCalendar timeGrid in iframe)
# ---------------------------------------------------------------------------


def _run_bookup_scraper(
    url: str,
    name: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[list[CalendarEvent], str]:
    """Scrape a BookUp SPA calendar (Tønsberg, Sandefjord Penguins).

    BookUp shows an iframe with a FullCalendar timeGrid view after clicking
    "Se tilgjengelighet".  Events are rendered as ``.fc-bgevent`` background
    blocks inside a ``.fc-time-grid`` table.

    The scraper:
      1. Navigates to the BookUp index page.
      2. Finds the ``app.html`` iframe.
      3. Clicks "Se tilgjengelighet" to reveal the calendar.
      4. Iterates week-by-week via the "next" button.
      5. Extracts ``.fc-bgevent`` elements with date / time / title.
    """
    from playwright.sync_api import sync_playwright

    events: list[CalendarEvent] = []
    raw_html: str = ""

    start_date_ref = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date_ref = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    total_days = (end_date_ref - start_date_ref).days
    max_weeks = (total_days // 7) + 3  # pad a bit

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30_000, wait_until="networkidle")
            page.wait_for_timeout(3_000)

            # Find the BookUp app iframe
            frame = page.frame(url=lambda u: "app.html" in u)
            if not frame:
                browser.close()
                return [], raw_html

            # Click "Se tilgjengelighet"
            btn = frame.locator("text=Se tilgjengelighet")
            if btn.count() == 0:
                browser.close()
                return [], raw_html
            btn.first.click()
            frame.wait_for_timeout(5_000)

            # Navigate to start month if possible
            _bookup_navigate_to_date(frame, start_date_ref)

            # Scrape week by week
            for week_idx in range(max_weeks):
                frame.wait_for_timeout(1_500)
                page_content = frame.content()
                raw_html += page_content

                week_events = _parse_bookup_timegrid(frame)
                # Filter to date range
                for ev in week_events:
                    if start_date_ref <= ev.datetime <= end_date_ref + __import__("datetime").timedelta(days=1):
                        events.append(ev)

                # Click next week
                next_btn = frame.locator(".fc-next-button, button[aria-label*='next'], .fc-next")
                if next_btn.count() > 0:
                    try:
                        next_btn.first.click()
                        frame.wait_for_timeout(1_500)
                    except Exception:
                        break
                else:
                    break

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


def _bookup_navigate_to_date(frame: Any, target: datetime) -> None:
    """Navigate the BookUp FullCalendar to the target date via prev/next.

    Reads the current visible week from the first ``fc-day-header`` element
    and clicks next/prev until the target date is in view.
    """
    import json as _json
    for _ in range(52):  # safety limit
        raw = frame.evaluate(
            "JSON.stringify(Array.from(document.querySelectorAll('[data-date]')).map(e => e.getAttribute('data-date')))"
        )
        dates: list[str] = _json.loads(raw) if isinstance(raw, str) else []
        if not dates:
            break
        try:
            first_date = datetime.strptime(dates[0], "%Y-%m-%d")
            last_date = datetime.strptime(dates[-1], "%Y-%m-%d")
        except (ValueError, IndexError):
            break
        if first_date <= target <= last_date:
            break
        if target < first_date:
            btn = frame.locator(".fc-prev-button")
        else:
            btn = frame.locator(".fc-next-button")
        if btn.count() > 0:
            try:
                btn.first.click()
                frame.wait_for_timeout(1_000)
            except Exception:
                break
        else:
            break


def _parse_bookup_timegrid(frame: Any) -> list[CalendarEvent]:
    """Extract events from a BookUp FullCalendar timeGrid week view.

    Maps ``.fc-bgevent`` elements to dates by finding their column's
    ``data-date`` attribute on the corresponding header ``<th>``.
    """
    import json as _json

    events: list[CalendarEvent] = []

    try:
        raw = frame.evaluate("""
            (() => {
                // Build date -> column index map from headers
                const headers = document.querySelectorAll('.fc-day-header[data-date]');
                const dateMap = {};
                headers.forEach((th, i) => {
                    dateMap[i] = th.getAttribute('data-date');
                });
                if (Object.keys(dateMap).length === 0) return JSON.stringify([]);

                // Get time slot labels (fc-axis)
                const timeLabels = document.querySelectorAll('.fc-axis.fc-time');
                const times = Array.from(timeLabels).map(el => el.innerText.trim());

                // Find the fc-time-grid container
                const grid = document.querySelector('.fc-time-grid');
                if (!grid) return JSON.stringify([]);

                // Get all columns in the content skeleton
                const cols = grid.querySelectorAll('.fc-content-skeleton .fc-content-col');
                const results = [];
                cols.forEach((col, colIdx) => {
                    const date = dateMap[colIdx];
                    if (!date) return;
                    const bgEvents = col.querySelectorAll('.fc-bgevent');
                    bgEvents.forEach(ev => {
                        const title = ev.getAttribute('title') || ev.innerText.trim() || 'Booket';
                        const style = ev.getAttribute('style') || '';
                        results.push({ date, title, style, colIdx });
                    });
                });
                return JSON.stringify(results);
            })()
        """)

        raw_events = _json.loads(raw) if isinstance(raw, str) else []
        if not isinstance(raw_events, list):
            return events

        for item in raw_events:
            date_str = item.get("date", "")
            title = item.get("title", "Booket")
            if not date_str:
                continue
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            # Try to extract time from style or other attributes
            # BookUp bg-events are positioned via inline style "top:..."
            events.append(
                CalendarEvent(
                    date=dt.strftime("%d.%m.%Y"),
                    name=title,
                    datetime=dt,
                    duration_hours=1.0,
                )
            )

    except Exception:
        pass

    return events


def _run_styledcalendar_scraper(
    name: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[list[CalendarEvent], str]:
    """Scrape StyledCalendar/FullCalendar widget (Bærum ishall/Jutul).

    Opens the StyledCalendar embed URL directly, switches to month view,
    iterates through each target month via the next-button, and extracts
    events from the rendered ``.fc-daygrid-event`` elements.
    """
    import json as _json
    from playwright.sync_api import sync_playwright

    events: list[CalendarEvent] = []
    raw_html = ""
    embed_url = "https://embed.styledcalendar.com/#rYk5U1FtYNByMIMz2AoR"

    start_month = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_month = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months_to_scrape = (
        (end_month.year - start_month.year) * 12
        + (end_month.month - start_month.month)
        + 1
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(embed_url, timeout=30_000)
            page.wait_for_timeout(8_000)  # Wait for JS render

            # Switch to month view
            month_btn = page.query_selector("button.fc-dayGridMonth-button")
            if month_btn:
                is_active = page.evaluate(
                    "document.querySelector('button.fc-dayGridMonth-button')?.classList.contains('fc-button-active')"
                )
                if not is_active:
                    month_btn.click()
                    page.wait_for_timeout(1_000)

            # Navigate to start month
            # First check what month we're on
            for _ in range(24):  # Max 2 years of clicking
                title = page.evaluate(
                    "document.querySelector('.fc-toolbar-title')?.innerText || ''"
                )
                if not title:
                    break
                try:
                    parts = title.lower().split()
                    month_names = [
                        "", "januar", "februar", "mars", "april", "mai", "juni",
                        "juli", "august", "september", "oktober", "november", "desember",
                    ]
                    cur_month = month_names.index(parts[0]) if parts[0] in month_names else 0
                    cur_year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                except (ValueError, IndexError):
                    break

                if cur_year > start_month.year or (cur_year == start_month.year and cur_month >= start_month.month):
                    break

                next_btn = page.query_selector(".fc-next-button")
                if next_btn:
                    next_btn.click()
                    page.wait_for_timeout(500)
                else:
                    break

            # Extract each month
            for month_idx in range(months_to_scrape):
                page.wait_for_timeout(1_000)

                # Extract events from current month view
                raw = page.evaluate("""
                    JSON.stringify(Array.from(document.querySelectorAll('.fc-daygrid-event')).map(e => {
                        const day = e.closest('[data-date]');
                        const date = day ? day.getAttribute('data-date') || '' : '';
                        const title = (e.querySelector('.fc-event-title') || e).innerText.trim();
                        return { date, title };
                    }))
                """)
                raw_events = _json.loads(raw) if isinstance(raw, str) else []
                if not isinstance(raw_events, list):
                    raw_events = []

                for item in raw_events:
                    date_str = item.get("date", "")
                    title = item.get("title", "")
                    if not date_str or not title:
                        continue
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        continue
                    events.append(CalendarEvent(
                        date=dt.strftime("%d.%m.%Y"),
                        name=title,
                        datetime=dt,
                        duration_hours=1.0,
                    ))

                # Navigate to next month
                if month_idx < months_to_scrape - 1:
                    next_btn = page.query_selector(".fc-next-button")
                    if next_btn:
                        next_btn.click()
                        page.wait_for_timeout(500)
                    else:
                        break

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


def _parse_date_param_calendar(
    html: str,
    month_start: datetime,
    norwegian_months: dict[str, int],
) -> list[CalendarEvent]:
    """Parse calendar events from a date-parameter page (brp.exigo.no-style).

    Strips HTML tags and looks for visible event-like text patterns.
    """
    import re
    from datetime import datetime as _dt

    events: list[CalendarEvent] = []
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Look for time ranges (HH:MM-HH:MM) that indicate bookings
    time_pattern = r"(\d{1,2}[\.:]\d{2})\s*-\s*(\d{1,2}[\.:]\d{2})"
    for m in re.finditer(time_pattern, text):
        start_str, end_str = m.groups()
        try:
            sh, sm = (int(x) for x in start_str.replace(".", ":").split(":"))
            eh, em = (int(x) for x in end_str.replace(".", ":").split(":"))
        except ValueError:
            continue
        duration = (eh + em / 60.0) - (sh + sm / 60.0)
        if duration < 0:
            duration += 24
        day = _dt(year=month_start.year, month=month_start.month, day=1)
        events.append(CalendarEvent(
            date=day.strftime("%d.%m.%Y"),
            name=f"Booking {m.group()}",
            datetime=day.replace(hour=sh, minute=sm),
            duration_hours=duration,
        ))
    return events


def _parse_outlook_calendar(
    html: str,
    norwegian_months: dict[str, int],
) -> list[CalendarEvent]:
    """Parse events from a single month's Outlook calendar HTML.

    Uses a regex-based approach on ``aria-label`` attributes, matching the
    pattern used by Outlook Web Calendar::

        "Event name, 10:00 AM to 11:30 AM, Monday, January 15, 2026"

    Returns a list of :class:`CalendarEvent` objects.
    """
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
                r"(\d{1,2}):(\d{2})\s+to\s+(\d{1,2}):(\d{2})",
                time_part,
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
                            found_date = datetime(
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
    cli_args = parser.parse_args()

    from .state import PipelineState, StageName  # noqa: E402
    from datetime import datetime as _dt  # noqa: E402

    _state = PipelineState(cli_args.work_dir)
    _cfg = _state.read_stage(StageName.CONFIG)
    if not _cfg:
        print("Stage 1 checkpoint not found -- run Stage 1 first.", file=sys.stderr)
        sys.exit(1)

    _start = _dt.strptime(_cfg["start_date"], "%Y-%m-%d")
    _end = _dt.strptime(_cfg["end_date"], "%Y-%m-%d")

    try:
        _result = run(_cfg, _state, _start, _end, strict=not cli_args.non_strict)
        n_sources = len(_result.get("sources", []))
        blocked = _result.get("blocked", [])
        print(f"Stage 2 OK -- {n_sources} kilder skannet, {len(blocked)} blokkert")
        sys.exit(0)
    except Stage2Error as _e:
        print(str(_e), file=sys.stderr)
        sys.exit(1)
