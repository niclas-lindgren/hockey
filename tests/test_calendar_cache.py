from __future__ import annotations

from pathlib import Path

from tournament_scheduler.utils.calendar_cache import CalendarCache


class TestCalendarCachePaths:
    def test_default_cache_dir_is_project_local(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        cache = CalendarCache()

        assert cache.cache_dir == Path(".pipeline") / "cache" / "calendars"
        assert cache.cache_dir.exists()

    def test_work_dir_places_cache_under_pipeline_root(self, tmp_path):
        work_dir = tmp_path / "custom-work"

        cache = CalendarCache(work_dir=str(work_dir))

        assert cache.cache_dir == work_dir / "cache" / "calendars"
        assert cache.cache_dir.exists()
