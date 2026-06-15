"""Season planning / optimization engine.

`SeasonPlanner` wraps `TournamentScheduler.find_available_dates` to obtain the
set of conflict-free weekend dates for a season window, then runs a greedy
assignment algorithm that:

  1. Picks 10-15 of those dates spread evenly across the season window.
  2. Assigns each chosen date/age-group combination to a host arena/club,
     ensuring every arena gets at least one hosted tournament before any
     arena hosts a second.
  3. Selects which teams participate in each tournament — every `Tournament`
     is single-age-group (one round-robin per tournament). When an age
     group's roster is small enough, every team is invited; otherwise a
     "least-recently-grouped-together" heuristic varies *which set of teams*
     gets invited together across the season.
  4. Cross-checks proposed dates against `AGE_GROUP_OVERLAP` and avoids
     scheduling overlapping age groups on the same weekend where a free
     alternative date exists; otherwise flags the collision in plan metadata.

The planner returns a `SeasonPlan` of `Tournament` objects without
per-tournament games — those are filled in later by the round-robin
generator.
"""

import math
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Set, Tuple

from tournament_scheduler.club_distances import compute_team_travel_distances
from tournament_scheduler.fairness_model import SeasonFairnessModel
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
    Game,
    Roster,
    SeasonPlan,
    Team,
    Tournament,
    overlapping_age_groups,
    team_key,
)
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
from tournament_scheduler.scheduler import TournamentScheduler
from tournament_scheduler.fairness_scoring import build_fairness_gate as _build_fairness_gate
from tournament_scheduler.game_generation import (
    arena_counts as _arena_counts,
    best_round_subset as _best_round_subset,
    diversity_score as _diversity_score,
    generate_round_robin_games as _generate_round_robin_games,
    month_balance_score as _month_balance_score,
    pairwise_matchup_score as _pairwise_matchup_score,
    rebalance_rounds as _rebalance_rounds,
)
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
from tournament_scheduler.season_config import DEFAULT_PARALLEL_GAMES


# Default target for how many tournaments each age group should receive.
DEFAULT_TARGET_TOURNAMENT_COUNT = 6

# A tournament needs at least three teams to be useful; two teams only
# produce a single match, which is better handled outside the season plan.
MIN_TEAMS_PER_TOURNAMENT = 3

# Default start time assigned to generated tournaments when no per-arena/
# per-age-group scheduling is available yet.
DEFAULT_TOURNAMENT_START_TIME = "09:00"

