"""Calendar scraping using Playwright - extracted from monolithic code."""

import sys
import re
from datetime import datetime
from typing import List
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from tournament_scheduler.models import CalendarEvent
from tournament_scheduler.interfaces import CalendarScraper as BaseCalendarScraper


class OutlookCalendarScraper(BaseCalendarScraper):
    """Handles scraping of Outlook calendars using Playwright."""

    def __init__(self):
        """Initialize calendar scraper."""
        self.norwegian_months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'januar': 1, 'februar': 2, 'mars': 3, 'april': 4,
            'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
        }

    def scrape_calendar(self, url: str, calendar_type: str,
                       start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Scrape Outlook calendar using Playwright.

        Args:
            url: Calendar URL
            calendar_type: Type of calendar (for logging)
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of CalendarEvent objects
        """
        events = []

        current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_month = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_month = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        months_to_start = ((start_month.year - current_month.year) * 12 +
                          (start_month.month - current_month.month))
        months_to_scrape = ((end_month.year - start_month.year) * 12 +
                           (end_month.month - start_month.month)) + 1

        try:
            with sync_playwright() as p:
                print(f"  Launching browser for {calendar_type}...", flush=True)
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                print(f"  Loading {calendar_type} calendar page...", flush=True)
                page.goto(url, timeout=30000)
                page.wait_for_timeout(2000)

                iframe_element = page.query_selector('iframe')
                if not iframe_element:
                    print(f"Warning: Could not find {calendar_type} iframe")
                    browser.close()
                    return events

                iframe = iframe_element.content_frame()
                if not iframe:
                    print(f"Warning: Could not load {calendar_type} iframe content")
                    browser.close()
                    return events

                print(f"  Accessing calendar iframe...", flush=True)
                iframe.wait_for_timeout(3000)

                # Navigate to start month
                if months_to_start > 0:
                    print(f"  Navigating to start month ({start_month.strftime('%B %Y')})...", flush=True)
                    for _ in range(months_to_start):
                        try:
                            next_button = iframe.query_selector('button[aria-label*="Go to next month"]')
                            if next_button:
                                next_button.click()
                                iframe.wait_for_timeout(1000)
                        except Exception as e:
                            print(f"  Warning: Could not navigate to start month: {e}", flush=True)
                            break
                elif months_to_start < 0:
                    print(f"  Navigating to start month ({start_month.strftime('%B %Y')})...", flush=True)
                    for _ in range(abs(months_to_start)):
                        try:
                            prev_button = iframe.query_selector('button[aria-label*="Go to previous month"]')
                            if prev_button:
                                prev_button.click()
                                iframe.wait_for_timeout(1000)
                        except Exception as e:
                            print(f"  Warning: Could not navigate to start month: {e}", flush=True)
                            break

                # Scrape events
                print(f"  Scraping {months_to_scrape} months of events ({start_month.strftime('%b %Y')} to {end_month.strftime('%b %Y')})...", flush=True)
                for month_offset in range(months_to_scrape):
                    iframe.wait_for_timeout(1000)
                    if month_offset > 0:
                        print(f"    Month {month_offset + 1}/{months_to_scrape}...", flush=True)

                    page_content = iframe.content()
                    month_events = self._parse_outlook_calendar(page_content)
                    events.extend(month_events)

                    if month_offset < months_to_scrape - 1:
                        try:
                            next_button = iframe.query_selector('button[aria-label*="Go to next month"]')
                            if next_button:
                                next_button.click()
                                iframe.wait_for_timeout(1500)
                            else:
                                print(f"Could not find next month button in {calendar_type}")
                                break
                        except Exception as e:
                            print(f"Warning: Could not navigate months: {e}")
                            break

                browser.close()

            # Deduplicate
            unique_events = []
            seen = set()
            for event in events:
                key = (event.date, event.name)
                if key not in seen:
                    seen.add(key)
                    unique_events.append(event)

            print(f"  ✓ Scraped {len(unique_events)} events from {calendar_type} calendar\n", flush=True)
            return unique_events

        except Exception as e:
            print(f"  ✗ Failed to scrape {calendar_type} calendar: {e}\n", file=sys.stderr, flush=True)
            return []

    def _parse_outlook_calendar(self, text: str) -> List[CalendarEvent]:
        """Parse events from Outlook calendar HTML.

        Args:
            text: HTML content from calendar

        Returns:
            List of CalendarEvent objects
        """
        events = []
        aria_pattern = r'aria-label="([^"]+)"'
        matches = re.findall(aria_pattern, text)

        for aria_label in matches:
            if 'Go to' in aria_label or 'Print' in aria_label or 'Month' in aria_label:
                continue

            parts = [p.strip() for p in aria_label.split(',')]
            if len(parts) < 4:
                continue

            event_name = parts[0]
            time_part = parts[1] if len(parts) > 1 else ''

            # Parse time and duration
            start_time = None
            end_time = None
            duration_hours = 0

            # AM/PM format
            time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)\s+to\s+(\d{1,2}):(\d{2})\s*(AM|PM)',
                                  time_part, re.IGNORECASE)
            if time_match:
                start_hour, start_min, start_period, end_hour, end_min, end_period = time_match.groups()
                start_hour, start_min, end_hour, end_min = map(int, [start_hour, start_min, end_hour, end_min])

                if start_period.upper() == 'PM' and start_hour != 12:
                    start_hour += 12
                elif start_period.upper() == 'AM' and start_hour == 12:
                    start_hour = 0

                if end_period.upper() == 'PM' and end_hour != 12:
                    end_hour += 12
                elif end_period.upper() == 'AM' and end_hour == 12:
                    end_hour = 0

                start_time = start_hour + start_min / 60.0
                end_time = end_hour + end_min / 60.0
                if end_time < start_time:
                    end_time += 24
                duration_hours = end_time - start_time
            else:
                # 24-hour format
                time_match = re.search(r'(\d{1,2}):(\d{2})\s+to\s+(\d{1,2}):(\d{2})', time_part)
                if time_match:
                    start_hour, start_min, end_hour, end_min = map(int, time_match.groups())
                    start_time = start_hour + start_min / 60.0
                    end_time = end_hour + end_min / 60.0
                    if end_time < start_time:
                        end_time += 24
                    duration_hours = end_time - start_time

            # Parse date
            found_date = None
            for i, part in enumerate(parts):
                for month_name, month_num in self.norwegian_months.items():
                    if month_name in part.lower():
                        day_match = re.search(r'\b(\d{1,2})\b', part)
                        year_match = None
                        for j in range(i, min(i+2, len(parts))):
                            year_match = re.search(r'\b(20\d{2})\b', parts[j])
                            if year_match:
                                break
                        if day_match and year_match:
                            try:
                                found_date = datetime(
                                    int(year_match.group(1)),
                                    month_num,
                                    int(day_match.group(1))
                                )
                                break
                            except ValueError:
                                continue
                if found_date:
                    break

            if found_date and event_name:
                # Apply start_time to datetime if parsed
                event_datetime = found_date
                if start_time is not None:
                    hours = int(start_time)
                    minutes = int((start_time - hours) * 60)
                    event_datetime = found_date.replace(hour=hours, minute=minutes)

                events.append(CalendarEvent(
                    date=found_date.strftime('%d.%m.%Y'),
                    name=event_name,
                    datetime=event_datetime,
                    duration_hours=duration_hours
                ))

        # Deduplicate
        unique_events = []
        seen = set()
        for event in events:
            key = (event.date, event.name)
            if key not in seen:
                seen.add(key)
                unique_events.append(event)

        return unique_events


# Backward compatibility alias
CalendarScraper = OutlookCalendarScraper
