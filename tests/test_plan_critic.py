"""Unit tests for tournament_scheduler.cli.plan_critic.generate_critic_summary."""
from __future__ import annotations

from datetime import date

import pytest

from tournament_scheduler.cli.plan_critic import generate_critic_summary
from tournament_scheduler.models import SeasonPlan, Tournament, Team


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tournament(
    host_club: str,
    year: int,
    month: int,
    day: int,
    age_group: str = "U10",
) -> Tournament:
    """Construct a minimal Tournament for testing."""
    return Tournament(
        date=date(year, month, day),
        arena=f"{host_club} arena",
        age_group=age_group,
        host_club=host_club,
    )


def _make_plan(**kwargs) -> SeasonPlan:
    """Build a SeasonPlan with sensible defaults, overrideable via kwargs."""
    defaults: dict = {
        "tournaments": [],
        "team_game_counts": {},
        "game_count_spread": 0,
        "month_balance_score": 1.0,
        "fairness_gate": {},
        "arena_day_collisions": [],
    }
    defaults.update(kwargs)
    return SeasonPlan(**defaults)


# ---------------------------------------------------------------------------
# Happy path: no issues
# ---------------------------------------------------------------------------


def test_no_issues_returns_empty_list():
    plan = _make_plan()
    result = generate_critic_summary(plan)
    assert result == []


def test_no_issues_balanced_plan():
    tournaments = [
        _make_tournament("Kongsberg", 2027, 1, 15),
        _make_tournament("Ringerike", 2027, 2, 12),
        _make_tournament("Skien", 2027, 3, 19),
    ]
    plan = _make_plan(
        tournaments=tournaments,
        team_game_counts={"Jar 1": 6, "Holmen 1": 6},
        game_count_spread=0,
        month_balance_score=0.95,
        fairness_gate={"status": "pass", "metrics": []},
        arena_day_collisions=[],
    )
    result = generate_critic_summary(plan)
    assert result == []


# ---------------------------------------------------------------------------
# Hosting clump detection
# ---------------------------------------------------------------------------


def test_hosting_clump_detected():
    """3 tournaments by same club in same month should trigger an issue."""
    tournaments = [
        _make_tournament("Kongsberg", 2027, 3, 5),
        _make_tournament("Kongsberg", 2027, 3, 12),
        _make_tournament("Kongsberg", 2027, 3, 19),
    ]
    plan = _make_plan(tournaments=tournaments)
    result = generate_critic_summary(plan)
    assert len(result) >= 1
    assert any("Kongsberg" in issue and "3" in issue for issue in result)


def test_hosting_clump_exactly_two_is_ok():
    """Exactly 2 tournaments by same club in same month is fine."""
    tournaments = [
        _make_tournament("Kongsberg", 2027, 3, 5),
        _make_tournament("Kongsberg", 2027, 3, 12),
    ]
    plan = _make_plan(tournaments=tournaments)
    result = generate_critic_summary(plan)
    clump_issues = [i for i in result if "Kongsberg" in i and "hosts" in i]
    assert clump_issues == []


def test_cancelled_tournaments_excluded_from_clump():
    """Cancelled tournaments must not count toward hosting clumps."""
    t1 = _make_tournament("Kongsberg", 2027, 3, 5)
    t2 = _make_tournament("Kongsberg", 2027, 3, 12)
    t3 = _make_tournament("Kongsberg", 2027, 3, 19)
    t3.cancelled = True
    plan = _make_plan(tournaments=[t1, t2, t3])
    result = generate_critic_summary(plan)
    clump_issues = [i for i in result if "Kongsberg" in i and "hosts" in i]
    assert clump_issues == []


# ---------------------------------------------------------------------------
# Game count outlier detection
# ---------------------------------------------------------------------------


def test_game_count_outlier_detected():
    """Spread > 4 should trigger an outlier issue."""
    plan = _make_plan(
        team_game_counts={"Jar 1": 12, "Holmen 1": 6},
        game_count_spread=6,
    )
    result = generate_critic_summary(plan)
    assert len(result) >= 1
    assert any("spread" in issue.lower() or "game" in issue.lower() for issue in result)


def test_game_count_spread_of_four_is_ok():
    """Spread == 4 is at the boundary and should NOT trigger an issue."""
    plan = _make_plan(
        team_game_counts={"Jar 1": 10, "Holmen 1": 6},
        game_count_spread=4,
    )
    result = generate_critic_summary(plan)
    outlier_issues = [i for i in result if "spread" in i.lower() or "redistribute" in i.lower()]
    assert outlier_issues == []


