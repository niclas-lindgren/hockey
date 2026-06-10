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
    CalendarEvent,
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

# Default start time assigned to generated tournaments when no per-arena/
# per-age-group scheduling is available yet.
DEFAULT_TOURNAMENT_START_TIME = "09:00"


def _cap_at_one_per_club(teams: Sequence[Team]) -> List[Team]:
    """Return at most one team per club from *teams*, keeping first occurrence.

    Used as a fast-path filter on the small-roster case to enforce the hard
    ``max_club_teams_per_tournament`` constraint (no intra-club matchups).
    """
    seen_clubs: set[str] = set()
    result: List[Team] = []
    for team in teams:
        if team.club not in seen_clubs:
            seen_clubs.add(team.club)
            result.append(team)
    return result


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
        max_teams_per_tournament_for_age_group: Optional[Dict[str, int]] = None,
        max_club_teams_per_tournament: int = 1,
        max_game_count_spread: int = 2,
        max_early_finish_gap_days: int = 60,
        division_skill_band: int = 2,
        max_hosting_deviation: int = 1,
        max_month_deviation_ratio: float = 0.5,
        events_by_club: Optional[Dict[str, List[CalendarEvent]]] = None,
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
            round_length_for_age_group: Optional mapping of age group ->
                round length in minutes, used to set each generated
                tournament's `start_time` and compute its duration/end time.
            target_tournament_count: Optional override for how many
                tournaments to propose (default: spread between
                `MIN_TOURNAMENTS` and `MAX_TOURNAMENTS` based on how many
                free dates are available).
            max_teams_per_tournament_for_age_group: Optional mapping of age
                group -> maximum number of teams invited to a single
                tournament. When set for an age group, takes precedence over
                the parallel-games heuristic in `_max_teams_for`.
            max_club_teams_per_tournament: Hard constraint on how many teams
                from the same club can be invited to a single tournament.
                Default 1 — at most one team per club per tournament,
                guaranteeing no intra-club matchups.
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
                `start_time` (and possibly its host arena, via fallback) is
                derived from `TournamentScheduler.find_arena_slot_for_date`
                instead of always using `DEFAULT_TOURNAMENT_START_TIME`.
        """
        self.scheduler = scheduler
        self.roster = roster
        self.club_arenas = club_arenas
        self.parallel_games_for_age_group = parallel_games_for_age_group or {}
        self.round_length_for_age_group = round_length_for_age_group or {}
        self.target_tournament_count = target_tournament_count
        self.max_teams_per_tournament_for_age_group = max_teams_per_tournament_for_age_group or {}
        self.max_club_teams_per_tournament = max_club_teams_per_tournament
        self.max_game_count_spread = max_game_count_spread
        self.max_early_finish_gap_days = max_early_finish_gap_days
        self.division_skill_band = division_skill_band
        self.max_hosting_deviation = max_hosting_deviation

        # Maps team label -> skill_level (int 1-10) for teams that have one.
        # Used by the skill-level proximity penalty in participant selection.
        self._team_skill_levels: Dict[str, int] = {
            team.label: team.skill_level
            for team in roster.teams
            if team.skill_level is not None
        }

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
        # Tracks the date of each team's most recent game. Used for
        # early-finish detection.
        self._team_last_date: Dict[str, date] = {}
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
        # Month-load warnings collected after build_plan runs.
        self._month_load_warnings: List[Tuple[int, int, int, float, float]] = []

        self.max_month_deviation_ratio = max_month_deviation_ratio
        self.events_by_club = events_by_club or {}

        # Fallback-host substitutions made during the most recent
        # `build_plan` run, for surfacing in the rules/decisions report.
        # Each entry is `(date, age_group, original_host_club, fallback_host_club)`.
        self._fallback_host_substitutions: List[Tuple[date, str, str, str]] = []

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
        self._fallback_host_substitutions = []

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

            actual_host_club = host_club
            actual_arena = arena
            start_time = DEFAULT_TOURNAMENT_START_TIME

            slot = self._find_slot_for_tournament(
                tournament_date, host_club, age_group, games
            )
            if slot is not None:
                slot_host_club, slot_start, _slot_end = slot
                start_time = slot_start
                if slot_host_club != host_club:
                    actual_host_club = slot_host_club
                    actual_arena = self.club_arenas.get(slot_host_club, slot_host_club)
                    self._fallback_host_substitutions.append(
                        (tournament_date, age_group, host_club, slot_host_club)
                    )

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
            start_date.date(), end_date.date(), len(chosen_dates)
        )

        plan.arena_counts = self._arena_counts(plan.tournaments)
        plan.diversity_score = self._diversity_score(plan.tournaments)
        plan.pairwise_matchup_score = self._pairwise_matchup_score(plan.tournaments)
        plan.month_balance_score = self._month_balance_score(expected_per_month)

        # Compute per-team game counts and last-game dates.
        self._compute_game_counts(plan.tournaments)
        plan.team_game_counts = dict(self._team_game_counts)
        plan.team_last_game_dates = dict(self._team_last_date)
        if self._team_game_counts:
            plan.game_count_spread = max(self._team_game_counts.values()) - min(self._team_game_counts.values())

        # Scan for club-load violations and record warnings.
        self._scan_club_load_warnings(plan.tournaments)
        # Scan for hosting-imbalance warnings.
        self._scan_hosting_warnings(plan)
        # Scan for game-count spread violations and early-finish issues.
        self._scan_game_count_warnings(plan.start_date, plan.end_date)
        # Scan for month-load imbalance warnings.
        self._scan_month_load_warnings(expected_per_month, plan.start_date)

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
        """Find a time-of-day slot for a tournament, if calendar data allows.

        Computes the required duration from `round_length_for_age_group` and
        the number of rounds in *games* (mirroring
        `Tournament.duration_minutes`), then delegates to
        `TournamentScheduler.find_arena_slot_for_date`.

        Returns `None` (leaving the caller to use
        `DEFAULT_TOURNAMENT_START_TIME` and the originally-assigned host)
        when no calendar data is available, no round length is configured
        for *age_group*, there are no games yet, or no candidate arena has a
        fitting slot.
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
    def month_load_warnings(self) -> List[Tuple[int, int, int, float, float]]:
        """Month-load imbalance warnings after ``build_plan``.

        Each entry is ``(year, month, count, expected, deviation_ratio)``
        where ``deviation_ratio`` is (count - expected) / expected —
        positive for over-loaded months, negative for under-loaded months.

        Only months exceeding ``max_month_deviation_ratio`` are included.
        """
        return list(self._month_load_warnings)

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
                    self._team_game_counts[team.label] = (
                        self._team_game_counts.get(team.label, 0) + 1
                    )
                    last = self._team_last_date.get(team.label)
                    if last is None or tournament.date > last:
                        self._team_last_date[team.label] = tournament.date

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
            for label, count in self._team_game_counts.items():
                if count == max_count or count == min_count:
                    self._game_count_warnings.append((label, count, spread, "spread"))

        # Early-finish warnings
        if window_end is not None and self._team_last_date:
            for label, last_date in self._team_last_date.items():
                gap = (window_end - last_date).days
                if gap > self.max_early_finish_gap_days:
                    self._game_count_warnings.append(
                        (label, self._team_game_counts.get(label, 0), gap, "early_finish")
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
        tournament where a club has more than ``max_club_teams_per_tournament``
        teams participating.  This should never fire now that the constraint
        is hard (``_pick_least_recently_grouped`` and ``_select_participants``
        both enforce it), but is retained as a defensive check.
        """
        max_club = self.max_club_teams_per_tournament
        for t in tournaments:
            club_counts: Dict[str, int] = {}
            for team in t.teams:
                club_counts[team.club] = club_counts.get(team.club, 0) + 1
            for club, count in club_counts.items():
                if count > max_club:
                    self._club_load_warnings.append(
                        (club, t.age_group, t.date.isoformat(), count)
                    )

    def _scan_hosting_warnings(self, plan: SeasonPlan) -> None:
        """Scan completed tournament hosting for proportional-imbalance violations.

        Compares each club's actual hosting count to its proportional
        target (derived from team-count share of the roster) and appends
        a human-readable warning for every club whose deviation exceeds
        ``max_hosting_deviation``.
        """
        clubs = self.roster.clubs()
        if not clubs or not plan.tournaments:
            return

        # Count teams per club from the roster.
        club_team_counts: Dict[str, int] = {}
        for team in self.roster.teams:
            club_team_counts[team.club] = club_team_counts.get(team.club, 0) + 1
        total_teams = sum(club_team_counts.values()) or 1

        num_tournaments = len(plan.tournaments)
        actual_hosting: Dict[str, int] = {}
        for tournament in plan.tournaments:
            host = tournament.host_club
            if host:
                actual_hosting[host] = actual_hosting.get(host, 0) + 1

        for club in clubs:
            team_count = club_team_counts.get(club, 0)
            expected = team_count / total_teams * num_tournaments
            actual = actual_hosting.get(club, 0)
            deviation = abs(actual - expected)
            if deviation > self.max_hosting_deviation:
                self._hosting_warnings.append(
                    f"{club} har {actual} hjemmeturnering(er) av {num_tournaments} "
                    f"(forventet ~{expected:.1f} basert på {team_count} lag, "
                    f"avvik {deviation:.1f} > {self.max_hosting_deviation})"
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
                report.append({
                    "regel": f"Parallelle kamper for {ag}: {pg}",
                    "forklaring": (
                        f"For aldersgruppen {ag} spilles det {pg} kamper samtidig "
                        f"per runde. Dette følger forbundets anbefalinger og påvirker "
                        f"hvor mange lag som inviteres til hver turnering."
                    ),
                    "kategori": "Hard krav",
                })
        else:
            report.append({
                "regel": "Parallelle kamper: ingen spesifisert",
                "forklaring": (
                    "Ingen aldersgrupper har spesifisert antall parallelle kamper. "
                    f"Planleggeren bruker et standard tak på {DEFAULT_MAX_TEAMS_PER_TOURNAMENT} lag "
                    f"per turnering."
                ),
                "kategori": "Hard krav",
            })

        # Per-age-group max teams.
        if self.max_teams_per_tournament_for_age_group:
            for ag, mt in sorted(self.max_teams_per_tournament_for_age_group.items()):
                report.append({
                    "regel": f"Maks lag per turnering for {ag}: {mt}",
                    "forklaring": (
                        f"For {ag} inviteres maksimalt {mt} lag til hver turnering. "
                        f"Dette bestemmes av konfigurasjonen og sikrer at alle lag får "
                        f"spille mot hverandre innenfor tilgjengelig tid."
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

        report.append({
            "regel": f"Minst {MIN_TOURNAMENTS} og maks {MAX_TOURNAMENTS} turneringer per sesong",
            "forklaring": (
                f"Sesongplanen skal inneholde mellom {MIN_TOURNAMENTS} og "
                f"{MAX_TOURNAMENTS} turneringer, avhengig av hvor mange ledige "
                f"helger som finnes i sesongvinduet. Antallet bestemmes automatisk "
                f"basert på en andel av tilgjengelige helger."
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

        Every club hosts at least one tournament before any club hosts a
        second time.  After that initial round, hosting is assigned in
        proportion to each club's team count -- clubs with more teams
        host proportionally more tournaments.  This prevents a club like
        Jar (7 teams) from hosting zero home tournaments while a
        single-team club hosts one.
        """
        clubs = self.roster.clubs()
        if not clubs:
            return ["" for _ in chosen_dates]

        # Count teams per club from the roster.
        club_team_counts: Dict[str, int] = {}
        for team in self.roster.teams:
            club_team_counts[team.club] = club_team_counts.get(team.club, 0) + 1
        total_teams = sum(club_team_counts.values()) or 1

        num_dates = len(chosen_dates)

        # Compute proportional targets using largest-remainder (Hare quota)
        # so the rounded integers sum exactly to num_dates.
        raw_targets: Dict[str, float] = {}
        for club in clubs:
            raw_targets[club] = club_team_counts.get(club, 0) / total_teams * num_dates

        targets: Dict[str, int] = {}
        remainders: List[Tuple[float, str]] = []
        assigned = 0
        for club in clubs:
            t = raw_targets[club]
            rounded = int(t)
            targets[club] = rounded
            assigned += rounded
            remainders.append((t - rounded, club))

        remainders.sort(key=lambda x: -x[0])
        for _ in range(num_dates - assigned):
            if remainders:
                club = remainders.pop(0)[1]
                targets[club] += 1

        actual_counts: Dict[str, int] = {club: 0 for club in clubs}
        last_hosted_index: Dict[str, int] = {club: -1 for club in clubs}
        assignments: List[str] = []

        for i, _ in enumerate(chosen_dates):
            ng_hosted = [club for club in clubs if last_hosted_index[club] == -1]
            if ng_hosted:
                # Phase 1: every club hosts at least once before any
                # repeats.  Among never-hosted clubs, prefer those with
                # the highest proportional target (more teams -> host
                # earlier).
                host = max(ng_hosted, key=lambda c: targets.get(c, 0))
            else:
                # Phase 2: pick the club furthest below its proportional
                # target.  If all clubs are at or above target, fall back
                # to least-recently-hosted.
                deficit_clubs = [
                    c for c in clubs
                    if actual_counts[c] < targets.get(c, 0)
                ]
                if deficit_clubs:
                    host = max(
                        deficit_clubs,
                        key=lambda c: targets.get(c, 0) - actual_counts[c],
                    )
                else:
                    host = min(clubs, key=lambda c: last_hosted_index[c])

            assignments.append(host)
            last_hosted_index[host] = i
            actual_counts[host] = actual_counts.get(host, 0) + 1

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

        Enforces the hard ``max_club_teams_per_tournament`` constraint:
        at most one team per club per tournament. Invites the whole
        age-group roster when it is small enough for a sensible
        round-robin and club diversity allows it; otherwise picks a
        subset using a least-recently-grouped-together heuristic.
        """
        candidates = self.roster.by_age_group(age_group)
        if not candidates:
            return []

        max_teams = self._max_teams_for(age_group)
        if len(candidates) <= max_teams:
            # Enforce club constraint even on the small-roster fast path.
            return _cap_at_one_per_club(candidates)

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
            return max(4, min(DEFAULT_MAX_TEAMS_PER_TOURNAMENT + parallel_games, parallel_games * 3))
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

        Enforces the hard ``max_club_teams_per_tournament`` constraint:
        teams from a club that already has a team in the selected set are
        excluded entirely.  If that leaves no candidates at all, falls back
        to the soft penalty to avoid deadlock.
        """
        max_club = self.max_club_teams_per_tournament
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

            # Hard club constraint: exclude teams from clubs already
            # represented in the selected set.  Falls back to soft penalty
            # when no candidates remain after filtering.
            hard_filtered: List[Team] = [
                t for t in remaining
                if sum(1 for s in selected if s.club == t.club) < max_club
            ]
            eligible = hard_filtered if hard_filtered else remaining

            # Club-load penalty for the fallback case (soft): push down
            # candidates from clubs that already have max_club teams in
            # the selected set.
            def club_penalty(team: Team) -> int:
                club_count = sum(1 for s in selected if s.club == team.club)
                if club_count >= max_club:
                    return club_count * 100  # outweighs typical match-up scores
                return 0

            # Skill-level proximity penalty: prefer candidates whose skill
            # level is within `division_skill_band` of the selected set's
            # median skill level.  Unrated teams (no skill_level) are never
            # penalised — they are treated as universally adjacent.
            def skill_penalty(team: Team) -> int:
                selected_levels = [
                    self._team_skill_levels[s.label]
                    for s in selected
                    if s.label in self._team_skill_levels
                ]
                if not selected_levels:
                    return 0  # no reference level yet
                if team.label not in self._team_skill_levels:
                    return 0  # unrated team — no filter
                median = sorted(selected_levels)[len(selected_levels) // 2]
                dist = abs(team.skill_level - median)
                if dist <= self.division_skill_band:
                    return 0
                return (dist - self.division_skill_band) * 100

            eligible.sort(
                key=lambda t: (
                    skill_penalty(t),
                    club_penalty(t),
                    repeat_matchup_score(t),
                    overlap_score(t),
                    self._invite_counts.get(t.label, 0),
                    candidates.index(t),
                )
            )
            chosen = eligible.pop(0)
            remaining.remove(chosen)
            selected.append(chosen)

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
                # Safety filter: skip intra-club matchups (belt-and-suspenders
                # guard alongside the hard constraint in participant selection).
                if home is not None and away is not None and home.club == away.club:
                    continue
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
        """Opponent-variety diversity score grounded in `_opponent_history`.

        Distinct from `_pairwise_matchup_score` (which measures how many
        *games* are first-time pairings). This metric instead measures, per
        team, how much of its eligible opponent pool it has actually faced
        this season:

        For each team that has played at least one game this season (i.e.
        appears in at least one pair recorded in `_opponent_history`), count
        its distinct opponents so far and divide by the number of "available
        opponents" — other teams in the same age group, excluding teams from
        its own club (since `max_club_teams_per_tournament=1` means
        intra-club matchups never occur).

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

        teams_by_label = {team.label: team for team in self.roster.teams}

        ratios = []
        for label, faced in opponents_faced.items():
            team = teams_by_label.get(label)
            if team is None:
                continue
            available = [
                other.label
                for other in self.roster.teams
                if other.label != label
                and other.age_group == team.age_group
                and other.club != team.club
            ]
            if not available:
                continue
            ratios.append(len(faced) / len(available))

        if not ratios:
            return 0.0
        return round(sum(ratios) / len(ratios), 3)

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