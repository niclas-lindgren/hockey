"""Calendar event caching to avoid repeated scraping."""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from tournament_scheduler.models import CalendarEvent
from rich.console import Console

console = Console()


class CalendarCache:
    """Cache calendar events to avoid repeated scraping."""

    def __init__(self, cache_dir: Optional[str] = None, ttl_minutes: int = 60):
        """Initialize calendar cache.

        Args:
            cache_dir: Directory for cache files. If None, uses ~/.hockey_calendar_cache/
            ttl_minutes: Cache time-to-live in minutes (default: 60)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / '.hockey_calendar_cache'

        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = timedelta(minutes=ttl_minutes)

    def _get_cache_key(self, url: str, calendar_name: str, start_date: datetime, end_date: datetime) -> str:
        """Generate cache key for a calendar request.

        Args:
            url: Calendar URL
            calendar_name: Name of calendar
            start_date: Start date
            end_date: End date

        Returns:
            Cache key (hex hash)
        """
        key_str = f"{url}|{calendar_name}|{start_date.isoformat()}|{end_date.isoformat()}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        url: str,
        calendar_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[List[CalendarEvent]]:
        """Get cached events if available and not stale.

        Args:
            url: Calendar URL
            calendar_name: Name of calendar
            start_date: Start date
            end_date: End date

        Returns:
            List of CalendarEvent objects if cache hit, None otherwise
        """
        cache_key = self._get_cache_key(url, calendar_name, start_date, end_date)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if cache is stale
            cached_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - cached_time > self.ttl:
                return None

            # Reconstruct CalendarEvent objects
            events = []
            for event_data in data['events']:
                event = CalendarEvent(
                    date=event_data['date'],
                    name=event_data['name'],
                    datetime=datetime.fromisoformat(event_data['datetime']),
                    duration_hours=event_data['duration_hours']
                )
                events.append(event)

            return events

        except Exception:
            # If cache is corrupted, return None
            return None

    def set(
        self,
        url: str,
        calendar_name: str,
        start_date: datetime,
        end_date: datetime,
        events: List[CalendarEvent]
    ) -> None:
        """Cache calendar events.

        Args:
            url: Calendar URL
            calendar_name: Name of calendar
            start_date: Start date
            end_date: End date
            events: List of CalendarEvent objects to cache
        """
        cache_key = self._get_cache_key(url, calendar_name, start_date, end_date)
        cache_file = self.cache_dir / f"{cache_key}.json"

        # Serialize events
        events_data = []
        for event in events:
            events_data.append({
                'date': event.date,
                'name': event.name,
                'datetime': event.datetime.isoformat(),
                'duration_hours': event.duration_hours
            })

        data = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'calendar_name': calendar_name,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'events': events_data
        }

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Fail silently but log warning
            console.print(f"  [yellow]⚠[/yellow] Advarsel: Kunne ikke cache kalenderdata: {e}", style="yellow")

    def clear(self) -> None:
        """Clear all cached calendar data."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception:
                pass
