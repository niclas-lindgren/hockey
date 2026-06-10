"""--generate-season CLI mode: build and export a full-season tournament plan."""

import sys
from datetime import datetime
from pathlib import Path

from tournament_scheduler.club_registry import build_data_source, known_clubs, missing_clubs
from tournament_scheduler.conflict_checkers.holiday_checker import HolidayConflictChecker
from tournament_scheduler.conflict_checkers.tournament_checker import TournamentConflictChecker
from tournament_scheduler.roster_loader import RosterConfigError, RosterLoader
from tournament_scheduler.scheduler import TournamentScheduler

from tournament_scheduler.season_planner import SeasonPlanner
from tournament_scheduler.utils.date_parser import DateParser
from tournament_scheduler.club_distances import furthest_traveling_team
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
        max_club_teams = federation_defaults.get('maxClubTeamsPerTournament', 2)
        if hasattr(args, 'max_club_teams') and args.max_club_teams is not None:
            max_club_teams = args.max_club_teams

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
            max_club_teams_per_tournament=max_club_teams,
        )

        TournamentOutput.print_info("Bygger sesongplan (dette kan ta litt tid)...")
        plan = planner.build_plan(season_start, season_end)

        if not plan.tournaments:
            TournamentOutput.print_no_dates_found()
            return

        self._print_plan(plan)

        self._print_club_load_warnings(planner)
        self._print_travel_warnings(plan)

        if args.export_excel:
            from tournament_scheduler.excel.plan_exporter import SeasonPlanExporter
            SeasonPlanExporter().export(plan, args.export_excel)

        if args.export_csv:
            from tournament_scheduler.csv.csv_exporter import CsvExporter
            games_path, overview_path = CsvExporter().export(plan, args.export_csv)
            TournamentOutput.print_success(f"CSV-eksport: {games_path}")
            TournamentOutput.print_success(f"CSV-oversikt: {overview_path}")

        if args.export_ical:
            from tournament_scheduler.ical.ical_exporter import ICalExporter
            exporter = ICalExporter()
            ical_path = exporter.export_tournament_summary(
                plan, args.export_ical,
                age_group_filter=args.ical_age_group,
            )
            TournamentOutput.print_success(f"iCal-eksport: {ical_path}")

            if args.ical_per_club:
                ical_dir = Path(args.export_ical).parent
                ical_stem = Path(args.export_ical).stem
                clubs = sorted({team.club for tournament in plan.tournaments for team in tournament.teams})
                for club in clubs:
                    club_path = str(ical_dir / f"{ical_stem}_{club}.ics")
                    exporter.export_tournament_summary(
                        plan, club_path,
                        age_group_filter=args.ical_age_group,
                        club=club,
                    )
                    TournamentOutput.print_success(f"  → {club}: {club_path}")

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

    @staticmethod
    def _print_club_load_warnings(planner) -> None:
        """Print warnings for clubs with too many teams in the same tournament."""
        warnings = planner.club_load_warnings
        if not warnings:
            return
        TournamentOutput.print_warning(
            f"Advarsel — {len(warnings)} tilfelle(r) der en klubb har flere lag "
            f"enn grensen ({planner.max_club_teams_per_tournament}) i samme turnering:"
        )
        for club, age_group, date_str, count in warnings:
            TournamentOutput.print_warning(
                f"  {club} ({age_group}, {date_str}): {count} lag"
            )

    @staticmethod
    def _print_travel_warnings(plan) -> None:
        """Print information about the furthest-traveling teams."""
        # The per-tournament travel info is already shown in
        # print_tournament_schedule. Here we surface the longest
        # single-leg trip in the entire plan.
        longest_team = None
        longest_km = 0
        for t in plan.tournaments:
            travel = furthest_traveling_team(t)
            if travel is not None:
                team, km = travel
                if km > longest_km:
                    longest_team = team
                    longest_km = km
        if longest_team:
            TournamentOutput.print_info(
                f"Lengste enkeltreise i sesongen: {longest_team.label} ({longest_km} km)"
            )
