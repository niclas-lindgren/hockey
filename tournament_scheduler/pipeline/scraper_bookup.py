"""BookUp SPA scraper for Stage 2.

Provides BookUp FullCalendar timeGrid scraping for Tønsberg and Sandefjord
Penguins calendar sources.  All three helpers (:func:`_run_bookup_scraper`,
:func:`_bookup_navigate_to_date`, :func:`_parse_bookup_timegrid`) share the
Playwright ``frame`` context and FullCalendar DOM semantics.
"""

from __future__ import annotations

import json as _json
from datetime import datetime, timedelta
from typing import Any

from ..models import CalendarEvent


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
                    if start_date_ref <= ev.datetime <= end_date_ref + timedelta(days=1):
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
