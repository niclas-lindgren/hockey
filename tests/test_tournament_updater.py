"""Tests for tournament update and rescheduling (backlog item 23).

Covers:
  1. Dropping a team from a 6-team tournament regenerates correct round-robin games
  2. Dropping a non-existent team returns a non-success result with a clear message
  3. Moving a date without conflict checkers produces a success result (no conflicts found)
  4. Cascading move — moving tournament A to tournament B's date swaps the two dates
"""

from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tournament_scheduler.models import SeasonPlan, Tournament, Team, Game
from tournament_scheduler.pipeline.state import PipelineState, StageName, StageStatus
from tournament_scheduler.pipeline.tournament_updater import TournamentUpdater, UpdateResult
from tournament_scheduler.pipeline.stage3_planning import _plan_to_dict
from tournament_scheduler.season_planner import SeasonPlanner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def six_team_tournament() -> Tournament:
    """A 6-team U10 tournament with round-robin games (distinct clubs)."""
    teams = [
        Team(club="Jar", label="Jar 1", age_group="U10"),
        Team(club="Holmen", label="Holmen 1", age_group="U10"),
        Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
        Team(club="Ringerike", label="Ringerike 1", age_group="U10"),
        Team(club="Skien", label="Skien 1", age_group="U10"),
        Team(club="Tønsberg", label="Tønsberg 1", age_group="U10"),
    ]
    t = Tournament(
        date=date(2027, 1, 16),
        arena="Jarhallen",
        age_group="U10",
        host_club="Jar",
        teams=teams,
    )
    t.games = SeasonPlanner.generate_round_robin_games(teams, parallel_games=2)
    return t


@pytest.fixture
def two_tournament_plan() -> tuple[SeasonPlan, Tournament, Tournament]:
    """A plan with two tournaments on different dates (used for cascade test)."""
    teams_a = [
        Team(club="Jar", label="Jar 1", age_group="U10"),
        Team(club="Kongsberg", label="Kongsberg 1", age_group="U10"),
        Team(club="Skien", label="Skien 1", age_group="U10"),
    ]
    teams_b = [
        Team(club="Jar", label="Jar 2", age_group="U10"),
        Team(club="Ringerike", label="Ringerike 1", age_group="U10"),
        Team(club="Tønsberg", label="Tønsberg 1", age_group="U10"),
    ]
    t1 = Tournament(
        date=date(2027, 1, 16),
        arena="Jarhallen",
        age_group="U10",
        host_club="Jar",
        teams=teams_a,
        games=SeasonPlanner.generate_round_robin_games(teams_a, 2),
    )
    t2 = Tournament(
        date=date(2027, 2, 20),
        arena="Ringerikshallen",
        age_group="U11",
        host_club="Ringerike",
        teams=teams_b,
        games=SeasonPlanner.generate_round_robin_games(teams_b, 2),
    )
    plan = SeasonPlan(tournaments=[t1, t2], start_date=date(2027, 1, 1), end_date=date(2027, 4, 30))
    return plan, t1, t2


def make_state_with_plan(plan: SeasonPlan, tmp_path: Any) -> PipelineState:
    """Write a SeasonPlan to a temp pipeline checkpoint and return the state."""
    state = PipelineState(str(tmp_path / "pipeline"))
    plan_dict = {
        "plan": _plan_to_dict(plan),
        "llm_confidence": 0.0,
        "llm_reasoning": "",
        "attempts": 1,
        "llm_skipped": True,
    }
    state.write_stage(StageName.PLANNING, plan_dict, status=StageStatus.DONE)
    return state


# ---------------------------------------------------------------------------
# Test 1: Drop a team — 6 teams → 5 teams, correct round-robin
# ---------------------------------------------------------------------------


