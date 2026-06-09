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

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Set, Tuple

from tournament_scheduler.models import (
    AGE_GROUP_OVERLAP,
    Game,
    Roster,
    SeasonPlan,
    Team,
    Tournament,
    overlapping_age_groups,
)
from tournament_scheduler.scheduler import TournamentScheduler


# Default bounds on how many tournaments the season plan should propose.
MIN_TOURNAMENTS = 10
MAX_TOURNAMENTS = 15

# A tournament round-robin works best with a modest number of teams; this is
# the practical ceiling used as a fallback when no parallel-games config is
# supplied for an age group (actual subset sizes are derived from available
# timeslots × parallelGames where that information is available).
DEFAULT_MAX_TEAMS_PER_TOURNAMENT = 6


class SeasonPlanner:
    """Greedy season-plan builder on top of `TournamentScheduler`."""

    def __init__(
        self,
        scheduler: TournamentScheduler,
        roster: Roster,
        club_arenas: Dict[str, str],
        parallel_games_for_age_group: Optional[Dict[str, int]] = None,
        target_tournament_count: Optional[int] = None,
        max_teams_per_tournament_for_age_group: Optional[Dict[str, int]] = None,
    ):
        """Initialize the planner.

        Args:
            scheduler: A configured `TournamentScheduler` used to find
                conflict-free weekend dates for the season window.
            roster: The manually-configured club/team roster for the season.
            club_arenas: Mapping of club/host name -> home arena name (e.g.
                from the club registry), used to assign tournament hosts.
            parallel_games_for_age_group: Optional mapping of age group ->
                configured parallel-games count, used to derive a practical
                round-robin subset size per age group. Falls back to
                `DEFAULT_MAX_TEAMS_PER_TOURNAMENT` when not provided.
            target_tournament_count: Optional override for how many
                tournaments to propose (default: spread between
                `MIN_TOURNAMENTS` and `MAX_TOURNAMENTS` based on how many
                free dates are available).
            max_teams_per_tournament_for_age_group: Optional mapping of age
                group -> maximum number of teams invited to a single
                tournament. When set for an age group, takes precedence over
                the parallel-games heuristic in `_max_teams_for`.
        """
        self.scheduler = scheduler
        self.roster = roster
        self.club_arenas = club_arenas
        self.parallel_games_for_age_group = parallel_games_for_age_group or {}
        self.target_tournament_count = target_tournament_count
        self.max_teams_per_tournament_for_age_group = max_teams_per_tournament_for_age_group or {}

        # Tracks, per team, the set of other teams it has already been
        # grouped with in a tournament this season — used by the
        # least-recently-grouped-together heuristic.
        self._grouped_with: Dict[str, Set[str]] = {}
        # Tracks how many times each team has been invited overall, to keep
        # invitations roughly balanced across the season.
        self._invite_counts: Dict[str, int] = {team.label: 0 for team in roster.teams}
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

        chosen_dates = self._pick_spread_dates(
            free_dates, start_date.date(), end_date.date(), age_groups
        )

        host_assignments = self._assign_hosts(chosen_dates)
        collisions: List[Tuple[date, str, str]] = []

        # Round-robin over age groups so the season covers a varied mix
        # rather than e.g. always scheduling U10 first.
        ag_index = 0
        scheduled_age_groups_by_date: Dict[date, List[str]] = {}

        for tournament_date, host_club in zip(chosen_dates, host_assignments):
            self._record_month(tournament_date)

            age_group = self._next_age_group(
                age_groups, ag_index, tournament_date, scheduled_age_groups_by_date
            )
            ag_index = (age_groups.index(age_group) + 1) % len(age_groups)

            collision = self._check_overlap_collision(
                tournament_date, age_group, scheduled_age_groups_by_date
            )
            if collision:
                collisions.append((tournament_date, age_group, collision))

            scheduled_age_groups_by_date.setdefault(tournament_date, []).append(age_group)

            arena = self.club_arenas.get(host_club, host_club)
            participants = self._select_participants(age_group)
            self._record_grouping(participants)

            parallel_games = self.parallel_games_for_age_group.get(age_group, DEFAULT_MAX_TEAMS_PER_TOURNAMENT)
            games = self.generate_round_robin_games(participants, parallel_games)
            self._record_opponent_history(games)

            tournament = Tournament(
                date=tournament_date,
                arena=arena,
                age_group=age_group,
                teams=participants,
                games=games,
                host_club=host_club,
            )
            plan.tournaments.append(tournament)

        expected_per_month = self._expected_monthly_load(
            start_date.date(), end_date.date(), len(chosen_dates)
        )

        plan.arena_counts = self._arena_counts(plan.tournaments)
        plan.diversity_score = self._diversity_score(plan.tournaments)
        plan.pairwise_matchup_score = self._pairwise_matchup_score(plan.tournaments)
        plan.month_balance_score = self._month_balance_score(expected_per_month)
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

    # ------------------------------------------------------------------
    # Step 1: pick dates spread evenly across the window
    # ------------------------------------------------------------------

    def _pick_spread_dates(
        self,
        free_dates: Sequence[date],
        window_start: date,
        window_end: date,
        age_groups: Sequence[str] = (),
    ) -> List[date]:
        """Pick 10-15 free dates, spread evenly across the season window.

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

        target_count = self.target_tournament_count or self._default_target_count(len(free_dates))
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
                    return spread_penalty + diversity_penalty

                best = min(candidates, key=combined_score)

                ag_index = (age_groups.index(predicted_age_group) + 1) % len(age_groups)
                scheduled_by_date.setdefault(best, []).append(predicted_age_group)
            else:
                best = min(candidates, key=lambda d: abs((d - bucket_center).days))

            chosen.append(best)
            used.add(best)

        return sorted(chosen)

    @staticmethod
    def _default_target_count(num_free_dates: int) -> int:
        """Pick a sensible target tournament count within [MIN, MAX] bounds."""
        return max(MIN_TOURNAMENTS, min(MAX_TOURNAMENTS, num_free_dates))

    # ------------------------------------------------------------------
    # Step 2: assign host arenas/clubs
    # ------------------------------------------------------------------

    def _assign_hosts(self, chosen_dates: Sequence[date]) -> List[str]:
        """Assign a host club to each chosen date.

        Round-robins over the clubs in the roster so every arena gets at
        least one hosted tournament before any arena hosts a second; once
        every club has hosted, falls back to least-recently-hosted.
        """
        clubs = self.roster.clubs()
        if not clubs:
            return ["" for _ in chosen_dates]

        last_hosted_index: Dict[str, int] = {club: -1 for club in clubs}
        assignments: List[str] = []

        for i, _ in enumerate(chosen_dates):
            # Prefer clubs that have never hosted yet, in roster order.
            never_hosted = [club for club in clubs if last_hosted_index[club] == -1]
            if never_hosted:
                host = never_hosted[0]
            else:
                # Least-recently-hosted: smallest last_hosted_index.
                host = min(clubs, key=lambda c: last_hosted_index[c])

            assignments.append(host)
            last_hosted_index[host] = i

        return assignments

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

        Invites the whole age-group roster when it is small enough for a
        sensible round-robin; otherwise picks a subset using a
        least-recently-grouped-together heuristic so that, across the
        season, each team gets varied company rather than always meeting the
        same clubs.
        """
        candidates = self.roster.by_age_group(age_group)
        if not candidates:
            return []

        max_teams = self._max_teams_for(age_group)
        if len(candidates) <= max_teams:
            return list(candidates)

        return self._pick_least_recently_grouped(candidates, max_teams)

    def _max_teams_for(self, age_group: str) -> int:
        """Return the maximum number of teams to invite to a single tournament.

        Explicit per-age-group config (from ``maxTeamsPerTournament`` in
        input.json) takes precedence.  Falls back to a heuristic derived from
        the parallel-games count, then to ``DEFAULT_MAX_TEAMS_PER_TOURNAMENT``.
        """
        explicit = self.max_teams_per_tournament_for_age_group.get(age_group)
        if explicit is not None and explicit > 0:
            return explicit
        parallel_games = self.parallel_games_for_age_group.get(age_group)
        if parallel_games and parallel_games > 0:
            return max(4, min(DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games - 1, parallel_games * 3))
        return DEFAULT_MAX_TEAMS_PER_TOURNAMENT

    def _pick_least_recently_grouped(self, candidates: Sequence[Team], count: int) -> List[Team]:
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
        """
        remaining = list(candidates)
        if not remaining:
            return []

        # Seed with the least-invited team so invitations stay balanced.
        remaining.sort(key=lambda t: (self._invite_counts.get(t.label, 0), candidates.index(t)))
        selected: List[Team] = [remaining.pop(0)]

        while remaining and len(selected) < count:
            def repeat_matchup_score(team: Team) -> int:
                total = 0
                for s in selected:
                    pair = frozenset((team.label, s.label))
                    total += self._opponent_history.get(pair, 0)
                return total

            def overlap_score(team: Team) -> int:
                grouped_with = self._grouped_with.get(team.label, set())
                return sum(1 for s in selected if s.label in grouped_with)

            remaining.sort(
                key=lambda t: (
                    repeat_matchup_score(t),
                    overlap_score(t),
                    self._invite_counts.get(t.label, 0),
                    candidates.index(t),
                )
            )
            selected.append(remaining.pop(0))

        return selected

    def _record_grouping(self, participants: Sequence[Team]) -> None:
        """Record that `participants` were grouped together this tournament."""
        labels = [team.label for team in participants]
        for team in participants:
            self._invite_counts[team.label] = self._invite_counts.get(team.label, 0) + 1
            grouped = self._grouped_with.setdefault(team.label, set())
            grouped.update(label for label in labels if label != team.label)

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
            pair = frozenset((game.home.label, game.away.label))
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
                    pair = frozenset((team_a.label, team_b.label))
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
                    )
                )

            # Rotate all but the first fixed element (standard circle method).
            rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

        return games

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
        """Pairwise-matchup diversity score grounded in `_opponent_history`.

        Reworked from the original co-attendance-based metric to measure
        actual scheduled matchups rather than mere tournament groupings:
        the fraction of all scheduled pairwise games (across `tournaments`)
        that are *first-time* pairings, i.e. the only time that exact pair
        of teams has been scheduled to play each other this season
        (1.0 = every scheduled game is a fresh matchup; lower values
        indicate more repeat matchups). This is equivalent to
        `_pairwise_matchup_score` and the two are kept in sync — see that
        method for the precise definition.
        """
        return self._pairwise_matchup_score(tournaments)

    @staticmethod
    def _pairwise_matchup_score(tournaments: Sequence[Tournament]) -> float:
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
                pair = frozenset((game.home.label, game.away.label))
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