# ---------------------------------------------------------------------------
# Fairness gate
# ---------------------------------------------------------------------------


def test_fairness_gate_fail_detected():
    """A 'fail' metric in fairness_gate should produce a fail issue."""
    gate = {
        "status": "fail",
        "metrics": [
            {
                "status": "fail",
                "label": "Travel distance",
                "value": 250,
                "threshold": 200,
                "detail": "Max travel exceeds threshold",
            }
        ],
    }
    plan = _make_plan(fairness_gate=gate)
    result = generate_critic_summary(plan)
    assert len(result) >= 1
    assert any("FAIL" in issue or "fail" in issue.lower() for issue in result)


def test_fairness_gate_warn_detected():
    """A 'warn' metric should produce a warning issue."""
    gate = {
        "status": "warn",
        "metrics": [
            {
                "status": "warn",
                "label": "Home/away balance",
                "value": 0.55,
                "threshold": 0.6,
                "detail": "",
            }
        ],
    }
    plan = _make_plan(fairness_gate=gate)
    result = generate_critic_summary(plan)
    assert len(result) >= 1
    assert any("warning" in issue.lower() or "warn" in issue.lower() for issue in result)


def test_fairness_gate_pass_no_issue():
    """Pass status with all-pass metrics should produce no issue."""
    gate = {
        "status": "pass",
        "metrics": [
            {"status": "pass", "label": "Travel distance", "value": 100, "threshold": 200, "detail": ""},
        ],
    }
    plan = _make_plan(fairness_gate=gate)
    result = generate_critic_summary(plan)
    assert result == []


# ---------------------------------------------------------------------------
# Arena-day collision detection
# ---------------------------------------------------------------------------


def test_arena_day_collision_detected():
    """Non-empty arena_day_collisions should produce a collision issue."""
    collisions = [
        {"date": "2027-03-12", "arena": "Kongsberg", "age_group": "U10"},
        {"date": "2027-03-12", "arena": "Kongsberg", "age_group": "U12"},
    ]
    plan = _make_plan(arena_day_collisions=collisions)
    result = generate_critic_summary(plan)
    assert len(result) >= 1
    assert any("collision" in issue.lower() or "2" in issue for issue in result)


def test_no_arena_day_collisions_no_issue():
    plan = _make_plan(arena_day_collisions=[])
    result = generate_critic_summary(plan)
    assert result == []


# ---------------------------------------------------------------------------
# Month balance
# ---------------------------------------------------------------------------


def test_low_month_balance_detected():
    plan = _make_plan(month_balance_score=0.4)
    result = generate_critic_summary(plan)
    assert len(result) >= 1
    assert any("0.40" in issue or "unevenly" in issue.lower() for issue in result)


def test_month_balance_at_threshold_ok():
    """score == 0.6 is right at the limit — should NOT trigger an issue."""
    plan = _make_plan(month_balance_score=0.6)
    result = generate_critic_summary(plan)
    balance_issues = [i for i in result if "balance" in i.lower() or "unevenly" in i.lower()]
    assert balance_issues == []


# ---------------------------------------------------------------------------
# Result is capped at 5
# ---------------------------------------------------------------------------


def test_result_never_exceeds_5():
    """Even with every detector firing, at most 5 issues are returned."""
    tournaments = [
        _make_tournament("Kongsberg", 2027, 3, 5),
        _make_tournament("Kongsberg", 2027, 3, 12),
        _make_tournament("Kongsberg", 2027, 3, 19),
        _make_tournament("Ringerike", 2027, 4, 9),
        _make_tournament("Ringerike", 2027, 4, 16),
        _make_tournament("Ringerike", 2027, 4, 23),
    ]
    gate = {
        "status": "fail",
        "metrics": [
            {"status": "fail", "label": "M1", "value": 1, "threshold": 0, "detail": "d1"},
            {"status": "fail", "label": "M2", "value": 2, "threshold": 0, "detail": "d2"},
            {"status": "warn", "label": "M3", "value": 3, "threshold": 2, "detail": "d3"},
        ],
    }
    collisions = [{"date": "2027-03-12", "arena": "Kongsberg", "age_group": "U10"}]
    plan = _make_plan(
        tournaments=tournaments,
        team_game_counts={"A": 15, "B": 5},
        game_count_spread=10,
        month_balance_score=0.3,
        fairness_gate=gate,
        arena_day_collisions=collisions,
    )
    result = generate_critic_summary(plan)
    assert len(result) <= 5
