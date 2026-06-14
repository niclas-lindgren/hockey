from datetime import date
import json

from tournament_scheduler.models import SeasonPlan, Team, Tournament
from tournament_scheduler.cli.rvv_cli import main as rvv_main
from tournament_scheduler.pipeline.manual_adjustment_workflow import ManualAdjustmentWorkflow
from tournament_scheduler.pipeline.stage3_helpers import _plan_to_dict
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus
from tournament_scheduler.season_planner import SeasonPlanner


def _make_plan() -> SeasonPlan:
    t1_teams = [
        Team(club="Jar", label="Jar 1", age_group="U10"),
        Team(club="Skien", label="Skien 1", age_group="U10"),
    ]
    t2_teams = [
        Team(club="Jar", label="Jar 1", age_group="U10"),
        Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
    ]

    t1 = Tournament(
        id="pin12345",
        date=date(2027, 1, 16),
        arena="Jarhallen",
        age_group="U10",
        host_club="Jar",
        teams=t1_teams,
        games=SeasonPlanner.generate_round_robin_games(t1_teams, 1),
    )
    t2 = Tournament(
        id="move1234",
        date=date(2027, 1, 23),
        arena="Skien ishall",
        age_group="U10",
        host_club="Skien",
        teams=t2_teams,
        games=SeasonPlanner.generate_round_robin_games(t2_teams, 1),
    )
    plan = SeasonPlan(
        tournaments=[t1, t2],
        start_date=date(2027, 1, 1),
        end_date=date(2027, 3, 31),
        manual_adjustments={
            "locked_dates": ["2027-01-16"],
            "banned_dates": ["2027-01-23"],
            "forced_host_clubs": ["Jar"],
            "excluded_host_clubs": ["Skien"],
            "pinned_tournament_ids": ["pin12345"],
        },
    )
    return plan


def _write_state(tmp_path):
    work_dir = tmp_path / "pipeline"
    state = PipelineState(work_dir)

    input_file = tmp_path / "input.json"
    input_file.write_text(
        json.dumps(
            {
                "start_date": "2027-01-01",
                "end_date": "2027-03-31",
                "age_groups": ["U10"],
                "parallel_games": {"U10": 1},
                "round_length_minutes": {"U10": 10},
                "teams": [
                    {"club": "Jar", "label": "Jar 1", "age_group": "U10"},
                    {"club": "Skien", "label": "Skien 1", "age_group": "U10"},
                    {"club": "Kongsberg", "label": "Kongsberg 1", "age_group": "U10"},
                ],
            }
        ),
        encoding="utf-8",
    )
    state.write_stage(
        StageName.CONFIG,
        {
            "input_path": str(input_file),
            "teams": [
                {"club": "Jar", "label": "Jar 1", "age_group": "U10"},
                {"club": "Skien", "label": "Skien 1", "age_group": "U10"},
                {"club": "Kongsberg", "label": "Kongsberg 1", "age_group": "U10"},
            ],
            "round_length_minutes": {"U10": 10},
        },
        status=StageStatus.DONE,
    )

    plan = _make_plan()
    state.write_stage(
        StageName.PLANNING,
        {"plan": _plan_to_dict(plan), "rules_report": []},
        status=StageStatus.DONE,
    )
    return state, plan


def test_manual_adjustment_workflow_moves_banned_dates_and_updates_host(tmp_path):
    state, plan = _write_state(tmp_path)
    workflow = ManualAdjustmentWorkflow(state)

    result = workflow.apply(plan)

    assert result.success is True
    assert result.operation == "manual_adjustment"
    assert len(result.changes["moved"]) == 1
    assert len(result.changes["host_changes"]) == 1
    assert plan.tournaments[0].date == date(2027, 1, 16)
    assert plan.tournaments[0].host_club == "Jar"
    assert plan.tournaments[1].date != date(2027, 1, 23)
    assert plan.tournaments[1].host_club == "Jar"
    assert plan.tournaments[1].arena == "Jarhallen"
    assert plan.fairness_gate["status"] in {"pass", "warn", "fail"}
    assert result.conflicts == []
    assert plan.manual_adjustments["pinned_tournament_ids"] == ["pin12345"]


def test_adjust_cli_runs_end_to_end(tmp_path):
    state, _plan = _write_state(tmp_path)
    export_dir = tmp_path / "export"

    code = rvv_main(
        [
            "adjust",
            "--work-dir",
            str(state.work_dir),
            "--export-dir",
            str(export_dir),
            "--lock-date",
            "2027-01-16",
            "--ban-date",
            "2027-01-23",
            "--pin-tournament",
            "pin12345",
            "--force-host-club",
            "Jar",
            "--exclude-host-club",
            "Skien",
        ]
    )

    assert code == 0
    assert (export_dir / "season_plan.xlsx").exists()
    assert (export_dir / "season_plan.html").exists()
    assert (export_dir / "season_plan_report.html").exists()
