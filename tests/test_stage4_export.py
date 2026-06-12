"""Tests for tournament_scheduler.pipeline.stage4_export."""

from datetime import date
from pathlib import Path
import re

import openpyxl
import pytest

from tournament_scheduler.models import Game, Roster, SeasonPlan, Team, Tournament
from tournament_scheduler.pipeline.stage4_export import Stage4Error, _dict_to_plan, run
from tournament_scheduler.pipeline.state import PipelineState, StageName


def _make_plan_dict():
    """Build a minimal but valid plan checkpoint dict."""
    t1 = {
        "date": "2025-10-05",
        "arena": "Kongsberghallen",
        "age_group": "U10",
        "host_club": "Kongsberg",
        "teams": [
            {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
            {"club": "Skien",     "label": "Skien U10A",     "age_group": "U10"},
        ],
        "games": [
            {"home": "Kongsberg U10A", "away": "Skien U10A", "parallel_slot": 0, "round_number": 3},
        ],
    }
    return {
        "plan": {
            "start_date": "2025-09-01",
            "end_date": "2025-12-01",
            "diversity_score": 1.0,
            "pairwise_matchup_score": 1.0,
            "month_balance_score": 1.0,
            "arena_counts": {"Kongsberghallen": 1},
            "tournaments": [t1],
        },
        "llm_confidence": 0.9,
        "llm_reasoning": "great",
        "attempts": 1,
        "llm_skipped": True,
    }


def _make_multi_age_group_plan_dict():
    data = _make_plan_dict()
    data["plan"]["tournaments"].append(
        {
            "date": "2025-11-02",
            "arena": "Bærum ishall",
            "age_group": "JU11",
            "host_club": "Jutul",
            "teams": [
                {"club": "Jutul", "label": "Jutul JU11A", "age_group": "JU11"},
                {"club": "Holmen", "label": "Holmen JU11A", "age_group": "JU11"},
            ],
            "games": [
                {"home": "Jutul JU11A", "away": "Holmen JU11A", "parallel_slot": 0, "round_number": 1},
            ],
        }
    )
    data["plan"]["arena_counts"]["Bærum ishall"] = 1
    return data


def _make_spond_plan_dict():
    data = _make_plan_dict()
    data["plan"]["tournaments"][0]["teams"] = [
        {"club": "Kongsberg", "label": "Kongsberg U10A", "age_group": "U10"},
        {"club": "Skien", "label": "Skien U10A", "age_group": "U10"},
        {"club": "Holmen", "label": "Holmen U10A", "age_group": "U10"},
    ]
    data["plan"]["tournaments"][0]["games"] = [
        {"home": "Kongsberg U10A", "away": "Skien U10A", "parallel_slot": 0, "round_number": 1},
        {"home": "Kongsberg U10A", "away": "Holmen U10A", "parallel_slot": 0, "round_number": 2},
        {"home": "Skien U10A", "away": "Holmen U10A", "parallel_slot": 0, "round_number": 3},
    ]
    return data


class TestDictToPlan:
    def test_round_trips_plan(self):
        plan_dict = _make_plan_dict()["plan"]
        plan = _dict_to_plan(plan_dict)
        assert isinstance(plan, SeasonPlan)
        assert len(plan.tournaments) == 1
        t = plan.tournaments[0]
        assert t.arena == "Kongsberghallen"
        assert len(t.games) == 1
        assert t.games[0].home.label == "Kongsberg U10A"
        assert t.games[0].round_number == 3

    def test_handles_missing_dates(self):
        plan_dict = {"tournaments": [], "diversity_score": 0.0,
                     "pairwise_matchup_score": 0.0, "month_balance_score": 0.0,
                     "arena_counts": {}}
        plan = _dict_to_plan(plan_dict)
        assert plan.start_date is None


class TestRunStage4:
    def test_produces_excel_file(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        assert "excel" in files
        assert Path(files["excel"]).exists()

    def test_generates_html_with_plan_driven_filters_and_ui_assets(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_multi_age_group_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        html_path = Path(files["html"])
        html = html_path.read_text(encoding="utf-8")

        assert '<option value="U10">U10</option>' in html
        assert '<option value="JU11">JU11</option>' in html
        assert re.search(r'Alle \((?:JU11 \+ U10|U10 \+ JU11)\)', html)
        assert 'id="themeToggle"' in html
        assert 'class="theme-toggle"' in html
        assert 'href="season_plan.xlsx"' in html
        assert 'href="season_plan.csv"' in html
        assert 'href="season_plan.ics"' in html
        assert 'href="season_plan.csv" class="export-link-btn"' in html or 'href="season_plan.csv"' in html
        assert 'debug-dashboard' not in html.lower()
        assert not re.search(r"[\U0001F300-\U0001FAFF]", html)

    def test_produces_ical_file(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        assert "ical" in files
        ics_path = Path(files["ical"])
        assert ics_path.exists()
        assert ics_path.suffix == ".ics"
        content = ics_path.read_text()
        assert "BEGIN:VCALENDAR" in content
        assert "VEVENT" in content

    def test_writes_timestamped_exports_and_flat_copies(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
            timestamped_export=True,
        )
        files = result.get("output_files", {})

        timestamped_paths = [Path(files[key]) for key in ("excel", "ical", "csv_games", "csv_overview", "html", "spond")]
        timestamp_dirs = {path.parent for path in timestamped_paths}
        assert len(timestamp_dirs) == 1
        timestamp_dir = timestamp_dirs.pop()
        assert timestamp_dir.parent == tmp_path / "export"
        assert timestamp_dir.name

        for path in timestamped_paths:
            assert path.exists()
            assert path.parent == timestamp_dir

        flat_paths = [Path(files[key]) for key in ("excel_flat", "ical_flat", "csv_games_flat", "csv_overview_flat", "html_flat", "spond_flat")]
        for path in flat_paths:
            assert path.exists()
            assert path.parent == tmp_path / "export"

    def test_stage4_spond_export_uses_tournament_rows(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_spond_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        workbook = openpyxl.load_workbook(files["spond"])
        sheet = workbook["Sesongplan"]
        rows = list(sheet.iter_rows(values_only=True))

        assert rows[0][0:5] == ("Dato", "Aktivitet", "Sted", "Start", "Slutt")
        assert rows[1][9] == "turnering"
        assert len(rows) == 2  # header + one tournament row, not one row per game

    def test_produces_csv_files(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        result = run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        files = result.get("output_files", {})
        assert "csv_games" in files
        assert "csv_overview" in files
        games_path = Path(files["csv_games"])
        assert games_path.exists()
        lines = games_path.read_text().splitlines()
        assert lines[0] == "date,arena,age_group,home,away,parallel_slot"
        assert len(lines) > 1  # header + at least one game row

    def test_marks_checkpoint_done(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        run(
            _make_plan_dict(), state,
            export_dir=str(tmp_path / "export"),
        )
        assert state.is_done(StageName.EXPORT)

    def test_raises_on_missing_plan(self, tmp_path):
        state = PipelineState(tmp_path / "pipeline")
        with pytest.raises(Stage4Error, match="Stage 3"):
            run({}, state, export_dir=str(tmp_path / "export"), strict=True)
