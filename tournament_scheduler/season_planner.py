"""Season planning / optimization engine.

`SeasonPlanner` now acts as a small orchestration facade around focused
helper modules for participant selection, host assignment, fairness
scoring, game generation, warning scans, and the rules report.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Set, Tuple

from tournament_scheduler.fairness_model import SeasonFairnessModel
from tournament_scheduler.game_generation import (
    arena_counts as _arena_counts,
    best_round_subset as _best_round_subset,
    diversity_score as _diversity_score,
    generate_round_robin_games as _generate_round_robin_games,
    month_balance_score as _month_balance_score,
    pairwise_matchup_score as _pairwise_matchup_score,
    rebalance_rounds as _rebalance_rounds,
)
from tournament_scheduler.fairness_scoring import build_fairness_gate as _build_fairness_gate
from tournament_scheduler.host_assignment import (
    assign_hosts as _assign_hosts,
    default_target_count as _default_target_count,
    find_slot_for_tournament as _find_slot_for_tournament,
    hosting_targets_for_age_group as _hosting_targets_for_age_group,
    proportional_integer_targets as _proportional_integer_targets,
)
from tournament_scheduler.models import (
    AGE_GROUP_OVERLAP,
    CalendarEvent,
    DatePreference,
    Game,
    Roster,
    SeasonPlan,
    Team,
    Tournament,
    overlapping_age_groups,
    team_key,
)
from tournament_scheduler.club_registry import club_for_arena as _club_for_arena
from tournament_scheduler.participant_selection import (
    age_group_deficit_spread as _age_group_deficit_spread,
    cap_per_club_deficit_aware as _cap_per_club_deficit_aware,
    deficit_score as _deficit_score,
    expected_average_for as _expected_average_for,
    max_club_teams_for as _max_club_teams_for,
    max_teams_for as _max_teams_for,
    normalized_invite_count as _normalized_invite_count,
    next_age_group as _next_age_group,
    participant_limit_for as _participant_limit_for,
    pick_least_recently_grouped as _pick_least_recently_grouped,
    pick_spread_dates as _pick_spread_dates,
    select_participants as _select_participants,
    target_tournaments_for_age_group as _target_tournaments_for_age_group,
)
from tournament_scheduler.rules_report import rules_report as _rules_report
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.season_config import DEFAULT_PARALLEL_GAMES
from tournament_scheduler.utils.slot_finder import matchday_duration_minutes
from tournament_scheduler.warnings import (
    compute_game_counts as _compute_game_counts,
    hosting_fairness_breakdown as _hosting_fairness_breakdown,
    scan_club_load_warnings as _scan_club_load_warnings,
    scan_feasibility_warnings as _scan_feasibility_warnings,
    scan_game_count_warnings as _scan_game_count_warnings,
    scan_hosting_warnings as _scan_hosting_warnings,
    scan_month_load_warnings as _scan_month_load_warnings,
    scan_per_team_share_warnings as _scan_per_team_share_warnings,
)


DEFAULT_TARGET_TOURNAMENT_COUNT = 6
MIN_TEAMS_PER_TOURNAMENT = 3
DEFAULT_TOURNAMENT_START_TIME = "10:00"
ARENA_DAY_SEQUENCE_BUFFER_MINUTES = 5
DEFAULT_FAIRNESS_THRESHOLDS = {
    "max_game_count_spread": 2,
    "max_hosting_deviation": 1,
    "max_team_travel_km": 700,
    "min_diversity_score": 0.75,
    "min_pairwise_matchup_score": 0.25,
    "min_month_balance_score": 0.75,
    "max_same_weekend_club_load": 3,
}


class SeasonPlanner:
    """Greedy season-plan builder on top of `TournamentScheduler`."""

    def __init__(
        self,
        scheduler: TournamentScheduler,
        roster: Roster,
        club_arenas: Dict[str, str],
        parallel_games_for_age_group: Optional[Dict[str, int]] = None,
        round_length_for_age_group: Optional[Dict[str, int]] = None,
        target_tournament_count: Optional[int] = None,
        max_club_teams_per_tournament: int = 1,
        deficit_cap_expansion: int = 1,
        max_game_count_spread: int = 2,
        max_early_finish_gap_days: int = 60,
        division_skill_band: int = 2,
        max_hosting_deviation: int = 1,
        max_hosting_days_per_month: int = 2,
        max_month_deviation_ratio: float = 0.5,
        events_by_club: Optional[Dict[str, List[CalendarEvent]]] = None,
        fairness_thresholds: Optional[Dict[str, float]] = None,
        fairness_model: Optional[SeasonFairnessModel] = None,
        date_preferences: Optional[List[DatePreference]] = None,
        preferanse_vekt_by_age_group: Optional[Dict[str, float]] = None,
        seed: Optional[int] = None,
    ):
        self.scheduler = scheduler
        self.roster = roster
        self.club_arenas = club_arenas
        self.parallel_games_for_age_group = parallel_games_for_age_group or {}
        self.round_length_for_age_group = round_length_for_age_group or {}
        self.target_tournament_count = target_tournament_count
        self.max_club_teams_per_tournament = max_club_teams_per_tournament
        self.deficit_cap_expansion = deficit_cap_expansion
        self.max_game_count_spread = max_game_count_spread
        self.max_early_finish_gap_days = max_early_finish_gap_days
        self.division_skill_band = division_skill_band
        self.max_hosting_deviation = max_hosting_deviation
        self.max_hosting_days_per_month = max_hosting_days_per_month

        duplicate_labels = {
            label for label, count in Counter(team.label for team in roster.teams).items() if count > 1
        }
        self._team_skill_levels: Dict[str, int] = {
            team_key(team, duplicate_labels): team.skill_level
            for team in roster.teams
            if team.skill_level is not None
        }
        self._duplicate_team_labels = duplicate_labels
        self._club_load_warnings: List[Tuple[str, str, str, int]] = []
        self._hosting_warnings: List[str] = []
        self._game_count_warnings: List[Tuple[str, int, int, str]] = []
        self._grouped_with: Dict[str, Set[str]] = {}
        self._team_game_counts: Dict[str, int] = {}
        self._running_game_counts: Dict[str, int] = {}
        self._club_cap_overrides: int = 0
        self._team_last_date: Dict[str, date] = {}
        self._invite_counts: Dict[str, int] = {self._team_key(team): 0 for team in roster.teams}
        club_age_group_counts: Dict[Tuple[str, str], int] = {}
        for team in roster.teams:
            key = (team.club, team.age_group)
            club_age_group_counts[key] = club_age_group_counts.get(key, 0) + 1
        self._club_age_group_team_counts: Dict[str, int] = {
            self._team_key(team): club_age_group_counts[(team.club, team.age_group)]
            for team in roster.teams
        }
        self._opponent_history: Dict[frozenset, int] = {}
        self._month_counts: Dict[Tuple[int, int], int] = {}
        self._month_load_warnings: List[Tuple[int, int, int, float, float]] = []
        self._per_team_share_warnings: List[Tuple[str, str, str, int, float]] = []
        self._feasibility_warnings: List[str] = []
        self._tournament_participations: Dict[str, int] = {self._team_key(team): 0 for team in roster.teams}

        self.max_month_deviation_ratio = max_month_deviation_ratio
        self.events_by_club = events_by_club or {}
        self.fairness_thresholds = dict(DEFAULT_FAIRNESS_THRESHOLDS)
        if fairness_thresholds:
            self.fairness_thresholds.update(fairness_thresholds)
        self.fairness_model = fairness_model or SeasonFairnessModel()
        self._fallback_host_substitutions: List[Tuple[date, str, str, str]] = []
        self.date_preferences: List[DatePreference] = date_preferences or []
        self.preferanse_vekt_by_age_group: Dict[str, float] = preferanse_vekt_by_age_group or {}
        self._rng: random.Random = random.Random(seed)

    def _team_target_tournament_count(self, team: Team) -> int:
        return team.target_tournament_count or (self.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT)

    def _team_at_target(self, team: Team) -> bool:
        key = self._team_key(team)
        return self._tournament_participations.get(key, 0) >= self._team_target_tournament_count(team)

    def _team_key(self, team: Team) -> str:
        return team_key(team, self._duplicate_team_labels)

    def build_plan(self, start_date: datetime, end_date: datetime) -> SeasonPlan:
        scheduling_result = self.scheduler.find_available_dates(start_date, end_date)
        free_dates = sorted(scheduling_result.available_dates)

        plan = SeasonPlan(tournaments=[], start_date=start_date.date(), end_date=end_date.date())

        age_groups = self.roster.age_groups()
        if not age_groups:
            return plan

        self._rng.shuffle(age_groups)

        scheduled: List[Tuple[date, str]] = []
        planned_age_groups_by_date: Dict[date, List[str]] = {}
        for age_group in age_groups:
            target_count = self._target_tournaments_for_age_group(age_group)
            chosen_dates = self._pick_spread_dates(
                free_dates,
                start_date.date(),
                end_date.date(),
                [age_group],
                planned_age_groups_by_date,
                target_count=target_count,
            )
            for tournament_date in chosen_dates:
                scheduled.append((tournament_date, age_group))
                planned_age_groups_by_date.setdefault(tournament_date, []).append(age_group)
                self._record_month(tournament_date)

        self._month_counts = {}
        scheduled.sort(key=lambda item: (item[0], item[1]))
        host_assignments = self._assign_hosts(scheduled)
        collisions: List[Tuple[date, str, str]] = []
        self._fallback_host_substitutions = []

        scheduled_age_groups_by_date: Dict[date, List[str]] = {}
        for (tournament_date, age_group), host_club in zip(scheduled, host_assignments):
            self._record_month(tournament_date)
            collision = self._check_overlap_collision(tournament_date, age_group, scheduled_age_groups_by_date)
            if collision:
                collisions.append((tournament_date, age_group, collision))
            scheduled_age_groups_by_date.setdefault(tournament_date, []).append(age_group)

            arena = self.club_arenas.get(host_club, host_club)
            participants = self._select_participants(age_group)

            # Reorder participants so the host club's team is first.
            # The home team in every generated game is participants[0], so
            # placing the arena-owning club at index 0 ensures correct home
            # team assignment regardless of selection order.
            home_club = _club_for_arena(arena) or host_club
            host_teams = [t for t in participants if t.club == home_club]
            other_teams = [t for t in participants if t.club != home_club]
            if host_teams:
                participants = host_teams + other_teams

            if len(participants) < MIN_TEAMS_PER_TOURNAMENT:
                plan.skipped_age_groups.append(
                    {
                        "age_group": age_group,
                        "team_count": len(participants),
                        "reason": f"Kun {len(participants)} lag konfigurert; minimum er {MIN_TEAMS_PER_TOURNAMENT}",
                    }
                )
                continue

            self._record_grouping(participants)
            parallel_games = self._parallel_games_for(age_group)
            games = self.generate_round_robin_games(participants, parallel_games)
            self._record_opponent_history(games)

            start_time = DEFAULT_TOURNAMENT_START_TIME
            slot = self._find_slot_for_tournament(tournament_date, host_club, age_group, games)
            if slot is not None:
                _slot_host_club, slot_start, _slot_end = slot
                start_time = slot_start

            ag_weight = self.preferanse_vekt_by_age_group.get(age_group, 0.0)
            date_pref_total = sum(
                p.vekt for p in self.date_preferences if p.fra <= tournament_date <= p.til
            )
            plan.tournaments.append(
                Tournament(
                    date=tournament_date,
                    arena=arena,
                    age_group=age_group,
                    teams=participants,
                    games=games,
                    host_club=host_club,
                    start_time=start_time,
                    preferanse_vekt=ag_weight,
                    scoring_weight_term=ag_weight + date_pref_total,
                )
            )

        expected_per_month = self._expected_monthly_load(start_date.date(), end_date.date(), len(scheduled))
        self._sequence_same_arena_day_start_times(plan)

        plan.arena_counts = self._arena_counts(plan.tournaments)
        plan.diversity_score = self._diversity_score(plan.tournaments)
        plan.pairwise_matchup_score = self._pairwise_matchup_score(plan.tournaments)
        plan.month_balance_score = self._month_balance_score(expected_per_month)
        plan.arena_day_collisions = []
        plan.arena_counts.pop("_arena_day_collisions", None)
        if self.date_preferences:
            plan.date_preference_weights = [
                {"fra": p.fra.isoformat(), "til": p.til.isoformat(), "vekt": p.vekt}
                for p in self.date_preferences
            ]

        self._compute_game_counts(plan.tournaments)
        skipped_age_groups_set = {entry["age_group"] for entry in plan.skipped_age_groups}
        public_team_game_counts: Dict[str, int] = {}
        public_team_last_dates: Dict[str, date] = {}
        for team in self.roster.teams:
            if team.age_group in skipped_age_groups_set:
                continue
            key = self._team_key(team)
            public_key = team_key(team, self._duplicate_team_labels)
            public_team_game_counts[public_key] = public_team_game_counts.get(public_key, 0) + self._team_game_counts.get(key, 0)
            last = self._team_last_date.get(key)
            if last is not None and (public_key not in public_team_last_dates or last > public_team_last_dates[public_key]):
                public_team_last_dates[public_key] = last
        plan.team_game_counts = public_team_game_counts
        plan.team_last_game_dates = public_team_last_dates
        if public_team_game_counts:
            plan.game_count_spread = max(public_team_game_counts.values()) - min(public_team_game_counts.values())

        plan.fairness_gate = self._build_fairness_gate(plan)
        self._scan_club_load_warnings(plan.tournaments)
        self._scan_hosting_warnings(plan)
        self._scan_game_count_warnings(plan.start_date, plan.end_date)
        self._scan_per_team_share_warnings(skipped_age_groups=plan.skipped_age_groups)
        self._scan_month_load_warnings(expected_per_month, plan.start_date)
        self._scan_feasibility_warnings(free_dates)

        if collisions:
            plan.arena_counts["_age_group_overlap_collisions"] = len(collisions)
            self._collisions = collisions
        else:
            self._collisions = []

        return plan

    @property
    def collisions(self) -> List[Tuple[date, str, str]]:
        return getattr(self, "_collisions", [])

    @property
    def fallback_host_substitutions(self) -> List[Tuple[date, str, str, str]]:
        return getattr(self, "_fallback_host_substitutions", [])

    @property
    def club_load_warnings(self) -> List[Tuple[str, str, str, int]]:
        return list(self._club_load_warnings)

    @property
    def hosting_warnings(self) -> List[str]:
        return list(self._hosting_warnings)

    @property
    def game_count_warnings(self) -> List[Tuple[str, int, int, str]]:
        return list(self._game_count_warnings)

    @property
    def per_team_share_warnings(self) -> List[Tuple[str, str, str, int, float]]:
        return list(self._per_team_share_warnings)

    @property
    def club_cap_overrides(self) -> int:
        return self._club_cap_overrides

    @property
    def feasibility_warnings(self) -> List[str]:
        return list(self._feasibility_warnings)

    @property
    def month_load_warnings(self) -> List[Tuple[int, int, int, float, float]]:
        return list(self._month_load_warnings)

    def _sequence_same_arena_day_start_times(self, plan: SeasonPlan) -> None:
        groups: Dict[Tuple[date, str], List[Tournament]] = {}
        for tournament in plan.tournaments:
            if tournament.cancelled:
                continue
            groups.setdefault((tournament.date, tournament.arena), []).append(tournament)

        for (_tournament_date, _arena), tournaments in groups.items():
            if len(tournaments) < 2:
                continue

            ordered = sorted(
                tournaments,
                key=lambda t: (t.start_time or DEFAULT_TOURNAMENT_START_TIME, t.age_group, t.id),
            )
            cursor_minutes: Optional[int] = None
            for tournament in ordered:
                start_time = tournament.start_time or DEFAULT_TOURNAMENT_START_TIME
                try:
                    requested = datetime.strptime(start_time, "%H:%M")
                    requested_minutes = requested.hour * 60 + requested.minute
                except ValueError:
                    requested_minutes = 10 * 60

                if cursor_minutes is None:
                    cursor_minutes = requested_minutes
                else:
                    cursor_minutes = max(cursor_minutes, requested_minutes)

                tournament.start_time = f"{cursor_minutes // 60:02d}:{cursor_minutes % 60:02d}"

                round_length = self.round_length_for_age_group.get(tournament.age_group)
                duration_minutes = (
                    matchday_duration_minutes(round_length, max(g.round_number for g in tournament.games))
                    if round_length and tournament.games
                    else 0
                )
                cursor_minutes += duration_minutes + ARENA_DAY_SEQUENCE_BUFFER_MINUTES

    @staticmethod
    def _expected_monthly_load(window_start: date, window_end: date, tournament_count: int) -> float:
        if tournament_count <= 0:
            return 0.0
        months_spanned = (window_end.year - window_start.year) * 12 + (window_end.month - window_start.month) + 1
        return tournament_count / max(1, months_spanned)

    def _record_month(self, tournament_date: date) -> None:
        key = (tournament_date.year, tournament_date.month)
        self._month_counts[key] = self._month_counts.get(key, 0) + 1

    def _score_candidate_date(
        self,
        candidate_date: date,
        age_group: str,
        candidate_participants: Sequence[Team],
        expected_per_month: float,
        tournament_weight: float = 0.0,
        date_preferences: Optional[List[DatePreference]] = None,
    ) -> float:
        repeat_penalty = 0.0
        participants = list(candidate_participants)
        if len(participants) >= 2:
            pair_count = 0
            repeat_total = 0
            for i, team_a in enumerate(participants):
                for team_b in participants[i + 1 :]:
                    pair = frozenset((self._team_key(team_a), self._team_key(team_b)))
                    repeat_total += self._opponent_history.get(pair, 0)
                    pair_count += 1
            if pair_count:
                repeat_penalty = repeat_total / pair_count

        month_penalty = max(0.0, self.month_load_ratio(candidate_date, expected_per_month) - 1.0)

        # Compute the subjective weight term (positive = penalise, negative = reward).
        # Cap magnitude to 2x the larger organic penalty so weights influence but
        # cannot completely override structural constraints.
        prefs = date_preferences if date_preferences is not None else self.date_preferences
        date_pref_total = sum(
            p.vekt for p in prefs if p.fra <= candidate_date <= p.til
        )
        raw_weight = tournament_weight + date_pref_total
        cap = max(abs(repeat_penalty), abs(month_penalty)) * 2
        if cap > 0.0:
            if raw_weight > cap:
                raw_weight = cap
            elif raw_weight < -cap:
                raw_weight = -cap

        return repeat_penalty + month_penalty + raw_weight

    def month_load_ratio(self, tournament_date: date, expected_per_month: float) -> float:
        if expected_per_month <= 0:
            return 0.0
        key = (tournament_date.year, tournament_date.month)
        return self._month_counts.get(key, 0) / expected_per_month

    def _parallel_games_for(self, age_group: str) -> int:
        return max(1, self.parallel_games_for_age_group.get(age_group, DEFAULT_PARALLEL_GAMES))

    def _check_overlap_collision(
        self,
        tournament_date: date,
        age_group: str,
        scheduled_by_date: Dict[date, List[str]],
    ) -> Optional[str]:
        for existing in scheduled_by_date.get(tournament_date, []):
            if age_group in overlapping_age_groups(existing) or existing in overlapping_age_groups(age_group):
                return existing
        return None

    def _record_grouping(self, participants: Sequence[Team]) -> None:
        labels = [self._team_key(team) for team in participants]
        games_added = max(0, len(participants) - 1)
        for team in participants:
            key = self._team_key(team)
            self._invite_counts[key] = self._invite_counts.get(key, 0) + 1
            self._tournament_participations[key] = self._tournament_participations.get(key, 0) + 1
            grouped = self._grouped_with.setdefault(key, set())
            grouped.update(label for label in labels if label != key)
            self._running_game_counts[key] = self._running_game_counts.get(key, 0) + games_added

    def _record_opponent_history(self, games: Sequence[Game]) -> None:
        for game in games:
            if game.home is None or game.away is None:
                continue
            pair = frozenset((self._team_key(game.home), self._team_key(game.away)))
            self._opponent_history[pair] = self._opponent_history.get(pair, 0) + 1


SeasonPlanner._pick_spread_dates = _pick_spread_dates
SeasonPlanner._target_tournaments_for_age_group = _target_tournaments_for_age_group
SeasonPlanner._assign_hosts = _assign_hosts
SeasonPlanner._find_slot_for_tournament = _find_slot_for_tournament
SeasonPlanner._next_age_group = _next_age_group
SeasonPlanner._select_participants = _select_participants
SeasonPlanner._cap_per_club_deficit_aware = _cap_per_club_deficit_aware
SeasonPlanner._participant_limit_for = _participant_limit_for
SeasonPlanner._max_teams_for = _max_teams_for
SeasonPlanner._max_club_teams_for = _max_club_teams_for
SeasonPlanner._age_group_deficit_spread = _age_group_deficit_spread
SeasonPlanner._expected_average_for = _expected_average_for
SeasonPlanner._deficit_score = _deficit_score
SeasonPlanner._normalized_invite_count = _normalized_invite_count
SeasonPlanner._pick_least_recently_grouped = _pick_least_recently_grouped
SeasonPlanner._hosting_targets_for_age_group = _hosting_targets_for_age_group
SeasonPlanner._proportional_integer_targets = staticmethod(_proportional_integer_targets)
SeasonPlanner._default_target_count = staticmethod(_default_target_count)
SeasonPlanner._build_fairness_gate = _build_fairness_gate
SeasonPlanner._compute_game_counts = _compute_game_counts
SeasonPlanner._scan_game_count_warnings = _scan_game_count_warnings
SeasonPlanner._scan_per_team_share_warnings = _scan_per_team_share_warnings
SeasonPlanner._scan_feasibility_warnings = _scan_feasibility_warnings
SeasonPlanner._scan_month_load_warnings = _scan_month_load_warnings
SeasonPlanner._scan_club_load_warnings = _scan_club_load_warnings
SeasonPlanner._hosting_fairness_breakdown = _hosting_fairness_breakdown
SeasonPlanner._scan_hosting_warnings = _scan_hosting_warnings
SeasonPlanner.generate_round_robin_games = staticmethod(_generate_round_robin_games)
SeasonPlanner._rebalance_rounds = staticmethod(_rebalance_rounds)
SeasonPlanner._best_round_subset = staticmethod(_best_round_subset)
SeasonPlanner._arena_counts = staticmethod(_arena_counts)
SeasonPlanner._diversity_score = _diversity_score
SeasonPlanner._pairwise_matchup_score = _pairwise_matchup_score
SeasonPlanner._month_balance_score = _month_balance_score
SeasonPlanner.rules_report = _rules_report
SeasonPlanner.DEFAULT_TOURNAMENT_START_TIME = DEFAULT_TOURNAMENT_START_TIME
SeasonPlanner.ARENA_DAY_SEQUENCE_BUFFER_MINUTES = ARENA_DAY_SEQUENCE_BUFFER_MINUTES
