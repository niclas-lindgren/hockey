"""--generate-season CLI mode: build and export a full-season tournament plan."""

import sys
from datetime import datetime

from tournament_scheduler.club_registry import build_data_source, known_clubs, missing_clubs
from tournament_scheduler.conflict_checkers.holiday_checker import HolidayConflictChecker
from tournament_scheduler.conflict_checkers.tournament_checker import TournamentConflictChecker
from tournament_scheduler.roster_loader import RosterConfigError, RosterLoader
from tournament_scheduler.scheduler import TournamentScheduler

from tournament_scheduler.season_planner import SeasonPlanner
from tournament_scheduler.utils.date_parser import DateParser
from tournament_scheduler.utils.rich_output import TournamentOutput


class SeasonCommand:
    """Runs the full-season schedule generation flow (--generate-season)."""

    def run(self, args, default_start_date: datetime, default_end_date: datetime) -> None:
        TournamentOutput.print_header("GENERER SESONGPLAN")

        season_start, season_end = self._resolve_season_window(args, default_start_date, default_end_date)
        TournamentOutput.print_info(
            f"Sesongvindu: {season_start.strftime('%Y-%m-%d')} til {season_end.strftime('%Y-%m-%d')}"
        )

        try:
            roster, federation_defaults = RosterLoader.load_with_defaults(args.roster_file)
        except RosterConfigError as exc:
            TournamentOutput.print_error(str(exc))
            sys.exit(1)

        TournamentOutput.print_success(
            f"Lastet inn {len(roster.teams)} lag fordelt på {len(roster.clubs())} klubber "
            f"og {len(roster.age_groups())} aldersgrupper"
        )

        parallel_games_for_age_group = federation_defaults.get('parallelGames', {})
        max_teams_per_tournament = federation_defaults.get('maxTeamsPerTournament', {})
        max_games_per_team = federation_defaults.get('maxGamesPerTeam', {})

        sources, club_arenas = self._build_calendar_sources()
        if not sources:
            TournamentOutput.print_error("Ingen klubber med kjente kalenderkilder funnet — kan ikke generere sesongplan.")
            sys.exit(1)

        scheduler = TournamentScheduler(
            calendar_sources=sources,
            conflict_checkers=self._build_conflict_checkers(sources),
            date_parser=DateParser()
        )

        planner = SeasonPlanner(
            scheduler=scheduler,
            roster=roster,
            club_arenas=club_arenas,
            parallel_games_for_age_group=parallel_games_for_age_group,
            max_teams_per_tournament_for_age_group=max_teams_per_tournament,
            max_games_per_team_for_age_group=max_games_per_team,
        )

        TournamentOutput.print_info("Bygger sesongplan (dette kan ta litt tid)...")
        plan = planner.build_plan(season_start, season_end)

        if not plan.tournaments:
            TournamentOutput.print_no_dates_found()
            return

        self._print_plan(plan)

        if args.export_excel:
            from tournament_scheduler.excel.plan_exporter import SeasonPlanExporter
            SeasonPlanExporter().export(plan, args.export_excel)

    def _resolve_season_window(self, args, default_start_date, default_end_date):
        season_start = default_start_date
        season_end = default_end_date
        if args.season_start:
            season_start = DateParser.parse(args.season_start)
            if not season_start:
                TournamentOutput.print_error(f"Ugyldig sesongstart-dato '{args.season_start}'. Bruk YYYY-MM-DD.")
                sys.exit(1)
        if args.season_end:
            season_end = DateParser.parse(args.season_end)
            if not season_end:
                TournamentOutput.print_error(f"Ugyldig sesongslutt-dato '{args.season_end}'. Bruk YYYY-MM-DD.")
                sys.exit(1)
        return season_start, season_end

    def _build_calendar_sources(self):
        sources = []
        club_arenas = {}
        for entry in known_clubs():
            source = build_data_source(entry)
            if source is not None:
                sources.append(source)
                club_arenas[entry.club] = entry.arena

        for entry in missing_clubs():
            TournamentOutput.print_warning(
                f"Hopper over {entry.club} — kalenderkilde mangler ennå ({entry.note or 'ingen URL'})"
            )

        return sources, club_arenas

    def _build_conflict_checkers(self, sources):
        checkers = [HolidayConflictChecker()]
        for source in sources:
            try:
                checkers.append(TournamentConflictChecker(source))
            except Exception:
                pass
        return checkers

    def _print_plan(self, plan):
        TournamentOutput.print_season_overview(plan)
        for tournament in sorted(plan.tournaments, key=lambda t: t.date):
            TournamentOutput.print_tournament_schedule(tournament)
        TournamentOutput.print_diversity_summary(plan)
