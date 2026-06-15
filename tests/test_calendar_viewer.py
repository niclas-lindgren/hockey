"""Tests for the scraped calendars HTML viewer."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tournament_scheduler.pipeline.calendar_viewer import generate_html


def _write_cache(tmp_path: Path, source_name: str) -> None:
    cache_dir = tmp_path / ".pipeline" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat()
    cache = {
        "_meta": {
            "updated_at": now,
            "ttl_hours": 6,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        },
        "source_count": 1,
        "total_events": 1,
        "sources": {
            source_name: {
                "name": source_name,
                "url": "https://example.com/calendar",
                "scrape_timestamp": now,
                "ttl_hours": 6,
                "event_count": 1,
                "blocked": False,
                "events": [
                    {
                        "date": "01.01.2025",
                        "name": "Trening",
                        "datetime": "2025-01-01T12:00:00",
                        "duration_hours": 1,
                    }
                ],
            }
        },
    }
    (cache_dir / "scraped_data.json").write_text(json.dumps(cache), encoding="utf-8")


class TestCalendarViewer:
    def test_generate_html_keeps_long_club_names_visible(self, tmp_path):
        source_name = "Sandefjord Penguins and Development Academy for Long Calendar Names"
        _write_cache(tmp_path, source_name)

        html_path = Path(generate_html(work_dir=str(tmp_path / ".pipeline"), export_dir=str(tmp_path / "export")))
        html = html_path.read_text(encoding="utf-8")

        assert source_name in html
        assert "width: 320px; min-width: 320px;" in html
        assert "align-items: flex-start;" in html
        club_label_block = html.split(".club-label {", 1)[1].split(".club-stats", 1)[0]
        assert "white-space: normal; overflow: visible; text-overflow: clip;" in club_label_block
        assert "overflow-wrap: anywhere;" in club_label_block
        assert "text-overflow: ellipsis" not in club_label_block
        assert "white-space: nowrap" not in club_label_block
