"""Credentialed scraping helpers for Stage 2.

Provides :func:`_try_credentialed_scrape` as the entry point, which checks
environment-variable credentials and delegates to
:func:`_run_credentialed_bookup_or_outlook` for the Playwright-based login
flow.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from ..models import CalendarEvent
from ..utils.calendar_cache import CalendarCache
from .scraper_bookup import _parse_bookup_timegrid
from .scraper_outlook import _parse_date_param_calendar, _parse_outlook_calendar
from .scraper_strategies import get_strategy, requires_credentials


def _try_credentialed_scrape(
    name: str,
    url: str,
    start_date: datetime,
    end_date: datetime,
    cache: CalendarCache | None = None,
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
        return _run_credentialed_bookup_or_outlook(
            name, url, start_date, end_date, strategy, creds, cache
        )
    except Exception as exc:
        return [], f"Credentialed scrape feilet for '{name}': {exc}"


def _run_credentialed_bookup_or_outlook(
    name: str,
    url: str,
    start_date: datetime,
    end_date: datetime,
    strategy: Any,
    creds: dict[str, str],
    cache: CalendarCache | None = None,
) -> tuple[list[CalendarEvent], str]:
    """Playwright scraper that logs in before scraping.

    Executes *strategy.initial_navigation* steps (with ``${VAR}`` placeholders
    replaced by *creds* values). For BookUp SPA sources, delegates to the
    BookUp timegrid parser after login. For Outlook sources, runs the standard
    iframe month-by-month scraping loop.
    """
    from string import Template
    from playwright.sync_api import sync_playwright
    from ..data_sources.calendar_scraper import OutlookCalendarScraper

    events: list[CalendarEvent] = []
    raw_html: str = ""
    norwegian_months = OutlookCalendarScraper(cache).norwegian_months

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

            # Now run the appropriate scraping loop based on engine
            is_bookup = getattr(strategy, 'engine', None) is not None and getattr(strategy.engine, 'value', '') == 'bookup_spa'
            if is_bookup:
                # BookUp SPA: find the app.html iframe and extract FullCalendar events
                page.wait_for_timeout(5_000)  # Wait for post-login redirect
                frame = page.frame(url=lambda u: 'app.html' in u)
                if frame:
                    # Click "Se tilgjengelighet" if visible
                    btn = frame.locator("text=Se tilgjengelighet")
                    if btn.count() > 0:
                        btn.first.click()
                        frame.wait_for_timeout(5_000)
                    # Navigate weeks and extract
                    start_date_ref = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date_ref = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    total_days = (end_date_ref - start_date_ref).days
                    max_weeks = (total_days // 7) + 3
                    for _ in range(max_weeks):
                        frame.wait_for_timeout(1_500)
                        week_events = _parse_bookup_timegrid(frame)
                        for ev in week_events:
                            if start_date_ref <= ev.datetime <= end_date_ref + __import__("datetime").timedelta(days=1):
                                events.append(ev)
                        next_btn = frame.locator(".fc-next-button, button[aria-label*='next'], .fc-next")
                        if next_btn.count() > 0:
                            try:
                                next_btn.first.click()
                                frame.wait_for_timeout(1_500)
                            except Exception:
                                break
                        else:
                            break
            else:
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
