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
        """
        self.scheduler = scheduler
        self.roster = roster
        self.club_arenas = club_arenas
        self.parallel_games_for_age_group = parallel_games_for_age_group or {}
        self.target_tournament_count = target_tournament_count

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

        chosen_dates = self._pick_spread_dates(free_dates, start_date.date(), end_date.date())

        plan = SeasonPlan(
            tournaments=[],
            start_date=start_date.date(),
            end_date=end_date.date(),
        )

        age_groups = self.roster.age_groups()
        if not age_groups:
            return plan

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

        plan.arena_counts = self._arena_counts(plan.tournaments)
        plan.diversity_score = self._diversity_score(plan.tournaments)
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
    ) -> List[date]:
        """Pick 10-15 free dates, spread evenly across the season window.

        Buckets the date range into N roughly-equal slices and picks the
        best (closest-to-bucket-center) free date per slice.
        """
        if not free_dates:
            return []

        target_count = self.target_tournament_count or self._default_target_count(len(free_dates))
        target_count = max(1, min(target_count, len(free_dates)))

        total_days = (window_end - window_start).days
        if total_days <= 0 or target_count == 1:
            return list(free_dates[:target_count])

        bucket_span = total_days / target_count
        chosen: List[date] = []
        used: Set[date] = set()

        for i in range(target_count):
            bucket_start = window_start + timedelta(days=int(i * bucket_span))
            bucket_end = window_start + timedelta(days=int((i + 1) * bucket_span))
            bucket_center = bucket_start + (bucket_end - bucket_start) / 2

            candidates = [d for d in free_dates if bucket_start <= d <= bucket_end and d not in used]
            if not candidates:
                # Fall back to the closest unused free date overall.
                candidates = [d for d in free_dates if d not in used]
            if not candidates:
                continue

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
        """Derive a practical round-robin subset size for an age group.

        Driven by the configured parallel-games count where available
        (more parallel sheets/timeslots support more teams in a round-robin
        within a single weekend), otherwise falls back to a sensible default.
        """
        parallel_games = self.parallel_games_for_age_group.get(age_group)
        if parallel_games and parallel_games > 0:
            # Heuristic: each parallel slot can comfortably support a couple
            # of extra teams in a single round-robin weekend.
            return max(4, min(DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games - 1, parallel_games * 3))
        return DEFAULT_MAX_TEAMS_PER_TOURNAMENT

    def _pick_least_recently_grouped(self, candidates: Sequence[Team], count: int) -> List[Team]:
        """Greedily build a subset that minimizes repeat groupings.

        Starts from the team that has been invited least often overall, then
        repeatedly adds the candidate that has been grouped with the
        already-selected teams the fewest times (ties broken by lowest
        overall invite count, then roster order).
        """
        remaining = list(candidates)
        if not remaining:
            return []

        # Seed with the least-invited team so invitations stay balanced.
        remaining.sort(key=lambda t: (self._invite_counts.get(t.label, 0), candidates.index(t)))
        selected: List[Team] = [remaining.pop(0)]

        while remaining and len(selected) < count:
            def overlap_score(team: Team) -> int:
                grouped_with = self._grouped_with.get(team.label, set())
                return sum(1 for s in selected if s.label in grouped_with)

            remaining.sort(
                key=lambda t: (
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
    def generate_round_robin_games(teams: Sequence[Team], parallel_games: int) -> List[Game]:
        """Generate a full round-robin schedule for `teams` using the circle method.

        Every team plays every other team exactly once. Games are grouped
        into rounds (one round = each team plays at most once), and within
        each round games are assigned to `parallel_slot` indices
        `0..min(parallel_games, games_in_round) - 1` so that up to
        `parallel_games` games run concurrently, minimizing the number of
        sequential rounds. Odd team counts get a "bye" each round, per the
        standard circle-method convention (a placeholder team sits out).

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

    @staticmethod
    def _diversity_score(tournaments: Sequence[Tournament]) -> float:
        """A simple diversity score: average fraction of *new* co-participants
        each team encounters across the season (1.0 = every grouping is novel).
        """
        grouped_with: Dict[str, Set[str]] = {}
        novel_total = 0
        encounter_total = 0

        for tournament in tournaments:
            labels = [team.label for team in tournament.teams]
            for team in tournament.teams:
                seen = grouped_with.setdefault(team.label, set())
                others = [label for label in labels if label != team.label]
                novel = [label for label in others if label not in seen]
                novel_total += len(novel)
                encounter_total += len(others)
                seen.update(others)

        if encounter_total == 0:
            return 0.0
        return round(novel_total / encounter_total, 3)