class TestDropTeam:
    def test_drop_team_regenerates_games(self, six_team_tournament: Tournament, tmp_path: Any):
        """Dropping one team from a 6-team tournament should produce 5-team round-robin."""
        plan = SeasonPlan(tournaments=[six_team_tournament])
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id

        result = updater.drop_team(tid, "Jar 1", plan=plan)

        assert result.success is True, f"Drop failed: {result.summary_nb}"
        assert result.operation == "team_drop"

        # Check the tournament in the plan (modified in-place)
        tournament = plan.tournaments[0]
        assert len(tournament.teams) == 5
        assert "Jar 1" not in {t.label for t in tournament.teams}

        # A 5-team round-robin with 2 parallel games should produce 10 games
        # (5 teams → 5 rounds × 2 games per round = 10 games, minus 0 byes since 5 is odd)
        # Actually: 5 teams → circle method with 6 slots (1 bye), 5 rounds, 2 games per round = 10
        assert len(tournament.games) == 10, f"Expected 10 games, got {len(tournament.games)}"

        # Verify it's a full round-robin — every pair of teams plays exactly once
        from collections import Counter
        pair_counts: Counter = Counter()
        for game in tournament.games:
            pair = frozenset((game.home.label, game.away.label))
            pair_counts[pair] += 1

        # With 5 teams, there are C(5,2) = 10 possible pairings; each should appear once
        assert len(pair_counts) == 10, f"Expected 10 unique pairings, got {len(pair_counts)}"
        for pair, count in pair_counts.items():
            assert count == 1, f"Pair {pair} appears {count} times (expected 1)"

    def test_drop_nonexistent_team_returns_error(
        self, six_team_tournament: Tournament, tmp_path: Any
    ):
        """Dropping a team that doesn't exist should return a non-success result."""
        plan = SeasonPlan(tournaments=[six_team_tournament])
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id

        result = updater.drop_team(tid, "NonExistentTeam", plan=plan)

        assert result.success is False
        assert "ble ikke funnet" in result.summary_nb.lower() or "ikke funnet" in result.summary_nb.lower()

    def test_drop_last_two_teams_returns_error(
        self, six_team_tournament: Tournament, tmp_path: Any
    ):
        """Dropping enough teams that only 1 remains should be rejected."""
        plan = SeasonPlan(tournaments=[six_team_tournament])
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id

        # First drop 4 teams (6 → 2)
        for label in ["Jar 1", "Holmen 1", "Kongsberg 1", "Ringerike 1"]:
            result = updater.drop_team(tid, label, plan=plan)
            assert result.success is True

        # Now try to drop one more (2 → 1) — should fail
        result = updater.drop_team(tid, "Skien 1", plan=plan)
        assert result.success is False
        assert "kun" in result.summary_nb.lower() or "minst" in result.summary_nb.lower()


# ---------------------------------------------------------------------------
# Test 2: Date move
# ---------------------------------------------------------------------------


class TestMoveDate:
    def test_move_date_no_conflicts(self, six_team_tournament: Tournament, tmp_path: Any):
        """Moving a tournament to a new date without conflict checkers succeeds."""
        plan = SeasonPlan(
            tournaments=[six_team_tournament],
            start_date=date(2027, 1, 1),
            end_date=date(2027, 4, 30),
        )
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id
        new_date = date(2027, 2, 13)

        result = updater.move_date(tid, new_date, plan=plan)

        assert result.success is True, f"Move failed: {result.summary_nb}"
        assert result.operation == "date_move"
        assert plan.tournaments[0].date == new_date

    def test_move_date_to_non_weekend_reports_conflict(
        self, six_team_tournament: Tournament, tmp_path: Any
    ):
        """Moving to a Wednesday flags a non-weekend conflict."""
        plan = SeasonPlan(
            tournaments=[six_team_tournament],
            start_date=date(2027, 1, 1),
            end_date=date(2027, 4, 30),
        )
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id
        wednesday = date(2027, 1, 20)  # A Wednesday
        assert wednesday.weekday() == 2

        # Without force, conflict should block the move
        result = updater.move_date(tid, wednesday, plan=plan, force=False)
        assert result.success is False
        assert "helgedag" in result.summary_nb.lower() or "ikke en" in result.summary_nb.lower()

        # With force, the move should succeed despite the conflict
        result = updater.move_date(tid, wednesday, plan=plan, force=True)
        assert result.success is True
        assert plan.tournaments[0].date == wednesday

    def test_move_date_with_force_ignores_conflicts(
        self, six_team_tournament: Tournament, tmp_path: Any
    ):
        """With force=True, move succeeds even when the date has plan-internal conflicts."""
        # Create a plan with two tournaments on different dates
        team_a = [Team(club="Jar", label="Jar 1", age_group="U10")]
        team_b = [Team(club="Skien", label="Skien 1", age_group="U10")]
        t1 = Tournament(
            date=date(2027, 1, 16), arena="Jarhallen", age_group="U10",
            teams=team_a, games=SeasonPlanner.generate_round_robin_games(team_a, 1),
        )
        t2 = Tournament(
            date=date(2027, 2, 20), arena="Skien ishall", age_group="U11",
            teams=team_b, games=SeasonPlanner.generate_round_robin_games(team_b, 1),
        )
        plan = SeasonPlan(tournaments=[t1, t2], start_date=date(2027, 1, 1), end_date=date(2027, 4, 30))
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)

        # Move t1 to t2's date with force
        result = updater.move_date(t1.id, date(2027, 2, 20), plan=plan, force=False)
        assert result.success is False  # plan-internal conflict blocks
        assert "allerede" in result.summary_nb.lower()

        result = updater.move_date(t1.id, date(2027, 2, 20), plan=plan, force=True)
        assert result.success is True
        assert t1.date == date(2027, 2, 20)