# Default thresholds for the roster-based fairness gate. These can be
# overridden via the planner constructor and (optionally) pipeline config.
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
        max_month_deviation_ratio: float = 0.5,
        events_by_club: Optional[Dict[str, List[CalendarEvent]]] = None,
        fairness_thresholds: Optional[Dict[str, float]] = None,
        fairness_model: Optional[SeasonFairnessModel] = None,
    ):
        """Initialize the planner.

        Args:
            scheduler: A configured `TournamentScheduler` used to find
                conflict-free weekend dates for the season window.
            roster: The manually-configured club/team roster for the season.
            club_arenas: Mapping of club/host name -> home arena name (e.g.
                from the club registry), used to assign tournament hosts.
            parallel_games_for_age_group: Optional mapping of age group ->
                configured parallel-games count, used to derive the
                tournament capacity for that age group. Falls back to the
                default parallel-games setting when not provided.
            round_length_for_age_group: Optional mapping of age group ->
                round length in minutes, used to set each generated
                tournament's `start_time` and compute its duration/end time.
            target_tournament_count: Optional override for the desired
                number of tournament participations per team (default:
                `DEFAULT_TARGET_TOURNAMENT_COUNT`).
            max_club_teams_per_tournament: Hard constraint on how many teams
                from the same club can be invited to a single tournament.
                Default 1 — at most one team per club per tournament unless
                the proportional allowance or other overrides permit more,
                which means same-club matchups can occur when needed.
            deficit_cap_expansion: Number of extra slots added to the
                proportional per-club cap in `_max_club_teams_for` when the
                deficit spread in the age group exceeds
                `max_game_count_spread`. Default 1 means at most one
                additional team from a deficit-heavy club can attend each
                tournament, accelerating catch-up for under-served sibling
                teams without drastically changing tournament composition.
            division_skill_band: Maximum skill-level difference treated as
                "adjacent" for the skill-division penalty in participant
                selection. Default 2 means levels 3 and 5 are adjacent but
                3 and 6 are not. Set to a large value (e.g. 99) to disable.
            max_month_deviation_ratio: A month is flagged as over- or
                under-loaded when its tournament count deviates more than
                this fraction from the expected seasonal average.
                Default 0.5 means >50% deviation triggers a warning.
            events_by_club: Optional mapping of club name -> calendar events
                (e.g. Stage 2's `events_by_club` checkpoint output), used for
                time-of-day-aware arena slot finding. When provided together
                with `round_length_for_age_group`, each tournament's
                `start_time` is derived from
                `TournamentScheduler.find_arena_slot_for_date` instead of
                always using `DEFAULT_TOURNAMENT_START_TIME`.
            fairness_thresholds: Optional mapping overriding the default
                roster-based fairness gate thresholds (e.g. max game count
                spread or minimum diversity score).
            fairness_model: Optional soft target model used for per-team
                fairness diagnostics. The default model nudges larger clubs
                slightly above the age-group average and smaller clubs
                slightly below it.
        """
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

        # Maps team label -> skill_level (int 1-10) for teams that have one.
        # Used by the skill-level proximity penalty in participant selection.
        duplicate_labels = {label for label, count in Counter(team.label for team in roster.teams).items() if count > 1}
        self._team_skill_levels: Dict[str, int] = {
            team_key(team, duplicate_labels): team.skill_level
            for team in roster.teams
            if team.skill_level is not None
        }
        self._duplicate_team_labels = duplicate_labels

        # Club-load warnings collected after build_plan runs.
        self._club_load_warnings: List[Tuple[str, str, str, int]] = []

        # Hosting-imbalance warnings collected after build_plan runs.
        self._hosting_warnings: List[str] = []

        # Game-count warnings collected after build_plan runs.
        self._game_count_warnings: List[Tuple[str, int, int, str]] = []

        # Tracks, per team, the set of other teams it has already been
        # grouped with in a tournament this season — used by the
        # least-recently-grouped-together heuristic.
        self._grouped_with: Dict[str, Set[str]] = {}
        # Tracks the total number of round-robin games each team has played
        # across all tournaments. Populated in _compute_game_counts after
        # build_plan generates all tournaments and their games.
        self._team_game_counts: Dict[str, int] = {}
        # Running estimate of each team's game count, updated incrementally
        # in _record_grouping as tournaments are scheduled (each team in a
        # tournament with N participants plays N-1 round-robin games).
        # Unlike `_team_game_counts` (only populated after build_plan
        # finishes), this is available *during* selection, so
        # `_deficit_score` can use it to identify under-served teams while
        # the season is still being built.
        self._running_game_counts: Dict[str, int] = {}
        # Counts how many times the deficit-aware override let a club
        # exceed its `_max_club_teams_for` allowance for a tournament,
        # because no under-cap candidate had as large a game-count deficit.
        # Surfaced alongside `per_team_share_warnings` so operators can
        # confirm same-club pairings beyond the proportional cap stay rare.
        self._club_cap_overrides: int = 0
        # Tracks the date of each team's most recent game. Used for
        # early-finish detection.
        self._team_last_date: Dict[str, date] = {}
        # Tracks how many times each team has been invited overall, to keep
        # invitations roughly balanced across the season.
        self._invite_counts: Dict[str, int] = {self._team_key(team): 0 for team in roster.teams}
        # Maps team label -> number of teams from the same club in the same
        # age group (including itself). Used to normalize invite counts so
        # that a club with many sibling teams in an age group (e.g. Jar
        # fielding 6 U10 teams) doesn't have each individual team starved of
        # invitations relative to a club with only one team in that age
        # group (e.g. Kongsberg's sole U10 team) — each team should get a
        # roughly similar number of games regardless of club size.
        club_age_group_counts: Dict[Tuple[str, str], int] = {}
        for team in roster.teams:
            key = (team.club, team.age_group)
            club_age_group_counts[key] = club_age_group_counts.get(key, 0) + 1
        self._club_age_group_team_counts: Dict[str, int] = {
            self._team_key(team): club_age_group_counts[(team.club, team.age_group)]
            for team in roster.teams
        }
        # Tracks, per unordered pair of teams (as a frozenset of labels),
        # how many times that pair has actually been scheduled to play each
        # other — distinct from `_grouped_with`, which only records mere
        # tournament co-attendance. Populated from the `Game`s produced by
        # `generate_round_robin_games`. Useful for a future
        # matchup-diversity heuristic that wants to know real opponent
        # history rather than just shared invitations.
        self._opponent_history: Dict[frozenset, int] = {}
        # Tracks how many tournaments have been scheduled in each
        # year-month (key: `(year, month)` tuple) of the season window —
        # used to spot months that are already carrying more than their
        # fair share of the season's tournament load.
        self._month_counts: Dict[Tuple[int, int], int] = {}
        # Month-load warnings collected after build_plan runs.
        self._month_load_warnings: List[Tuple[int, int, int, float, float]] = []

        # Per-team-share warnings collected after build_plan runs. Each
        # entry is `(team_label, club, age_group, actual_count,
        # expected_count)` for every team whose actual game count deviates
        # from the average for its age group by more than
        # `max_game_count_spread` — surfacing club/age-group skew
        # explicitly (e.g. a Jar U10 team under-invited relative to
        # Kongsberg's U10 team).
        self._per_team_share_warnings: List[Tuple[str, str, str, int, float]] = []

        # Feasibility warnings collected after build_plan runs. Each entry
        # is a human-readable Norwegian string explaining why an age group's
        # participation target could not reasonably be met (e.g. too few
        # free weekends for the desired per-team participation count).
        self._feasibility_warnings: List[str] = []

        # Per-team tournament participation count — how many tournaments
        # each team has been invited to (distinct from game counts, which
        # are tracked by `_running_game_counts`). Used to enforce per-team
        # target_tournament_count caps.
        self._tournament_participations: Dict[str, int] = {
            self._team_key(team): 0 for team in roster.teams
        }

        self.max_month_deviation_ratio = max_month_deviation_ratio
        self.events_by_club = events_by_club or {}
        self.fairness_thresholds = dict(DEFAULT_FAIRNESS_THRESHOLDS)
        if fairness_thresholds:
            self.fairness_thresholds.update(fairness_thresholds)
        self.fairness_model = fairness_model or SeasonFairnessModel()

        # Kept for compatibility with older reports/tests; the planner now
        # only books tournaments from the assigned host club's own calendar.
        self._fallback_host_substitutions: List[Tuple[date, str, str, str]] = []

    def _team_target_tournament_count(self, team: Team) -> int:
        """Return the tournament participation target for *team*.

        Returns the per-team override if set, otherwise the global default.
        """
        return team.target_tournament_count or (self.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT)

    def _team_at_target(self, team: Team) -> bool:
        """Return True if *team* has reached its tournament participation cap."""
        key = self._team_key(team)
        count = self._tournament_participations.get(key, 0)
        target = self._team_target_tournament_count(team)
        return count >= target

    def _team_key(self, team: Team) -> str:
        return team_key(team, self._duplicate_team_labels)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build_plan(self, start_date: datetime, end_date: datetime) -> SeasonPlan:
        """Build and return a `SeasonPlan` for the given season window."""
        scheduling_result = self.scheduler.find_available_dates(start_date, end_date)
        free_dates = sorted(scheduling_result.available_dates)

        plan = SeasonPlan(
            tournaments=[],
            start_date=start_date.date(),
            end_date=end_date.date(),
        )

        age_groups = self.roster.age_groups()
        if not age_groups:
            return plan

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

        # Reset month counters so the actual plan build repopulates them from
        # the finalized tournament list (the counters above were only used for
        # spread scoring while selecting dates for later age groups).
        self._month_counts = {}

        scheduled.sort(key=lambda item: (item[0], item[1]))
        host_assignments = self._assign_hosts(scheduled)
        collisions: List[Tuple[date, str, str]] = []
        self._fallback_host_substitutions = []

        scheduled_age_groups_by_date: Dict[date, List[str]] = {}

        for (tournament_date, age_group), host_club in zip(scheduled, host_assignments):
            self._record_month(tournament_date)

            collision = self._check_overlap_collision(
                tournament_date, age_group, scheduled_age_groups_by_date
            )
            if collision:
                collisions.append((tournament_date, age_group, collision))

            scheduled_age_groups_by_date.setdefault(tournament_date, []).append(age_group)

            arena = self.club_arenas.get(host_club, host_club)
            participants = self._select_participants(age_group)
            if len(participants) < MIN_TEAMS_PER_TOURNAMENT:
                plan.skipped_age_groups.append({
                    "age_group": age_group,
                    "team_count": len(participants),
                    "reason": f"Kun {len(participants)} lag konfigurert; minimum er {MIN_TEAMS_PER_TOURNAMENT}",
                })
                continue
            self._record_grouping(participants)

            parallel_games = self._parallel_games_for(age_group)
            games = self.generate_round_robin_games(participants, parallel_games)
            self._record_opponent_history(games)

            actual_host_club = host_club
            actual_arena = arena
            start_time = DEFAULT_TOURNAMENT_START_TIME

            slot = self._find_slot_for_tournament(
                tournament_date, host_club, age_group, games
            )
            if slot is not None:
                _slot_host_club, slot_start, _slot_end = slot
                start_time = slot_start

            tournament = Tournament(
                date=tournament_date,
                arena=actual_arena,
                age_group=age_group,
                teams=participants,
                games=games,
                host_club=actual_host_club,
                start_time=start_time,
            )
            plan.tournaments.append(tournament)

        expected_per_month = self._expected_monthly_load(
            start_date.date(), end_date.date(), len(scheduled)
        )

        plan.arena_counts = self._arena_counts(plan.tournaments)
        plan.diversity_score = self._diversity_score(plan.tournaments)
        plan.pairwise_matchup_score = self._pairwise_matchup_score(plan.tournaments)
        plan.month_balance_score = self._month_balance_score(expected_per_month)

        # Compute per-team game counts and last-game dates.
        self._compute_game_counts(plan.tournaments)
        # Build set of teams whose age group was skipped (fewer than
        # MIN_TEAMS_PER_TOURNAMENT teams) so they are excluded from
        # fairness metrics and game-count spread calculations.
        skipped_age_groups_set = {
            entry["age_group"] for entry in plan.skipped_age_groups
        }
        public_team_game_counts: Dict[str, int] = {}
        public_team_last_dates: Dict[str, date] = {}
        for team in self.roster.teams:
            if team.age_group in skipped_age_groups_set:
                continue
            key = self._team_key(team)
            public_team_game_counts[team.label] = public_team_game_counts.get(team.label, 0) + self._team_game_counts.get(key, 0)
            last = self._team_last_date.get(key)
            if last is not None and (team.label not in public_team_last_dates or last > public_team_last_dates[team.label]):
                public_team_last_dates[team.label] = last
        plan.team_game_counts = public_team_game_counts
        plan.team_last_game_dates = public_team_last_dates
        if public_team_game_counts:
            plan.game_count_spread = max(public_team_game_counts.values()) - min(public_team_game_counts.values())

        # Build the roster-based fairness gate from the final plan scores.
        plan.fairness_gate = self._build_fairness_gate(plan)

        # Scan for club-load violations and record warnings.
        self._scan_club_load_warnings(plan.tournaments)
        # Scan for hosting-imbalance warnings.
        self._scan_hosting_warnings(plan)
        # Scan for game-count spread violations and early-finish issues.
        self._scan_game_count_warnings(plan.start_date, plan.end_date)
        # Scan for per-club/per-age-group game-count share skew.
        self._scan_per_team_share_warnings(skipped_age_groups=plan.skipped_age_groups)
        # Scan for month-load imbalance warnings.
        self._scan_month_load_warnings(expected_per_month, plan.start_date)
        # Scan for feasibility warnings: age groups whose participation
        # target cannot reasonably be met with the available free dates.
        self._scan_feasibility_warnings(free_dates)

        if collisions:
            plan.arena_counts["_age_group_overlap_collisions"] = len(collisions)
            self._collisions = collisions
        else:
            self._collisions = []

        return plan

    @property
    def collisions(self) -> List[Tuple[date, str, str]]:
        """Age-group-overlap collisions that could not be avoided.

        Each entry is `(date, age_group, overlapping_age_group_already_on_that_date)`.
        Populated after `build_plan` runs.
        """
        return getattr(self, "_collisions", [])

    @property
    def fallback_host_substitutions(self) -> List[Tuple[date, str, str, str]]:
        """Fallback-host substitutions made during the most recent `build_plan` run.

        Each entry is `(date, age_group, original_host_club, fallback_host_club)`.
        A tournament's `_assign_hosts`-derived `host_club` is still counted
        toward the proportional hosting totals computed by `_assign_hosts`
        (hosting fairness is decided up front, before slot availability is
        known); this list records where the *actual* arena/host ended up
        differing from that assignment because the originally-assigned
        host's arena had no free slot of sufficient length on the chosen
        date.
        """
        return getattr(self, "_fallback_host_substitutions", [])

    def _find_slot_for_tournament(
        self,
        tournament_date: date,
        host_club: str,
        age_group: str,
        games: List[Game],
    ) -> Optional[Tuple[str, str, str]]:
        """Find a time-of-day slot in the host club's own calendar.

        Computes the required duration from `round_length_for_age_group` and
        the number of rounds in *games* (mirroring
        `Tournament.duration_minutes`), then delegates to
        `TournamentScheduler.find_arena_slot_for_date`.

        Returns `None` (leaving the caller to use
        `DEFAULT_TOURNAMENT_START_TIME` and the originally-assigned host)
        when no calendar data is available, no round length is configured
        for *age_group*, there are no games yet, or the host club has no
        fitting slot in its own hall.
        """
        if not self.events_by_club:
            return None

        round_length = self.round_length_for_age_group.get(age_group)
        if not round_length:
            return None

        if not games:
            return None

        max_round = max(g.round_number for g in games)
        required_minutes = round_length * max_round
        if required_minutes <= 0:
            return None

        return self.scheduler.find_arena_slot_for_date(
            tournament_date, host_club, required_minutes, self.events_by_club
        )

    @property
    def club_load_warnings(self) -> List[Tuple[str, str, str, int]]:
        """Club-load soft-constraint warnings after ``build_plan``.

        Each entry is ``(club_name, age_group, date_str, team_count)``
        for every tournament where the number of teams invited from a
        single club exceeds ``max_club_teams_per_tournament``.
        """
        return list(self._club_load_warnings)

    @property
    def hosting_warnings(self) -> List[str]:
        """Proportional-hosting warnings after ``build_plan``.

        Each entry is a human-readable message describing a club whose
        actual hosting count deviates from its proportional (by team
        count) target beyond ``max_hosting_deviation``.
        """
        return list(self._hosting_warnings)

    @property
    def game_count_warnings(self) -> List[Tuple[str, int, int, str]]:
        """Game-count spread and early-finish warnings after ``build_plan``.

        Each entry is ``(team_label, games_played, spread, warning_type)``
        where ``warning_type`` is one of:

        - ``"spread"`` — the team is on either the high or low extreme
          of the game-count spread, and the spread exceeds
          ``max_game_count_spread``.
        - ``"early_finish"`` — the team's last game is more than
          ``max_early_finish_gap_days`` before the season end date.
        """
        return list(self._game_count_warnings)

    @property
    def per_team_share_warnings(self) -> List[Tuple[str, str, str, int, float]]:
        """Per-team game-count-share warnings after ``build_plan``.

        Each entry is ``(team_label, club, age_group, actual_count,
        expected_count)`` for every team whose actual game count
        (``team_game_counts``) deviates from the soft fairness target for
        its age group by more than ``max_game_count_spread``.

        This complements ``game_count_warnings`` (which only flags the
        global high/low extremes) by surfacing club- and age-group-level
        skew explicitly — e.g. a club fielding many sibling teams in one age
        group whose teams are systematically under- or over-invited relative
        to other teams in the same age group.
        """
        return list(self._per_team_share_warnings)

    @property
    def club_cap_overrides(self) -> int:
        """Number of times the deficit-aware club-cap override fired.

        Counts how many times a team was selected for a tournament despite
        its club already having reached its `_max_club_teams_for(age_group,
        club)` allowance for that tournament — i.e. a same-club pairing
        beyond the proportional cap, allowed only because no under-cap
        candidate had as large a game-count deficit (`_deficit_score`).

        Read alongside `per_team_share_warnings`: a small value relative to
        the total number of tournaments confirms such overrides remain the
        exception, used only to reduce per-team game-count skew.
        """
        return self._club_cap_overrides

    @property
    def feasibility_warnings(self) -> List[str]:
        """Return human-readable Norwegian feasibility warnings.

        Each warning explains why an age group's desired participation
        target could not reasonably be met given available free dates.
        """
        return list(self._feasibility_warnings)

    @property
    def month_load_warnings(self) -> List[Tuple[int, int, int, float, float]]:
        """Month-load imbalance warnings after ``build_plan``.

        Each entry is ``(year, month, count, expected, deviation_ratio)``
        where ``deviation_ratio`` is (count - expected) / expected —
        positive for over-loaded months, negative for under-loaded months.

        Only months exceeding ``max_month_deviation_ratio`` are included.
        """
        return list(self._month_load_warnings)

    def _build_fairness_gate(self, plan: SeasonPlan) -> Dict[str, object]:
        """Return a structured pass/warn/fail summary for key fairness metrics."""
        thresholds = self.fairness_thresholds
        metrics: List[Dict[str, object]] = []

        def add_metric(
            key: str,
            label: str,
            value: float | int,
            threshold: float | int,
            *,
            direction: str,
            severity: str,
            detail: str,
            unit: str = "",
        ) -> None:
            if threshold is None:
                threshold_value = 0.0
            else:
                threshold_value = float(threshold)
            value_float = float(value)
            if direction == "max":
                within = value_float <= threshold_value
                if threshold_value <= 0:
                    score = 100 if value_float <= 0 else 0
                elif within:
                    score = 100
                else:
                    score = max(0, int(round(100 * max(0.0, 2 - (value_float / threshold_value)))))
            else:
                within = value_float >= threshold_value
                if threshold_value <= 0:
                    score = 100 if value_float > 0 else 0
                elif within:
                    score = 100
                else:
                    score = max(0, int(round(100 * max(0.0, value_float / threshold_value))))
            status = "pass" if within else ("fail" if severity == "fail" else "warn")
            metrics.append(
                {
                    "key": key,
                    "label": label,
                    "value": value,
                    "threshold": threshold,
                    "direction": direction,
                    "severity": severity,
                    "status": status,
                    "score": score,
                    "unit": unit,
                    "detail": detail,
                }
            )

        team_travel = compute_team_travel_distances(plan)
        max_team_travel = max(team_travel.values()) if team_travel else 0

        hosting_breakdown = self._hosting_fairness_breakdown(plan)
        hosting_deviation = float(hosting_breakdown.get("max_deviation", 0.0))
        hosting_detail = str(hosting_breakdown.get("detail", ""))

        same_weekend_load = 0
        weekend_loads: Dict[tuple[int, int], Dict[str, int]] = {}
        for tournament in plan.tournaments:
            iso_year, iso_week, _ = tournament.date.isocalendar()
            bucket = weekend_loads.setdefault((iso_year, iso_week), {})
            host_club = tournament.host_club or ""
            if host_club:
                bucket[host_club] = bucket.get(host_club, 0) + 1
        for loads in weekend_loads.values():
            if loads:
                same_weekend_load = max(same_weekend_load, max(loads.values()))
        weekend_detail = f"maks {same_weekend_load} turneringer fra samme klubb i samme uke"

        age_group_spreads: List[float] = []
        skipped_age_groups_set = {
            entry["age_group"] for entry in plan.skipped_age_groups
        }
        teams_by_age_group: Dict[str, List[Team]] = {}
        for team in self.roster.teams:
            teams_by_age_group.setdefault(team.age_group, []).append(team)
        for age_group, teams in teams_by_age_group.items():
            if age_group in skipped_age_groups_set:
                continue
            counts = [
                self._team_game_counts.get(self._team_key(team), 0)
                for team in teams
            ]
            if counts:
                average = sum(counts) / len(counts)
                spread = max(counts) - min(counts)
                # Normalize by average with a floor of 1 and cap at 1.0.
                # The ratio-based normalization (spread/average) can diverge
                # when averages are small early in planning; the floor and
                # cap keep the metric in a stable [0, 1] range regardless
                # of how few games have been played so far.
                normalized = spread / max(average, 1.0)
                age_group_spreads.append(min(normalized, 1.0))
        normalized_game_count_spread = max(age_group_spreads) if age_group_spreads else float(plan.game_count_spread)

        add_metric(
            "game_count_spread",
            "Kamper per lag",
            round(normalized_game_count_spread, 3),
            thresholds.get("max_game_count_spread", self.max_game_count_spread),
            direction="max",
            severity="fail",
            detail=f"Normalisert spredning per aldersgruppe er {normalized_game_count_spread:.3f} (rå spredning: {plan.game_count_spread} kamper, tak på [0, 1]).",

        )
        add_metric(
            "hosting_deviation",
            "Hjemmebanebelastning",
            hosting_deviation,
            thresholds.get("max_hosting_deviation", self.max_hosting_deviation),
            direction="max",
            severity="fail",
            detail=hosting_detail or "Aldersgruppevis vertskapsfordeling ligger innenfor terskelen.",
        )
        if metrics and metrics[-1].get("key") == "hosting_deviation":
            metrics[-1]["age_group_breakdown"] = hosting_breakdown.get("age_group_breakdown", [])
        add_metric(
            "travel_distance",
            "Reisebelastning",
            max_team_travel,
            thresholds.get("max_team_travel_km", DEFAULT_FAIRNESS_THRESHOLDS["max_team_travel_km"]),
            direction="max",
            severity="warn",
            detail=f"Lengst reisende lag har {max_team_travel} km total reise.",
            unit="km",
        )
        add_metric(
            "opponent_diversity",
            "Motstandervariasjon",
            plan.diversity_score,
            thresholds.get("min_diversity_score", DEFAULT_FAIRNESS_THRESHOLDS["min_diversity_score"]),
            direction="min",
            severity="warn",
            detail=f"Snittet av unik motstanderdekning er {plan.diversity_score:.3f}.",
        )
        add_metric(
            "pairwise_matchups",
            "Nye matchups",
            plan.pairwise_matchup_score,
            thresholds.get("min_pairwise_matchup_score", DEFAULT_FAIRNESS_THRESHOLDS["min_pairwise_matchup_score"]),
            direction="min",
            severity="warn",
            detail=f"Andel nye kampoppsett er {plan.pairwise_matchup_score:.3f}.",
        )
        add_metric(
            "month_balance",
            "Månedsbalanse",
            plan.month_balance_score,
            thresholds.get("min_month_balance_score", DEFAULT_FAIRNESS_THRESHOLDS["min_month_balance_score"]),
            direction="min",
            severity="warn",
            detail=f"Månedsbalansen er {plan.month_balance_score:.3f}.",
        )
        add_metric(
            "same_weekend_club_load",
            "Klubblast per helg",
            same_weekend_load,
            thresholds.get("max_same_weekend_club_load", DEFAULT_FAIRNESS_THRESHOLDS["max_same_weekend_club_load"]),
            direction="max",
            severity="warn",
            detail=weekend_detail,
        )

        statuses = [str(m["status"]) for m in metrics]
        if "fail" in statuses:
            overall_status = "fail"
        elif "warn" in statuses:
            overall_status = "warn"
        else:
            overall_status = "pass"
        overall_score = int(round(sum(float(m["score"]) for m in metrics) / len(metrics))) if metrics else 100
        return {
            "status": overall_status,
            "score": overall_score,
            "metrics": metrics,
            "thresholds": dict(thresholds),
        }

    def _compute_game_counts(self, tournaments: Sequence[Tournament]) -> None:
        """Compute per-team round-robin game counts and last-game dates.

        Walks every ``Game`` in every ``Tournament``, counting how many
        games each team plays overall and tracking the date of each team's
        most recent game. Results are stored in ``_team_game_counts`` and
        ``_team_last_date`` respectively.
        """
        self._team_game_counts = {}
        self._team_last_date = {}
        for tournament in tournaments:
            for game in tournament.games:
                for team in (game.home, game.away):
                    if team is None:
                        continue
                    key = self._team_key(team)
                    self._team_game_counts[key] = self._team_game_counts.get(key, 0) + 1
                    last = self._team_last_date.get(key)
                    if last is None or tournament.date > last:
                        self._team_last_date[key] = tournament.date

    def _scan_game_count_warnings(
        self,
        window_start: Optional[date],
        window_end: Optional[date],
    ) -> None:
        """Scan computed game counts for spread and early-finish violations.

        Appends structured warnings to ``_game_count_warnings``.

        - **Spread warnings**: when ``max(team_game_counts) - min(team_game_counts)``
          exceeds ``max_game_count_spread``, every team whose count is at
          either extreme gets flagged.
        - **Early-finish warnings**: when the season end date is known, teams
          whose last game is more than ``max_early_finish_gap_days`` before
          the end date are flagged.
        """
        self._game_count_warnings = []

        if not self._team_game_counts:
            return

        max_count = max(self._team_game_counts.values())
        min_count = min(self._team_game_counts.values())
        spread = max_count - min_count

        # Spread warnings
        if spread > self.max_game_count_spread:
            for key, count in self._team_game_counts.items():
                if count == max_count or count == min_count:
                    self._game_count_warnings.append((key, count, spread, "spread"))

        # Early-finish warnings
        if window_end is not None and self._team_last_date:
            for key, last_date in self._team_last_date.items():
                gap = (window_end - last_date).days
                if gap > self.max_early_finish_gap_days:
                    self._game_count_warnings.append(
                        (key, self._team_game_counts.get(key, 0), gap, "early_finish")
                    )

    def _scan_per_team_share_warnings(self, skipped_age_groups: Optional[List[Dict[str, object]]] = None) -> None:
        """Scan computed game counts for per-club/per-age-group skew.

        For each age group, computes a soft target game count for every
        team using ``self.fairness_model`` and then flags every team whose
        actual count deviates from that target by more than
        ``max_game_count_spread``. Appends
        ``(team_label, club, age_group, actual_count, expected_count)``
        tuples to ``_per_team_share_warnings``.

        This surfaces skew that ``_scan_game_count_warnings`` (global
        high/low extremes only) can miss — e.g. a club fielding many sibling
        teams in one age group being systematically under-invited relative
        to other teams in the same age group.

        Args:
            skipped_age_groups: Optional list of skipped-age-group entries
                (each with an ``age_group`` key). Teams in these age groups
                are excluded from share warnings.
        """
        self._per_team_share_warnings = []

        skipped_set: Set[str] = set()
        if skipped_age_groups:
            skipped_set = {entry["age_group"] for entry in skipped_age_groups}

        teams_by_age_group: Dict[str, List[Team]] = {}
        for team in self.roster.teams:
            if team.age_group in skipped_set:
                continue
            teams_by_age_group.setdefault(team.age_group, []).append(team)

        for age_group, teams in teams_by_age_group.items():
            if not teams:
                continue
            expected_by_team = self.fairness_model.targets_for_age_group(
                teams,
                self._team_game_counts,
            )
            for team in teams:
                key = self._team_key(team)
                actual = self._team_game_counts.get(key, 0)
                expected = expected_by_team.get(key, 0.0)
                if abs(actual - expected) > self.max_game_count_spread:
                    self._per_team_share_warnings.append(
                        (key, team.club, age_group, actual, expected)
                    )

    def _scan_feasibility_warnings(self, free_dates: Sequence[date]) -> None:
        """Check each age group's participation target against free-date capacity.

        When an age group has enough teams to form a tournament but the
        desired per-team participation target cannot reasonably be met
        given the number of available free weekends, emit a warning.
        """
        self._feasibility_warnings = []

        for age_group in self.roster.age_groups():
            teams = self.roster.by_age_group(age_group)
            if len(teams) < MIN_TEAMS_PER_TOURNAMENT:
                self._feasibility_warnings.append(
                    f"{age_group}: kun {len(teams)} lag — "
                    f"minimum {MIN_TEAMS_PER_TOURNAMENT} lag kreves for å arrangere turnering. "
                    f"Aldersgruppen hoppes over."
                )
                continue

            capacity = min(len(teams), self._max_teams_for(age_group))
            
            # Compute target tournament count from per-team targets summed
            total_target = sum(
                (t.target_tournament_count or self.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT)
                for t in teams
            )
            target_count = max(1, math.ceil(total_target / capacity))
            
            # Show the range of per-team targets in the warning message
            targets = [
                t.target_tournament_count or self.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT
                for t in teams
            ]
            min_target = min(targets)
            max_target = max(targets)

            # Rough feasibility: if the target tournament count for this
            # age group alone exceeds the total number of free dates,
            # the desired participation level is unrealistic.
            if target_count > len(free_dates):
                target_desc = f"{min_target}" if min_target == max_target else f"{min_target}–{max_target}"
                self._feasibility_warnings.append(
                    f"{age_group}: målet på ~{target_desc} deltakelser per lag "
                    f"({target_count} turneringer) kan neppe nås — det er bare "
                    f"{len(free_dates)} ledige helger i sesongvinduet. "
                    f"Planleggeren justerer ned automatisk."
                )

    def _scan_month_load_warnings(
        self,
        expected_per_month: float,
        start_date: Optional[date],
    ) -> None:
        """Scan month counts for over/under-loaded months.

        Appends ``(year, month, count, expected, deviation)`` tuples to
        ``_month_load_warnings`` for every month whose tournament count
        deviates more than ``max_month_deviation_ratio`` from the
        seasonal average.
        """
        self._month_load_warnings = []
        if expected_per_month <= 0 or not self._month_counts:
            return

        # Only check months that are within the season window.
        if start_date is None:
            return

        from calendar import monthrange

        end_month = 4  # April — season ends Apr 30
        for (year, month), count in sorted(self._month_counts.items()):
            # Skip months outside the Oct–Apr window.
            # October = 10, November = 11, December = 12,
            # January = 1, February = 2, March = 3, April = 4.
            if not ((month >= 10) or (month <= end_month)):
                continue

            deviation = (count - expected_per_month) / expected_per_month
            if abs(deviation) > self.max_month_deviation_ratio:
                self._month_load_warnings.append(
                    (year, month, count, expected_per_month, deviation)
                )

    def _scan_club_load_warnings(self, tournaments: Sequence[Tournament]) -> None:
        """Scan completed tournaments for club-load violations.

        Appends structured warnings to ``_club_load_warnings`` for every
        tournament where a club has more teams participating than its
        per-club allowance (`_max_club_teams_for`).  This should never fire
        now that the constraint is hard (``_pick_least_recently_grouped``
        and ``_select_participants`` both enforce it), but is retained as a
        defensive check.
        """
        for t in tournaments:
            club_counts: Dict[str, int] = {}
            for team in t.teams:
                club_counts[team.club] = club_counts.get(team.club, 0) + 1
            for club, count in club_counts.items():
                max_club = self._max_club_teams_for(t.age_group, club)
                if count > max_club:
                    self._club_load_warnings.append(
                        (club, t.age_group, t.date.isoformat(), count)
                    )

    def _hosting_fairness_breakdown(self, plan: SeasonPlan) -> Dict[str, object]:
        """Return age-group-aware expected vs actual hosting diagnostics."""
        rows: List[Dict[str, object]] = []
        max_deviation = 0.0
        max_detail = ""
        tournaments_by_age: Dict[str, List[Tournament]] = {}
        for tournament in plan.tournaments:
            tournaments_by_age.setdefault(tournament.age_group, []).append(tournament)

        for age_group in sorted(tournaments_by_age):
            tournaments = tournaments_by_age[age_group]
            age_teams = self.roster.by_age_group(age_group)
            club_team_counts: Dict[str, int] = {}
            for team in age_teams:
                club_team_counts[team.club] = club_team_counts.get(team.club, 0) + 1
            total_age_teams = sum(club_team_counts.values()) or 1
            actual_hosting: Dict[str, int] = {}
            for tournament in tournaments:
                host = tournament.host_club
                if host:
                    actual_hosting[host] = actual_hosting.get(host, 0) + 1

            for club in sorted(set(club_team_counts) | set(actual_hosting)):
                team_count = club_team_counts.get(club, 0)
                expected = team_count / total_age_teams * len(tournaments) if team_count else 0.0
                actual = actual_hosting.get(club, 0)
                deviation = abs(actual - expected)
                row = {
                    "age_group": age_group,
                    "club": club,
                    "teams": team_count,
                    "actual": actual,
                    "expected": round(expected, 2),
                    "deviation": round(deviation, 2),
                    "tournaments": len(tournaments),
                }
                rows.append(row)
                if deviation >= max_deviation:
                    max_deviation = deviation
                    max_detail = (
                        f"{age_group}: {club} har {actual} hjemmeturnering(er), "
                        f"forventet ~{expected:.1f} basert på {team_count} lag i aldersgruppen."
                    )

        if rows:
            examples = "; ".join(
                f"{row['age_group']} {row['club']}: {row['actual']} vs ~{float(row['expected']):.1f}"
                for row in sorted(rows, key=lambda row: float(row["deviation"]), reverse=True)[:4]
            )
            detail = f"Aldersgruppevis vertskapsfordeling: {examples}. Størst avvik: {max_detail}"
        else:
            detail = "Ingen vertskapsdata å vurdere."
        return {
            "max_deviation": max_deviation,
            "detail": detail,
            "age_group_breakdown": rows,
        }

    def _scan_hosting_warnings(self, plan: SeasonPlan) -> None:
        """Scan hosting for age-group-aware proportional-imbalance violations."""
        if not plan.tournaments:
            return

        breakdown = self._hosting_fairness_breakdown(plan)
        for row in breakdown.get("age_group_breakdown", []):
            if not isinstance(row, dict):
                continue
            deviation = float(row.get("deviation", 0.0) or 0.0)
            if deviation > self.max_hosting_deviation:
                self._hosting_warnings.append(
                    f"{row.get('club')} har {row.get('actual')} hjemmeturnering(er) i {row.get('age_group')} "
                    f"(forventet ~{float(row.get('expected', 0.0)):.1f} basert på "
                    f"{row.get('teams')} lag i aldersgruppen, avvik {deviation:.1f} > "
                    f"{self.max_hosting_deviation})"
                )

    # ------------------------------------------------------------------
    # Rules report — transparent audit of all constraints and decisions
    # ------------------------------------------------------------------

    def rules_report(self) -> List[Dict[str, str]]:
        """Return a structured report of every constraint, rule, and
        automatic decision made by the scheduler, with Norwegian-language
        explanations.

        Each entry is a dict with keys ``regel`` (short rule name),
        ``forklaring`` (Norwegian rationale), and ``kategori`` (one of
        ``"Hard krav"``, ``"Automatisk avgjørelse"``, or ``"Anbefaling"``).
        """
        report: List[Dict[str, str]] = []

        # ------------------------------------------------------------------
        # Hard constraints — enforced at code level, cannot be violated.
        # ------------------------------------------------------------------

        report.append({
            "regel": f"Maks {self.max_club_teams_per_tournament} lag per klubb per turnering",
            "forklaring": (
                f"Høyst {self.max_club_teams_per_tournament} lag fra samme klubb kan delta "
                f"i én og samme turnering. Dette er et hardt krav som forhindrer "
                f"at to lag fra samme klubb møter hverandre — slike kamper er "
                f"uønsket fordi de ikke gir variasjon for spillerne."
            ),
            "kategori": "Hard krav",
        })

        # Federation-mandated parallel-games defaults.
        if self.parallel_games_for_age_group:
            for ag, pg in sorted(self.parallel_games_for_age_group.items()):
                capacity = self._max_teams_for(ag)
                report.append({
                    "regel": f"Parallelle kamper for {ag}: {pg}",
                    "forklaring": (
                        f"For aldersgruppen {ag} spilles det {pg} kamper samtidig "
                        f"per runde. Det gir plass til opptil {capacity} lag per "
                        f"turnering, og hvis lagetallet er oddetall får ett lag pause "
                        "i hver runde."
                    ),
                    "kategori": "Hard krav",
                })
        else:
            report.append({
                "regel": "Parallelle kamper: ingen spesifisert",
                "forklaring": (
                    "Ingen aldersgrupper har spesifisert antall parallelle kamper. "
                    f"Planleggeren bruker et standard nivå på {DEFAULT_PARALLEL_GAMES} parallelle kamper "
                    f"og kan dermed invitere opptil {DEFAULT_PARALLEL_GAMES * 2 + 1} lag per turnering."
                ),
                "kategori": "Hard krav",
            })


        # Skill-level divisions.
        report.append({
            "regel": f"Ferdighetsnivå-bånd: ±{self.division_skill_band}",
            "forklaring": (
                f"Lag med registrert ferdighetsnivå (1–10) grupperes med lag innenfor "
                f"±{self.division_skill_band} nivåer av hverandre. Dette motvirker "
                f"ensidige kamper og sikrer jevnere motstand. Lag uten registrert "
                f"nivå påvirkes ikke."
            ),
            "kategori": "Hard krav",
        })

        # ------------------------------------------------------------------
        # Automatic decisions — the algorithm chooses, but the rationale is
        # deterministic and explained here.
        # ------------------------------------------------------------------

        report.append({
            "regel": "Minst mulig gjentatte grupperinger",
            "forklaring": (
                "Når planleggeren velger hvilke lag som skal møtes i en turnering, "
                "prioriterer den lag som ikke har vært i samme turnering tidligere "
                "i sesongen. Målet er at hvert lag skal møte flest mulig forskjellige "
                "motstandere gjennom sesongen."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": f"Jevn fordeling av turneringer over sesongen",
            "forklaring": (
                f"Sesongvinduet deles i omtrent like store tidsbolker, og én "
                f"turnering legges til hver bolk. Dette sikrer at turneringene "
                f"er spredt jevnt utover og at ingen periode blir overbelastet. "
                f"Måneder som avviker mer enn {int(self.max_month_deviation_ratio * 100)}% "
                f"fra forventet antall turneringer flagges som et varsel."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": f"Rettferdig fordeling av hjemmeturneringer",
            "forklaring": (
                f"Arena-vertskap fordeles proporsjonalt etter antall lag hver klubb "
                f"stiller. Klubber med flere lag får hjemmeturnering oftere. "
                f"Maksimalt tillatt avvik fra forventet antall er "
                f"{self.max_hosting_deviation} turnering(er)."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": f"Jevnt antall kamper per lag",
            "forklaring": (
                f"Planleggeren teller opp alle kamper hvert lag spiller i løpet av "
                f"sesongen. Forskjellen mellom laget med flest og færrest kamper "
                f"skal være maksimalt {self.max_game_count_spread}. "
                f"Lag som blir ferdige for tidlig (mer enn "
                f"{self.max_early_finish_gap_days} dager før sesongslutt) flagges "
                f"som et varsel."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": "Jevn fordeling av kamper innad i aldersgruppe/klubb",
            "forklaring": (
                f"For hver aldersgruppe beregnes gjennomsnittlig antall kamper "
                f"per lag. Lag som avviker fra dette gjennomsnittet med mer enn "
                f"{self.max_game_count_spread} kamper flagges som et varsel. "
                f"Dette fanger opp skjevheter der en klubb med flere lag i samme "
                f"aldersgruppe (f.eks. flere U10-lag) systematisk får færre eller "
                f"flere kamper enn andre lag i samme aldersgruppe."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        for label, club, age_group, actual, expected in self._per_team_share_warnings:
            direction = "flere" if actual > expected else "færre"
            report.append({
                "regel": f"Skjev kampfordeling: {label}",
                "forklaring": (
                    f"{label} ({club}, {age_group}) spiller {actual} kamper, "
                    f"mens snittet for {age_group} er {expected:.1f} — "
                    f"{abs(actual - expected):.1f} {direction} enn snittet."
                ),
                "kategori": "Anbefaling",
            })

        report.append({
            "regel": "Behovsbasert unntak fra klubb-tak per turnering",
            "forklaring": (
                "Når et lag fra en klubb som allerede har fylt sin "
                "forholdsmessige andel av plassene i en turnering "
                "(_max_club_teams_for) har et større etterslep i antall "
                "spilte kamper enn alle ledige lag fra andre klubber, kan "
                "laget likevel velges — med en straff i prioriteringen "
                "proporsjonal med hvor langt over taket klubben er. Dette "
                "gjør at klubber med mange lag i samme aldersgruppe "
                "(f.eks. Jar) ikke blir systematisk underforsynt med "
                f"kamper. Dette unntaket er brukt {self._club_cap_overrides} "
                "gang(er) i denne sesongplanen."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": "Ingen overlappende aldersgrupper",
            "forklaring": (
                "Aldersgrupper som deler spillerbase (for eksempel JU11 og U10) "
                "skal helst ikke ha turnering samme helg, fordi noen spillere "
                "tilhører begge grupper og ville blitt dobbeltbooket. "
                "Planleggeren forsøker å unngå dette; kollisjoner som ikke kan "
                "løses, rapporteres."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": "Round-robin: alle mot alle innen turneringen",
            "forklaring": (
                "Innenfor hver turnering spiller alle inviterte lag mot hverandre "
                "nøyaktig én gang (round-robin). Turneringens størrelse og antall "
                "parallelle kamper avgjør hvor mange runder som trengs. "
                "Hjemme/borte byttes annenhver runde for rettferdig fordeling."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        report.append({
            "regel": "Sikkerhetsfilter mot klubb-interne kamper",
            "forklaring": (
                "Som en ekstra sikkerhet (belt-and-suspenders) hoppes det over "
                "kamper mellom to lag fra samme klubb under round-robin-genereringen, "
                "selv om deltakerutvelgelsen allerede skal ha forhindret dette."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        target_val = self.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT
        all_same_target = all(
            t.target_tournament_count is None or t.target_tournament_count == target_val
            for t in self.roster.teams
        )
        if all_same_target:
            target_desc = f"cirka {target_val} turneringsdeltakelser per lag"
            target_detail = (
                f"Hver aldersgruppe planlegges mot et mykt mål på rundt "
                f"{target_val} turneringsdeltakelser per lag."
            )
        else:
            targets = {
                t.target_tournament_count or target_val
                for t in self.roster.teams
            }
            target_range = ", ".join(sorted(str(t) for t in targets))
            target_desc = f"{min(targets)}–{max(targets)} turneringsdeltakelser per lag (varierer per lag)"
            target_detail = (
                f"Lag planlegges mot individuelle mål for turneringsdeltakelser: "
                f"{target_range}. Lag uten eget mål bruker standarden på {target_val}. "
            )
        report.append({
            "regel": f"Mykt mål: {target_desc}",
            "forklaring": (
                f"{target_detail} "
                f"Tallet er en ønsket sesongbelastning — planleggeren vil heller "
                f"lage færre, bedre turneringer enn å presse inn ekstra bare for "
                f"å nå målet. Dersom en aldersgruppe har for få lag eller for få "
                f"ledige helger til å oppfylle målet, justeres det ned."
            ),
            "kategori": "Automatisk avgjørelse",
        })

        # Time-of-day slot finding -- only relevant when calendar data was
        # supplied (`events_by_club`); otherwise tournaments keep the
        # default start time and this rule has no effect.
        if self.events_by_club:
            report.append({
                "regel": "Tidspunkt på dagen velges ut fra vertsklubbens egen hallkalender",
                "forklaring": (
                    "For hver turnering beregnes hvor lang tid hele turneringen "
                    "tar (rundelengde × antall runder), og planleggeren ser "
                    "etter en sammenhengende ledig luke av denne lengden i "
                    "vertsklubbens egen hallkalender. Tidspunkt nærmest 11:00 "
                    "foretrekkes, for å unngå svært tidlige eller sene "
                    "starttider. Hvis vertsklubbens egen hall ikke har en "
                    "passende ledig luke den dagen, beholdes den opprinnelige "
                    "vertsklubben og standard starttid i stedet for å låne "
                    "kapasitet fra andre klubber."
                ),
                "kategori": "Automatisk avgjørelse",
            })

        return report

    # ------------------------------------------------------------------
    # Step 1: pick dates spread evenly across the window
    # ------------------------------------------------------------------

    def _pick_spread_dates(
        self,
        free_dates: Sequence[date],
        window_start: date,
        window_end: date,
        age_groups: Sequence[str] = (),
        scheduled_age_groups_by_date: Optional[Dict[date, List[str]]] = None,
        target_count: Optional[int] = None,
    ) -> List[date]:
        """Pick 10-15 free dates for one age group, spread evenly across the season window.

        Buckets the date range into N roughly-equal slices. Within each
        bucket, candidates are ranked by a combined score: closeness to the
        bucket center (so the spread stays even) plus a projected
        matchup-diversity / month-balance penalty from `_score_candidate_date`
        — using a *tentative* age-group and participant prediction for each
        candidate date (mirroring `_next_age_group`/`_select_participants`,
        but against local copies of the tracking state so the real
        selection in `build_plan` is unaffected). This lets the planner
        prefer dates that are likely to produce fresher matchups and
        better-balanced months, not just even date spacing.

        `age_groups` may be empty (e.g. when the roster has none yet), in
        which case the projected-score component is skipped and selection
        falls back to closeness-to-center only.
        """
        if not free_dates:
            return []

        scheduled_age_groups_by_date = scheduled_age_groups_by_date or {}

        target_count = target_count or self._default_target_count(len(free_dates))
        target_count = max(1, min(target_count, len(free_dates)))

        total_days = (window_end - window_start).days
        if total_days <= 0 or target_count == 1:
            return list(free_dates[:target_count])

        expected_per_month = self._expected_monthly_load(window_start, window_end, target_count)

        bucket_span = total_days / target_count
        chosen: List[date] = []
        used: Set[date] = set()

        # Local copies of the predictive state, advanced as buckets are
        # filled, so later buckets' predictions account for earlier picks
        # without mutating the planner's real tracking structures.
        ag_index = 0
        scheduled_by_date: Dict[date, List[str]] = {}

        for i in range(target_count):
            bucket_start = window_start + timedelta(days=int(i * bucket_span))
            bucket_end = window_start + timedelta(days=int((i + 1) * bucket_span))
            bucket_center = bucket_start + (bucket_end - bucket_start) / 2
            half_span_days = max(1.0, (bucket_end - bucket_start).days / 2)

            candidates = [d for d in free_dates if bucket_start <= d <= bucket_end and d not in used]
            if not candidates:
                # Fall back to the closest unused free date overall.
                candidates = [d for d in free_dates if d not in used]
            if not candidates:
                continue

            if age_groups:
                predicted_age_group = self._next_age_group(
                    age_groups, ag_index, bucket_center, scheduled_by_date
                )
                predicted_participants = self._select_participants(predicted_age_group)

                def combined_score(d: date) -> float:
                    spread_penalty = abs((d - bucket_center).days) / half_span_days
                    diversity_penalty = self._score_candidate_date(
                        d, predicted_age_group, predicted_participants, expected_per_month
                    )
                    overlap_penalty = 0.0
                    for existing in scheduled_age_groups_by_date.get(d, []):
                        if (
                            predicted_age_group in overlapping_age_groups(existing)
                            or existing in overlapping_age_groups(predicted_age_group)
                        ):
                            overlap_penalty += 100.0
                    return spread_penalty + diversity_penalty + overlap_penalty

                best = min(candidates, key=combined_score)

                ag_index = (age_groups.index(predicted_age_group) + 1) % len(age_groups)
                scheduled_by_date.setdefault(best, []).append(predicted_age_group)
            else:
                best = min(candidates, key=lambda d: abs((d - bucket_center).days))

            chosen.append(best)
            used.add(best)

        return sorted(chosen)

    def _target_tournaments_for_age_group(self, age_group: str) -> int:
        """Return the number of tournaments to aim for in `age_group`.

        ``deltakelser_per_lag`` (also accepted as ``target_tournament_count``
        for backward compatibility) is a *soft* target: the desired number of
        tournament participations per team over the season. The scheduler
        converts that into a per-age-group tournament count by dividing by
        the age group's practical capacity (capped by the roster size).

        This is a load/participation hint, not a hard quota. The planner
        prefers fewer, better tournaments over hitting the target exactly,
        and will never create low-value tournaments just to satisfy it.
        When an age group has too few teams or free dates to reasonably
        meet the target, the count is adjusted downward.
        """
        teams = self.roster.by_age_group(age_group)
        if len(teams) < MIN_TEAMS_PER_TOURNAMENT:
            return 0
        
        # Sum per-team targets: each team contributes its own target if set,
        # otherwise the global default. This lets teams with lower targets
        # reduce the overall age-group tournament count appropriately.
        total_target = sum(
            (t.target_tournament_count or self.target_tournament_count or DEFAULT_TARGET_TOURNAMENT_COUNT)
            for t in teams
        )
        capacity = min(len(teams), self._max_teams_for(age_group))
        return max(1, math.ceil(total_target / capacity))

    @staticmethod
    def _default_target_count(num_free_dates: int) -> int:
        """Fallback when no age-group-specific target is available.

        Returns at most ``DEFAULT_TARGET_TOURNAMENT_COUNT``, bounded by
        the number of free dates — again a soft upper bound, never a
        hard quota.
        """
        return max(1, min(DEFAULT_TARGET_TOURNAMENT_COUNT, num_free_dates))

    # ------------------------------------------------------------------
    # Step 2: assign host arenas/clubs
    # ------------------------------------------------------------------

    def _assign_hosts(self, scheduled: Sequence[Tuple[date, str]]) -> List[str]:
        """Assign a host club to each scheduled ``(date, age_group)``.

        Hosting targets are computed independently per age group from the
        clubs that actually field teams in that age group. A club with many
        teams elsewhere in the roster therefore does not receive extra host
        responsibility for an unrelated age group.
        """
        if not scheduled:
            return []

        age_totals: Dict[str, int] = {}
        for _, age_group in scheduled:
            age_totals[age_group] = age_totals.get(age_group, 0) + 1

        targets_by_age = {
            age_group: self._hosting_targets_for_age_group(age_group, count)
            for age_group, count in age_totals.items()
        }
        actual_by_age: Dict[str, Dict[str, int]] = {
            age_group: {club: 0 for club in targets}
            for age_group, targets in targets_by_age.items()
        }
        last_hosted_by_age: Dict[str, Dict[str, int]] = {
            age_group: {club: -1 for club in targets}
            for age_group, targets in targets_by_age.items()
        }

        assignments: List[str] = []
        all_clubs = self.roster.clubs()
        for i, (_, age_group) in enumerate(scheduled):
            targets = targets_by_age.get(age_group, {})
            if not targets:
                assignments.append(all_clubs[i % len(all_clubs)] if all_clubs else "")
                continue

            actual_counts = actual_by_age[age_group]
            last_hosted_index = last_hosted_by_age[age_group]
            deficit_clubs = [
                club for club in targets
                if actual_counts.get(club, 0) < targets.get(club, 0)
            ]
            if deficit_clubs:
                host = max(
                    deficit_clubs,
                    key=lambda club: (
                        targets.get(club, 0) - actual_counts.get(club, 0),
                        -last_hosted_index.get(club, -1),
                        targets.get(club, 0),
                    ),
                )
            else:
                host = min(targets, key=lambda club: last_hosted_index.get(club, -1))

            assignments.append(host)
            actual_counts[host] = actual_counts.get(host, 0) + 1
            last_hosted_index[host] = i

        return assignments

    def _hosting_targets_for_age_group(self, age_group: str, tournament_count: int) -> Dict[str, int]:
        """Return integer host targets for one age group."""
        teams = self.roster.by_age_group(age_group)
        club_team_counts: Dict[str, int] = {}
        for team in teams:
            club_team_counts[team.club] = club_team_counts.get(team.club, 0) + 1
        return self._proportional_integer_targets(club_team_counts, tournament_count)

    @staticmethod
    def _proportional_integer_targets(weights: Dict[str, int], total: int) -> Dict[str, int]:
        """Round weighted quotas to integers that sum to ``total``."""
        if total <= 0 or not weights:
            return {club: 0 for club in weights}
        weight_sum = sum(max(0, weight) for weight in weights.values()) or 1
        raw_targets = {
            club: max(0, weight) / weight_sum * total
            for club, weight in weights.items()
        }
        targets: Dict[str, int] = {}
        remainders: List[Tuple[float, str]] = []
        assigned = 0
        for club, raw in raw_targets.items():
            rounded = int(raw)
            targets[club] = rounded
            assigned += rounded
            remainders.append((raw - rounded, club))
        remainders.sort(key=lambda item: (-item[0], item[1]))
        for _, club in remainders[: max(0, total - assigned)]:
            targets[club] += 1
        return targets

    # ------------------------------------------------------------------
    # Step 3: select participating teams
    # ------------------------------------------------------------------

    def _next_age_group(
        self,
        age_groups: Sequence[str],
        start_index: int,
        tournament_date: date,
        scheduled_by_date: Dict[date, List[str]],
    ) -> str:
        """Pick the next age group to schedule, round-robin from `start_index`.

        Tries to avoid picking an age group that overlaps with one already
        scheduled on `tournament_date`, when an alternative is available.
        """
        already_on_date = scheduled_by_date.get(tournament_date, [])

        for offset in range(len(age_groups)):
            candidate = age_groups[(start_index + offset) % len(age_groups)]
            overlaps_existing = any(
                candidate in overlapping_age_groups(existing) or existing in overlapping_age_groups(candidate)
                for existing in already_on_date
            )
            if not overlaps_existing:
                return candidate

        # No non-overlapping alternative — fall back to the round-robin pick.
        return age_groups[start_index % len(age_groups)]

    def _check_overlap_collision(
        self,
        tournament_date: date,
        age_group: str,
        scheduled_by_date: Dict[date, List[str]],
    ) -> Optional[str]:
        """Return the name of an overlapping age group already scheduled on
        `tournament_date`, if any (i.e. an unavoidable collision), else None.
        """
        for existing in scheduled_by_date.get(tournament_date, []):
            if age_group in overlapping_age_groups(existing) or existing in overlapping_age_groups(age_group):
                return existing
        return None

    def _select_participants(self, age_group: str) -> List[Team]:
        """Select the teams to invite to a tournament for the given age group.

        Enforces a per-club slot allowance (see `_max_club_teams_for`):
        each club may have up to a number of teams in a single tournament
        proportional to how many teams it fields in this age group.
        Tournament size itself is derived from the configured parallel-games
        count (roughly ``2 * parallel_games``); odd-sized participant sets
        are fine when the roster itself is odd and still fits within that
        base capacity, but we do not add an extra slot beyond the base
        capacity just to accommodate a bye/rest round.
        Invites the whole age-group roster when it fits that capacity and
        club diversity allows it; otherwise picks a subset using a
        least-recently-grouped-together heuristic.

        Root-cause note (club-size skew): previously, with a flat
        ``max_club_teams_per_tournament=1``, each club got at most one
        "slot" per tournament regardless of how many teams it fields in
        this age group. A club with many same-age-group teams (e.g. Jar
        fielding 7 U10 teams) therefore had its single slot shared/rotated
        across all of those teams, while a club with only one team in the
        age group (e.g. Kongsberg's sole U10 team) got that slot every
        time. `_max_club_teams_for` now grants such clubs a proportional
        number of slots (rounded up, capped by the tournament size limit),
        so several of a club's same-age-group siblings can be invited to
        the same tournament when capacity allows, equalizing each
        individual team's expected game count with a single-team club's
        count. See `per_team_share_warnings`
        (`_scan_per_team_share_warnings`) for any residual skew.
        """
        candidates = self.roster.by_age_group(age_group)
        if not candidates:
            return []

        # Exclude teams that have already reached their per-team
        # tournament participation cap. Teams at their target are not
        # invited to further tournaments, even if capacity exists.
        candidates = [t for t in candidates if not self._team_at_target(t)]
        if not candidates:
            return []

        max_teams = self._participant_limit_for(age_group, len(candidates))
        if len(candidates) <= max_teams:
            # Enforce per-club slot allowance even on the small-roster
            # fast path, but deficit-aware: a candidate over its club's
            # `_max_club_teams_for` allowance is dropped only if some
            # under-cap candidate has an equal-or-larger deficit (see
            # `_deficit_score`); otherwise it is kept so the team with the
            # largest season-wide deficit isn't excluded just because its
            # club already has its proportional share represented.
            return self._cap_per_club_deficit_aware(candidates, age_group)

        return self._pick_least_recently_grouped(candidates, max_teams, age_group)

    def _cap_per_club_deficit_aware(
        self, teams: Sequence[Team], age_group: str
    ) -> List[Team]:
        """Filter `teams` by `_max_club_teams_for`, with a deficit override.

        Walks `teams` in order, keeping a running per-club count. A team
        whose club has already reached its `_max_club_teams_for(age_group,
        club)` allowance among the kept teams is excluded *unless* its
        deficit score (`_deficit_score`) is greater than every still-pending
        under-cap candidate's deficit score — mirroring the override applied
        in `_pick_least_recently_grouped`. Increments
        `_club_cap_overrides` whenever a kept team exceeds its club's
        allowance.
        """
        result: List[Team] = []
        club_counts: Dict[str, int] = {}
        remaining = list(teams)

        for index, team in enumerate(remaining):
            club_count = club_counts.get(team.club, 0)
            max_club = self._max_club_teams_for(age_group, team.club)
            if club_count < max_club:
                club_counts[team.club] = club_count + 1
                result.append(team)
                continue

            # Over cap: keep only if no other still-pending under-cap
            # candidate has an equal-or-larger deficit.
            pending_under_cap_deficits = [
                self._deficit_score(t, age_group)
                for t in remaining[index + 1:]
                if club_counts.get(t.club, 0) < self._max_club_teams_for(age_group, t.club)
            ]
            this_deficit = self._deficit_score(team, age_group)
            if pending_under_cap_deficits and max(pending_under_cap_deficits) >= this_deficit:
                continue

            club_counts[team.club] = club_count + 1
            result.append(team)
            self._club_cap_overrides += 1

        return result

    def _parallel_games_for(self, age_group: str) -> int:
        """Return the configured parallel-games count for `age_group`."""
        parallel_games = self.parallel_games_for_age_group.get(age_group, DEFAULT_PARALLEL_GAMES)
        return max(1, parallel_games)

    def _base_team_capacity(self, age_group: str) -> int:
        """Return the even team-count capacity implied by parallel games."""
        return self._parallel_games_for(age_group) * 2

    def _participant_limit_for(self, age_group: str, team_count: int) -> int:
        """Return the max teams that fit a tournament for `team_count` rosters.

        Even-sized rosters are limited to the base even capacity. Odd-sized
        rosters can take one extra team, which the round-robin generator turns
        into a bye/rest round.
        """
        base_capacity = self._base_team_capacity(age_group)
        return min(base_capacity, team_count)

    def _max_teams_for(self, age_group: str) -> int:
        """Return the largest odd-capacity tournament size for `age_group`.

        This is the upper bound the planner can ever use for the age group:
        the even base capacity. Odd rosters are still allowed as long as
        they fit within that capacity, but we do not extend the limit by
        one extra team.
        """
        return self._base_team_capacity(age_group)

    def _max_club_teams_for(self, age_group: str, club: str) -> int:
        """Return how many teams from `club` may play in one `age_group` tournament.

        Replaces the old flat ``max_club_teams_per_tournament`` cap with a
        per-club allowance proportional to how many teams that club fields
        in this age group, relative to the age group's total team count:

            ceil(club_team_count / total_team_count * tournament_capacity)

        capped at the age group's `_max_teams_for` tournament-size limit, and
        floored at `max_club_teams_per_tournament` (default 1) for any club
        that has at least one team in the age group. This lets a club with
        many same-age-group teams (e.g. Jar fielding 7 U10 teams) send
        several of them to the same tournament when capacity permits,
        instead of rotating a single shared slot — equalizing each
        individual team's expected game count with a single-team club's
        (e.g. Kongsberg's sole U10 team).
        """
        teams_in_age_group = self.roster.by_age_group(age_group)
        total = len(teams_in_age_group)
        if total == 0:
            return self.max_club_teams_per_tournament
        club_team_count = sum(1 for t in teams_in_age_group if t.club == club)
        if club_team_count == 0:
            return self.max_club_teams_per_tournament

        max_teams = self._max_teams_for(age_group)
        proportional = math.ceil(club_team_count / total * max_teams)

        # Deficit-aware cap expansion: when the age group's deficit spread
        # exceeds `max_game_count_spread`, add `deficit_cap_expansion` extra
        # slots to the proportional cap. This lets teams from clubs that
        # are structurally behind (e.g. Jar's many U10 siblings rotating
        # through limited slots) catch up faster without fundamentally
        # changing the proportional fairness logic for balanced groups.
        deficit_spread = self._age_group_deficit_spread(age_group, teams_in_age_group)
        if deficit_spread > self.max_game_count_spread:
            proportional = min(proportional + self.deficit_cap_expansion, max_teams)

        return max(self.max_club_teams_per_tournament, min(proportional, max_teams))

    def _age_group_deficit_spread(self, age_group: str, teams_in_age_group: Optional[List[Team]] = None) -> float:
        """Return the deficit spread (max - min deficit) across `age_group`.

        When planning targets and running counts are available, computes
        each team's deficit (target - actual) and returns the spread.
        Returns 0.0 when no running counts are available (e.g. at the
        start of planning) so the cap expansion does not kick in early.
        """
        if teams_in_age_group is None:
            teams_in_age_group = self.roster.by_age_group(age_group)
        if not teams_in_age_group:
            return 0.0
        if not any(self._running_game_counts.get(self._team_key(t), 0) for t in teams_in_age_group):
            return 0.0
        deficits = [
            self._deficit_score(t, age_group)
            for t in teams_in_age_group
        ]
        if not deficits:
            return 0.0
        return max(deficits) - min(deficits)


    def _expected_average_for(self, age_group: str) -> float:
        """Return the current running average game count for `age_group`.

        Computes ``sum(counts) / len(counts)`` over `_running_game_counts`
        for every team in `age_group` (teams with no recorded games count
        as 0) — the same averaging pattern used by
        `_scan_per_team_share_warnings`, but evaluated against the
        in-progress `_running_game_counts` so it can be used as a live
        target during selection.
        """
        teams = self.roster.by_age_group(age_group)
        if not teams:
            return 0.0
        counts = [self._running_game_counts.get(self._team_key(team), 0) for team in teams]
        return sum(counts) / len(counts)

    def _deficit_score(self, team: Team, age_group: str) -> float:
        """Return how far below the fairness target `team` is.

        A positive value means `team` has played fewer games so far than
        the soft target from `self.fairness_model` and should be
        prioritized for future invitations; a negative value means it is
        already above that target. Used by `_pick_least_recently_grouped`
        and `_select_participants` to steer the season toward the same
        soft fairness shape that post-plan warnings use.

        If the team has already reached its per-team tournament
        participation cap (`_team_at_target`), returns -1 so the team
        is deprioritised and will not be invited to further tournaments.
        """
        if self._team_at_target(team):
            return -1.0
        age_group_teams = self.roster.by_age_group(age_group)
        if not age_group_teams:
            return 0.0
        key = self._team_key(team)
        target = self.fairness_model.planning_target_games_for_team(
            team,
            age_group_teams,
            self._running_game_counts,
        )
        return target - self._running_game_counts.get(key, 0)

    def _normalized_invite_count(self, team: Team) -> float:
        """Return `team`'s invite count, normalized by club-size-in-age-group.

        Multiplying the raw invite count by the number of same-club teams in
        the same age group converts it into a proxy for the club's *total*
        invitations to that age group. A Jar U10 team (1 of 6 siblings)
        reaches the same normalized value as Kongsberg's sole U10 team only
        after Jar's U10 teams collectively receive ~6x as many invitations,
        so each individual team ends up with a roughly equal expected share
        regardless of how many sibling teams its club fields in that age
        group.
        """
        key = self._team_key(team)
        sibling_count = self._club_age_group_team_counts.get(key, 1)
        return self._invite_counts.get(key, 0) * sibling_count

    def _pick_least_recently_grouped(
        self, candidates: Sequence[Team], count: int, age_group: str
    ) -> List[Team]:
        """Greedily build a subset that minimizes repeat matchups.

        Starts from the team that has been invited least often overall, then
        repeatedly adds the candidate that would create the fewest *actual
        repeat matchups* with the already-selected teams, per
        `_opponent_history` — directly enforcing "avoid repeat matchups
        where alternatives exist" at selection time, rather than only
        measuring it after the fact. Ties in repeat-matchup count fall back
        to the original heuristic: fewest prior tournament co-attendances
        (`_grouped_with`), then lowest overall invite count, then roster
        order.

        Enforces a per-club slot allowance: teams from a club that already
        has `_max_club_teams_for(age_group, club)` teams in the selected set
        are excluded entirely. If that leaves no candidates at all, falls
        back to the soft penalty to avoid deadlock.

        Root-cause note (club-size skew): see `_select_participants` and
        `_record_grouping` for why raw `_invite_counts` alone would
        under-prioritize teams from clubs with many same-age-group
        siblings. This method's seed selection and tie-break both use
        `_normalized_invite_count` instead of raw `_invite_counts` to
        rotate a club's shared per-tournament slot(s) evenly across its
        siblings, while `_max_club_teams_for` grants clubs with many
        same-age-group teams proportionally more slots per tournament so
        individual siblings' game counts can match a single-team club's
        count. Any residual skew is reported via `per_team_share_warnings`.
        """
        remaining = list(candidates)
        if not remaining:
            return []

        # Seed with the team furthest below the age group's running average
        # game count (largest deficit, see `_deficit_score`), falling back
        # to the least-invited team so invitations stay balanced. The
        # invite count is normalized by the number of same-club teams in
        # the same age group, so a team that is one of several siblings from
        # the same club (e.g. one of Jar's 6 U10 teams) is prioritized
        # roughly proportionally more often than a club's sole team in that
        # age group (e.g. Kongsberg's only U10 team), equalizing each team's
        # expected per-season invitation count.
        remaining.sort(
            key=lambda t: (
                -self._deficit_score(t, age_group),
                self._normalized_invite_count(t),
                candidates.index(t),
            )
        )
        selected: List[Team] = [remaining.pop(0)]

        while remaining and len(selected) < count:
            def repeat_matchup_score(team: Team) -> int:
                total = 0
                for s in selected:
                    pair = frozenset((self._team_key(team), self._team_key(s)))
                    total += self._opponent_history.get(pair, 0)
                return total

            def overlap_score(team: Team) -> int:
                grouped_with = self._grouped_with.get(self._team_key(team), set())
                return sum(1 for s in selected if self._team_key(s) in grouped_with)

            # Deficit-aware club constraint: a candidate whose club already
            # has its full `_max_club_teams_for(age_group, club)` allowance
            # represented in `selected` is excluded *unless* its deficit
            # score (see `_deficit_score`) is greater than every under-cap
            # candidate's deficit score in `remaining` — i.e. it is only
            # allowed to exceed its club's cap when no under-cap team needs
            # the slot more. This replaces the previous purely hard filter,
            # which could leave the team with the largest season-wide
            # deficit (e.g. a Jar sibling) excluded whenever any other
            # club's under-cap team was available, even if that team's own
            # deficit was small or negative.
            under_cap: List[Team] = [
                t for t in remaining
                if sum(1 for s in selected if s.club == t.club)
                < self._max_club_teams_for(age_group, t.club)
            ]
            over_cap: List[Team] = [t for t in remaining if t not in under_cap]
            max_under_cap_deficit = (
                max(self._deficit_score(t, age_group) for t in under_cap)
                if under_cap else None
            )
            eligible_over_cap = [
                t for t in over_cap
                if max_under_cap_deficit is None
                or self._deficit_score(t, age_group) > max_under_cap_deficit
            ]
            eligible = under_cap + eligible_over_cap
            if not eligible:
                eligible = remaining

            selected_clubs = {s.club for s in selected}
            # Deficit-aware club-mix filter: when the age group's deficit
            # spread exceeds max_game_count_spread, skip the cross-club
            # mixing heuristic so multi-team clubs (e.g. Jar with 7 U10
            # teams) can bring more than one sibling to a tournament when
            # their teams are structurally behind. When deficits are small
            # or zero, the filter stays active to preserve opponent diversity.
            deficit_spread = self._age_group_deficit_spread(age_group)
            if deficit_spread <= self.max_game_count_spread:
                preferred_club_mix = [t for t in eligible if t.club not in selected_clubs]
                if preferred_club_mix:
                    eligible = preferred_club_mix

            eligible_over_cap_labels = {self._team_key(t) for t in eligible_over_cap}

            # Club-load penalty: push down candidates whose club is already
            # heavily represented in `selected`, even before the hard/proportional
            # cap is hit. This nudges the picker toward cross-club mixing so one
            # club doesn't monopolize a tournament when alternative opponents
            # are available.
            def club_penalty(team: Team) -> int:
                club_count = sum(1 for s in selected if s.club == team.club)
                max_club = self._max_club_teams_for(age_group, team.club)
                base = club_count * 10
                if club_count < max_club:
                    return base
                if self._team_key(team) in eligible_over_cap_labels:
                    return base + (club_count - max_club + 1) * 50
                return base + club_count * 100  # outweighs typical match-up scores

            # Skill-level proximity penalty: prefer candidates whose skill
            # level is within `division_skill_band` of the selected set's
            # median skill level.  Unrated teams (no skill_level) are never
            # penalised — they are treated as universally adjacent.
            def skill_penalty(team: Team) -> int:
                selected_levels = [
                    self._team_skill_levels[self._team_key(s)]
                    for s in selected
                    if self._team_key(s) in self._team_skill_levels
                ]
                if not selected_levels:
                    return 0  # no reference level yet
                if self._team_key(team) not in self._team_skill_levels:
                    return 0  # unrated team — no filter
                median = sorted(selected_levels)[len(selected_levels) // 2]
                dist = abs(team.skill_level - median)
                if dist <= self.division_skill_band:
                    return 0
                return (dist - self.division_skill_band) * 100

            eligible.sort(
                key=lambda t: (
                    -self._deficit_score(t, age_group) * 1000,
                    repeat_matchup_score(t),
                    overlap_score(t),
                    skill_penalty(t),
                    club_penalty(t),
                    self._normalized_invite_count(t),
                    candidates.index(t),
                )
            )
            chosen = eligible.pop(0)
            remaining.remove(chosen)
            selected.append(chosen)

            chosen_club_count = sum(1 for s in selected if s.club == chosen.club)
            if chosen_club_count > self._max_club_teams_for(age_group, chosen.club):
                self._club_cap_overrides += 1

        return selected

    def _record_grouping(self, participants: Sequence[Team]) -> None:
        """Record that `participants` were grouped together this tournament.

        Note: `_invite_counts` (incremented here) tracks raw invitations
        per team *label*, with no awareness of how many same-club teams
        share an age group. Read alone, it would balance individual labels
        evenly — but since `max_club_teams_per_tournament` caps a club to
        one slot per tournament regardless of its team count, a club
        fielding several same-age-group teams (e.g. Jar's 7 U10 teams)
        effectively dilutes one shared slot's invites across all of them.
        `_pick_least_recently_grouped` compensates for this via
        `_normalized_invite_count`, which multiplies each team's
        `_invite_counts` value by its club's same-age-group team count
        before comparing — see that method's docstring for details.
        """
        labels = [self._team_key(team) for team in participants]
        games_added = max(0, len(participants) - 1)
        for team in participants:
            key = self._team_key(team)
            self._invite_counts[key] = self._invite_counts.get(key, 0) + 1
            self._tournament_participations[key] = (
                self._tournament_participations.get(key, 0) + 1
            )
            grouped = self._grouped_with.setdefault(key, set())
            grouped.update(label for label in labels if label != key)
            self._running_game_counts[key] = (
                self._running_game_counts.get(key, 0) + games_added
            )

    def _record_opponent_history(self, games: Sequence[Game]) -> None:
        """Record actual scheduled matchups from `games` in `_opponent_history`.

        Unlike `_record_grouping` (which only tracks tournament
        co-attendance), this tracks how many times each unordered pair of
        teams has actually been scheduled to play one another, keyed by a
        `frozenset` of the two team labels so that home/away order doesn't
        matter.
        """
        for game in games:
            if game.home is None or game.away is None:
                continue
            pair = frozenset((self._team_key(game.home), self._team_key(game.away)))
            self._opponent_history[pair] = self._opponent_history.get(pair, 0) + 1

    # ------------------------------------------------------------------
    # Month-load tracking
    # ------------------------------------------------------------------

    @staticmethod
    def _expected_monthly_load(window_start: date, window_end: date, tournament_count: int) -> float:
        """Return the season's expected average tournament count per month.

        Derived from the number of distinct year-months spanned by the
        season window and the total number of tournaments being scheduled.
        Used as the baseline that `month_load_ratio` compares actual counts
        against. Returns `0.0` when the window is empty or no tournaments
        are scheduled.
        """
        if tournament_count <= 0:
            return 0.0

        months_spanned = (
            (window_end.year - window_start.year) * 12
            + (window_end.month - window_start.month)
            + 1
        )
        months_spanned = max(1, months_spanned)
        return tournament_count / months_spanned

    def _record_month(self, tournament_date: date) -> None:
        """Record that a tournament was scheduled in `tournament_date`'s month."""
        key = (tournament_date.year, tournament_date.month)
        self._month_counts[key] = self._month_counts.get(key, 0) + 1

    def _score_candidate_date(
        self,
        candidate_date: date,
        age_group: str,
        candidate_participants: Sequence[Team],
        expected_per_month: float,
    ) -> float:
        """Score a candidate date for a tentative age-group/participant set.

        Combines two penalties (lower score = more desirable candidate):

        - **Repeat-matchup penalty**: the average `_opponent_history` count
          across all unordered pairs in `candidate_participants` — higher
          when the candidate set would create more repeat matchups.
        - **Month-load penalty**: how far above the season's expected
          per-month average `candidate_date`'s month already is, per
          `month_load_ratio` — higher when the month is already overloaded.
          Only the excess above `1.0` (i.e. above-average load) counts as a
          penalty; under-loaded months contribute `0`.

        The two penalties are weighted equally and summed. `age_group` is
        accepted for symmetry/future use (e.g. age-group-specific weighting)
        but does not currently affect the score directly — its influence is
        already captured via `candidate_participants`.
        """
        repeat_penalty = 0.0
        participants = list(candidate_participants)
        if len(participants) >= 2:
            pair_count = 0
            repeat_total = 0
            for i, team_a in enumerate(participants):
                for team_b in participants[i + 1:]:
                    pair = frozenset((self._team_key(team_a), self._team_key(team_b)))
                    repeat_total += self._opponent_history.get(pair, 0)
                    pair_count += 1
            if pair_count:
                repeat_penalty = repeat_total / pair_count

        load_ratio = self.month_load_ratio(candidate_date, expected_per_month)
        month_penalty = max(0.0, load_ratio - 1.0)

        return repeat_penalty + month_penalty

    def month_load_ratio(self, tournament_date: date, expected_per_month: float) -> float:
        """Report how loaded `tournament_date`'s month is, relative to average.

        Returns the ratio of the month's current tournament count (as
        recorded via `_record_month`, including `tournament_date` itself if
        already recorded) to `expected_per_month`. A ratio greater than `1.0`
        indicates the month is already carrying more than its fair share of
        the season's tournament load — a concrete signal that downstream
        selection logic can use to prefer a less-loaded alternative date
        where one exists. Returns `0.0` when `expected_per_month` is `0`.
        """
        if expected_per_month <= 0:
            return 0.0

        key = (tournament_date.year, tournament_date.month)
        return self._month_counts.get(key, 0) / expected_per_month

    # ------------------------------------------------------------------
    # Within-tournament round-robin game-schedule generator
    # ------------------------------------------------------------------

    @staticmethod
    def generate_round_robin_games(
        teams: Sequence[Team],
        parallel_games: int,
    ) -> List[Game]:
        """Generate a round-robin schedule for `teams` using the circle method.

        Games are grouped into rounds (one round = each team plays at most
        once), and within each round games are assigned to `parallel_slot`
        indices so that up to `parallel_games` games run concurrently.

        When the generated game list is sparse, the surviving games are
        repacked into the smallest possible number of balanced rounds so the
        exported plan stays easy to read.

        Args:
            teams: The participating teams (all the same age group).
            parallel_games: Max number of games that can run concurrently.

        Returns:
            A flat list of `Game`, each with its `parallel_slot` set to its
            position within its round (0-based).
        """
        n = len(teams)
        if n < 2:
            return []

        parallel_games = max(1, parallel_games)

        # Circle method requires an even number of "slots" — pad with a bye
        # placeholder (None) when there's an odd number of teams.
        roster = list(teams)
        has_bye = n % 2 == 1
        if has_bye:
            roster = roster + [None]  # type: ignore[list-item]

        slot_count = len(roster)
        num_rounds = slot_count - 1
        half = slot_count // 2

        games: List[Game] = []
        rotation = roster[:]

        for round_index in range(num_rounds):
            round_pairs: List[Tuple[Team, Team]] = []
            for i in range(half):
                home = rotation[i]
                away = rotation[slot_count - 1 - i]
                if home is None or away is None:
                    continue  # bye — this team sits out this round
                round_pairs.append((home, away))

            # Alternate home/away across rounds for a fairer split.
            if round_index % 2 == 1:
                round_pairs = [(away, home) for home, away in round_pairs]

            for slot_index, (home, away) in enumerate(round_pairs):
                games.append(
                    Game(
                        home=home,
                        away=away,
                        parallel_slot=slot_index % parallel_games,
                        round_number=round_index + 1,
                    )
                )

            # Rotate all but the first fixed element (standard circle method).
            rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

        round_sizes: dict[int, int] = {}
        for game in games:
            round_sizes[game.round_number] = round_sizes.get(game.round_number, 0) + 1
        expected_round_size = n // 2
        if round_sizes and all(count == expected_round_size for count in round_sizes.values()):
            return games
        return SeasonPlanner._rebalance_rounds(games, parallel_games)

    @staticmethod
    def _rebalance_rounds(games: Sequence[Game], parallel_games: int) -> List[Game]:
        """Pack games into the smallest balanced set of rounds possible.

        The circle method yields a valid round structure when all pairings are
        kept. When the generated game list becomes lumpy for any reason,
        this helper reassigns games to rounds so that:

        - no team appears twice in the same round,
        - no round exceeds ``parallel_games`` games, and
        - the round counts stay as even as the constraints allow.
        """
        if not games:
            return []

        parallel_games = max(1, parallel_games)

        team_degree: dict[str, int] = {}
        for game in games:
            team_degree[game.home.label] = team_degree.get(game.home.label, 0) + 1
            team_degree[game.away.label] = team_degree.get(game.away.label, 0) + 1

        max_team_games = max(team_degree.values(), default=0)
        required_rounds = max(max_team_games, math.ceil(len(games) / parallel_games))
        required_rounds = max(1, required_rounds)

        base_size, remainder = divmod(len(games), required_rounds)
        ideal_sizes = [base_size + (1 if i < remainder else 0) for i in range(required_rounds)]

        def _target_candidates() -> list[list[int]]:
            candidates: list[list[int]] = []

            def build(prefix: list[int], remaining: int, max_next: int, rounds_left: int) -> None:
                if rounds_left == 0:
                    if remaining == 0:
                        candidates.append(prefix[:])
                    return

                if remaining < rounds_left or remaining > rounds_left * parallel_games:
                    return

                upper = min(max_next, remaining - (rounds_left - 1))
                lower = max(1, math.ceil(remaining / rounds_left))
                for size in range(upper, lower - 1, -1):
                    prefix.append(size)
                    build(prefix, remaining - size, size, rounds_left - 1)
                    prefix.pop()

            build([], len(games), parallel_games, required_rounds)
            if not candidates:
                candidates.append(ideal_sizes)

            average = len(games) / required_rounds
            candidates.sort(
                key=lambda sizes: (
                    max(sizes) - min(sizes),
                    sum((size - average) ** 2 for size in sizes),
                    tuple(-size for size in sizes),
                )
            )
            return candidates

        ordered = list(enumerate(games))
        ordered.sort(
            key=lambda item: (
                -(team_degree[item[1].home.label] + team_degree[item[1].away.label]),
                item[1].round_number or 0,
                item[1].home.label,
                item[1].away.label,
                item[0],
            )
        )

        round_games: list[list[tuple[int, Game]]] = []
        round_teams: list[set[str]] = []
        round_counts: list[int] = []

        def try_targets(target_sizes: list[int]) -> bool:
            nonlocal round_games, round_teams, round_counts
            round_games = [[] for _ in range(required_rounds)]
            round_teams = [set() for _ in range(required_rounds)]
            round_counts = [0 for _ in range(required_rounds)]

            def backtrack(index: int) -> bool:
                if index >= len(ordered):
                    return True

                remaining_slots = sum(target_sizes[r] - round_counts[r] for r in range(required_rounds))
                if remaining_slots < len(ordered) - index:
                    return False

                original_index, game = ordered[index]
                candidate_rounds = [
                    r for r in range(required_rounds)
                    if round_counts[r] < target_sizes[r]
                    and game.home.label not in round_teams[r]
                    and game.away.label not in round_teams[r]
                ]
                candidate_rounds.sort(key=lambda r: (round_counts[r], r))

                for round_index in candidate_rounds:
                    round_games[round_index].append((original_index, game))
                    round_counts[round_index] += 1
                    round_teams[round_index].update({game.home.label, game.away.label})

                    if backtrack(index + 1):
                        return True

                    round_games[round_index].pop()
                    round_counts[round_index] -= 1
                    round_teams[round_index].discard(game.home.label)
                    round_teams[round_index].discard(game.away.label)

                return False

            return backtrack(0)

        solved = False
        for target_sizes in _target_candidates():
            if try_targets(target_sizes):
                solved = True
                break

        if not solved:
            return games


        rebased: List[Game] = []
        for round_index, games_in_round in enumerate(round_games, start=1):
            games_in_round.sort(
                key=lambda item: (
                    item[1].round_number or 0,
                    item[0],
                    item[1].home.label,
                    item[1].away.label,
                )
            )
            for slot_index, (_, game) in enumerate(games_in_round):
                game.round_number = round_index
                game.parallel_slot = slot_index % parallel_games
                rebased.append(game)
        return rebased

    @staticmethod
    def _best_round_subset(
        candidates: Sequence[tuple[int, Game]],
        parallel_games: int,
    ) -> list[tuple[int, Game]]:
        """Return the largest compatible subset of games for one round."""
        limit = max(1, parallel_games)
        ordered = list(candidates)
        best: list[tuple[int, Game]] = []
        best_signature: tuple[int, ...] | None = None

        def signature(selection: list[tuple[int, Game]]) -> tuple[int, ...]:
            return tuple(index for index, _ in selection)

        def consider(selection: list[tuple[int, Game]]) -> None:
            nonlocal best, best_signature
            current_signature = signature(selection)
            if len(selection) > len(best):
                best = selection[:]
                best_signature = current_signature
            elif len(selection) == len(best):
                if best_signature is None or current_signature < best_signature:
                    best = selection[:]
                    best_signature = current_signature

        def backtrack(index: int, chosen: list[tuple[int, Game]], used_teams: set[str]) -> None:
            consider(chosen)

            if index >= len(ordered) or len(chosen) >= limit:
                return
            if len(chosen) + (len(ordered) - index) <= len(best):
                return

            # Skip the current candidate.
            backtrack(index + 1, chosen, used_teams)

            # Or include it when it doesn't collide with the teams already
            # chosen for this round.
            original_index, game = ordered[index]
            if game.home.label in used_teams or game.away.label in used_teams:
                return
            chosen.append((original_index, game))
            backtrack(index + 1, chosen, used_teams | {game.home.label, game.away.label})
            chosen.pop()

        backtrack(0, [], set())
        return best

    # ------------------------------------------------------------------
    # Plan metadata helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _arena_counts(tournaments: Sequence[Tournament]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for tournament in tournaments:
            counts[tournament.arena] = counts.get(tournament.arena, 0) + 1
        return counts

    def _diversity_score(self, tournaments: Sequence[Tournament]) -> float:
        """Opponent-variety diversity score grounded in `_opponent_history`.

        Distinct from `_pairwise_matchup_score` (which measures how many
        *games* are first-time pairings). This metric instead measures, per
        team, how much of its eligible opponent pool it has actually faced
        this season:

        For each team that has played at least one game this season (i.e.
        appears in at least one pair recorded in `_opponent_history`), count
        its distinct opponents so far and divide by the number of "available
        opponents" — other teams in the same age group, excluding teams from
        its own club.

        The overall score is the average of these per-team ratios, rounded
        to 3 decimals (1.0 = every team has played every eligible opponent
        at least once; lower values indicate teams repeatedly facing a
        narrow set of opponents). Returns `0.0` when no teams have played
        any games.
        """
        # Distinct opponents faced so far, per team label.
        opponents_faced: Dict[str, set] = {}
        for pair in self._opponent_history:
            a, b = tuple(pair)
            opponents_faced.setdefault(a, set()).add(b)
            opponents_faced.setdefault(b, set()).add(a)

        if not opponents_faced:
            return 0.0

        teams_by_key = {self._team_key(team): team for team in self.roster.teams}

        ratios = []
        for key, faced in opponents_faced.items():
            team = teams_by_key.get(key)
            if team is None:
                continue
            available = [
                self._team_key(other)
                for other in self.roster.teams
                if self._team_key(other) != key
                and other.age_group == team.age_group
                and other.club != team.club
            ]
            if not available:
                continue
            ratios.append(len(faced) / len(available))

        if not ratios:
            return 0.0
        return round(sum(ratios) / len(ratios), 3)

    def _pairwise_matchup_score(self, tournaments: Sequence[Tournament]) -> float:
        """Fraction of scheduled matchups that are first-time pairings.

        Walks every `Game` across `tournaments` in order, building up a
        running per-pair match count (keyed by `frozenset` of team labels —
        equivalent to what `_opponent_history` accumulates over a full
        season) and counts a game as a "first-time pairing" when it's the
        first scheduled meeting between that exact pair of teams.

        Returns `novel_pairings / total_games` rounded to 3 decimals
        (1.0 = every scheduled game is a fresh matchup; lower values mean
        more repeat matchups). Returns `0.0` when no games were scheduled.
        """
        seen_pairs: Dict[frozenset, int] = {}
        novel_total = 0
        game_total = 0

        for tournament in tournaments:
            for game in tournament.games:
                if game.home is None or game.away is None:
                    continue
                pair = frozenset((self._team_key(game.home), self._team_key(game.away)))
                game_total += 1
                if pair not in seen_pairs:
                    novel_total += 1
                seen_pairs[pair] = seen_pairs.get(pair, 0) + 1

        if game_total == 0:
            return 0.0
        return round(novel_total / game_total, 3)

    def _month_balance_score(self, expected_per_month: float) -> float:
        """Score how evenly tournaments are spread across the season's months.

        Grounded in `_month_counts` (populated during `build_plan`):
        computes, for every month that hosted at least one tournament, how
        far its actual count deviates from `expected_per_month`, averages
        those deviations (as a fraction of the expected value), and
        converts that into a `0..1` balance score where `1.0` means every
        month carried exactly its expected share and lower values indicate
        more uneven month-to-month distribution.

        Returns `0.0` when there is no expected load to compare against or
        no months were recorded.
        """
        if expected_per_month <= 0 or not self._month_counts:
            return 0.0

        deviation_total = 0.0
        for count in self._month_counts.values():
            deviation_total += abs(count - expected_per_month) / expected_per_month

        avg_deviation = deviation_total / len(self._month_counts)
        return round(max(0.0, 1.0 - avg_deviation), 3)


# Delegate the participant-selection / host-assignment helpers to focused modules.
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


# Delegate the helper-heavy planning logic to focused modules.
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
