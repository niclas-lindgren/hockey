"""Tests for the standalone activity calendar page (issue #33)."""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl

from tournament_scheduler.pipeline.activity_viewer import generate_activity_artifacts, generate_html


def _write_activity_workbook(path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.active.title = "Innstillinger"
    ws = wb.create_sheet("Aktiviteter")
    ws.append(["Måned", "Dato", "Aktivitet", "Sted"])
    ws.append(["Januar", 17, "Spillerutvikling JU14", "Sandefjord"])
    ws.append(["Mars", 3, "Klubbforum U13/U14", "Kongsberg"])
    wb.save(path)


class TestActivityViewer:
    def test_generate_activity_artifacts_writes_json_and_standalone_page(self, tmp_path):
        input_path = tmp_path / "input.xlsx"
        _write_activity_workbook(input_path)

        artifacts = generate_activity_artifacts(
            input_path=str(input_path),
            export_dir=str(tmp_path / "export"),
            default_year=2026,
            generated_at="2026-07-29T12:00:00Z",
        )

        assert artifacts is not None
        json_path = Path(artifacts["activities_json"])
        html_path = Path(artifacts["activities_html"])
        assert json_path.name == "activities.json"
        assert html_path.as_posix().endswith("activities/index.html")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["activities"][0]["date"] == "2026-01-17"
        html = html_path.read_text(encoding="utf-8")
        assert "Aktivitetskalender for Region Viken Vest" in html
        assert "../activities.json" in html
        assert "SheetJS" not in html
        assert "xlsx" not in html.lower()

    def test_generate_activity_artifacts_returns_none_without_activity_sheet(self, tmp_path):
        input_path = tmp_path / "input.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "Innstillinger"
        wb.save(input_path)

        assert generate_activity_artifacts(input_path=str(input_path), export_dir=str(tmp_path / "export")) is None

    def test_page_contains_view_switch_filter_and_accessible_details(self, tmp_path):
        html_path = Path(generate_html(export_dir=str(tmp_path / "export")))
        html = html_path.read_text(encoding="utf-8")

        assert "Årshjul" in html
        assert "Liste" in html
        assert "Aldersgruppe" in html
        assert 'id="ageFilter"' in html
        assert 'aria-live="polite"' in html
        assert "setAttribute('role', 'button')" in html
        assert "addEventListener('keydown'" in html
        assert "showDetails(activity)" in html

    def test_page_positions_year_wheel_markers_by_actual_date(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "function dayOfYear(date)" in html
        assert "function dateToAngle(iso, year)" in html
        assert "daysInYear(targetYear)" in html
        assert "Math.cos(angle)" in html
        assert "Math.sin(angle)" in html

    def test_page_has_chronological_list_mobile_default_and_iframe_height_message(self, tmp_path):
        html = Path(generate_html(export_dir=str(tmp_path / "export"))).read_text(encoding="utf-8")

        assert "month-group" in html
        assert "activity-list" in html
        assert "matchMedia('(max-width: 760px)')" in html
        assert "mobile-default" in html
        assert "rvv-activities-height" in html
        assert "postMessage" in html
        assert "overflow-x: hidden" in html