# ---------------------------------------------------------------------------
# Test 3: Cascade move — swapping dates
# ---------------------------------------------------------------------------


class TestCascadeMove:
    def test_cascade_swap_dates(self, two_tournament_plan, tmp_path: Any):
        """Moving tournament A to tournament B's date should swap the dates."""
        plan, t1, t2 = two_tournament_plan
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)

        original_t1_date = t1.date
        original_t2_date = t2.date

        # Move t1 to t2's date with cascade=True
        result = updater.move_date(t1.id, t2.date, plan=plan, force=True, cascade=True)

        assert result.success is True
        # t1 should now be on t2's original date
        assert t1.date == original_t2_date, f"t1 should be on {original_t2_date}, got {t1.date}"
        # t2 (the displaced tournament) should now be on t1's original date
        assert t2.date == original_t1_date, f"t2 should be on {original_t1_date}, got {t2.date}"
        assert len(result.cascade) == 1
        assert result.cascade[0]["displaced_tournament_id"] == t2.id

    def test_cascade_no_swap_when_disabled(self, two_tournament_plan, tmp_path: Any):
        """With cascade=False, moving to an occupied date forces both onto the same date."""
        plan, t1, t2 = two_tournament_plan
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)

        original_t1_date = t1.date
        original_t2_date = t2.date

        result = updater.move_date(t1.id, t2.date, plan=plan, force=True, cascade=False)

        assert result.success is True
        # t1 moved to t2's date
        assert t1.date == original_t2_date
        # t2 should NOT have been moved (cascade=False)
        assert t2.date == original_t2_date
        assert len(result.cascade) == 0


# ---------------------------------------------------------------------------
# Test 4: Checkpoint write and read round-trip
# ---------------------------------------------------------------------------


class TestCheckpointRoundTrip:
    def test_write_and_read_updated_checkpoint(
        self, six_team_tournament: Tournament, tmp_path: Any
    ):
        """After a drop_team, writing the checkpoint and re-reading should preserve the change."""
        plan = SeasonPlan(tournaments=[six_team_tournament])
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id

        result = updater.drop_team(tid, "Jar 1", plan=plan)
        assert result.success is True

        # Write the updated checkpoint
        updater.write_updated_checkpoint(plan, log_entry=result)

        # Re-read from a fresh state
        state2 = PipelineState(state.work_dir)
        plan2 = updater.load_plan()

        assert len(plan2.tournaments) == 1
        assert len(plan2.tournaments[0].teams) == 5
        assert "Jar 1" not in {t.label for t in plan2.tournaments[0].teams}
        assert len(plan2.tournaments[0].games) == 10

    def test_log_update_writes_jsonl_entry(self, six_team_tournament: Tournament, tmp_path: Any):
        """log_update should append a JSONL entry to the pipeline logs directory."""
        plan = SeasonPlan(tournaments=[six_team_tournament])
        state = make_state_with_plan(plan, tmp_path)
        updater = TournamentUpdater(state=state)
        tid = six_team_tournament.id

        # First create a log entry
        result = updater.drop_team(tid, "Jar 1", plan=plan)
        log_path = updater.log_update(result)

        import json
        with open(log_path, "r", encoding="utf-8") as f:
            entry = json.loads(f.read())

        assert entry["type"] == "tournament_update"
        assert entry["tournament_id"] == tid
        assert entry["operation"] == "team_drop"
        assert entry["success"] is True
        assert "Jar 1" in entry.get("changes", {}).get("team_removed", "")
