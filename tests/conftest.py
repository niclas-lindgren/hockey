import pytest

from tournament_scheduler.testing.canonical_input import (
    build_canonical_planner,
    load_canonical_input_data,
    load_canonical_roster,
    load_canonical_season_window,
)


@pytest.fixture
def canonical_input_data():
    return load_canonical_input_data()


@pytest.fixture
def canonical_roster():
    return load_canonical_roster()


@pytest.fixture
def canonical_season_window():
    return load_canonical_season_window()


@pytest.fixture
def canonical_planner():
    planner, start, end = build_canonical_planner()
    return planner, start, end


@pytest.fixture
def canonical_plan(canonical_planner):
    planner, start, end = canonical_planner
    plan = getattr(planner, "_canonical_plan", None)
    if plan is None:
        plan = planner.build_plan(start, end)
    return planner, plan, start, end
