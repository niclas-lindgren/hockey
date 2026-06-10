#!/usr/bin/env python3
"""
Hockey Tournament Scheduler
Finds optimal weekend dates for hockey tournaments by analyzing conflicts from multiple sources.
"""

import argparse
import sys
from datetime import datetime, timedelta

from tournament_scheduler.cli.reschedule_command import RescheduleCommand
from tournament_scheduler.cli.scheduling_command import SchedulingCommand
from tournament_scheduler.cli.season_command import SeasonCommand
from tournament_scheduler.cli.update_command import UpdateCommand
from tournament_scheduler.utils.date_parser import DateParser


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Find optimal weekend dates for hockey tournaments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --teams "Team A,Team B" --start-date 2025-01-01 --end-date 2025-06-30
  %(prog)s --excel-file tournaments.xlsx --teams "Vikings,Bears"
        '''
    )

    parser.add_argument('--teams', type=str, default='',
                        help='Comma-separated list of team names to filter conflicts')
    parser.add_argument('--excel-file', type=str,
                        help='Path to Excel file with existing tournament dates')
    parser.add_argument('--start-date', type=str,
                        help='Start date (YYYY-MM-DD), default: today')
    parser.add_argument('--end-date', type=str,
                        help='End date (YYYY-MM-DD), default: 6 months from start')
    parser.add_argument('--reschedule', type=str,
                        help='Reschedule tournament from this date (YYYY-MM-DD). Requires --excel-file.')
    parser.add_argument('--generate-season', action='store_true',
                        help='Generate a full-season tournament schedule across the configured club roster.')
    parser.add_argument('--roster-file', type=str,
                        help='Path to a roster config file (JSON or YAML) listing clubs/teams/age-groups '
                             '(e.g. {"Jar": {"Jar 1": "U10", "Jar 2": "U11"}}) for --generate-season.')
    parser.add_argument('--season-start', type=str,
                        help='Season start date (YYYY-MM-DD) for --generate-season, default: --start-date or today.')
    parser.add_argument('--season-end', type=str,
                        help='Season end date (YYYY-MM-DD) for --generate-season, default: --end-date or +6 months.')
    parser.add_argument('--parallel-games-config', type=str,
                        help='Path to a parallel-games config file (JSON/YAML) for --generate-season.')
    parser.add_argument('--export-excel', type=str,
                        help='Path to write an .xlsx export of the generated season plan (used with --generate-season).')
    parser.add_argument('--export-csv', type=str,
                        help='Path to write a CSV export of the generated season plan (used with --generate-season).')

    # Tournament update flags
    parser.add_argument('--update-tournament', type=str,
                        help='ID for turneringen som skal oppdateres i sesongplanen. Bruk med --team-drop eller --new-date.')
    parser.add_argument('--team-drop', type=str,
                        help='Fjern et lag fra turneringen (lagets label, f.eks. "Jar 1"). Krever --update-tournament.')
    parser.add_argument('--new-date', type=str,
                        help='Ny dato for turneringen (YYYY-MM-DD). Krever --update-tournament.')
    parser.add_argument('--force', action='store_true',
                        help='Tving flytting av turnering selv om det er konflikter.')
    parser.add_argument('--no-cascade', action='store_true',
                        help='Ikke kaskader til andre turneringer ved datoflytting.')
    parser.add_argument('--work-dir', type=str, default='.pipeline',
                        help='Pipeline work directory (standard: .pipeline).')

    return parser


def _parse_date_arg(value: str, label: str) -> datetime:
    parsed = DateParser.parse(value)
    if not parsed:
        print(f"Error: Invalid {label} date format '{value}'. Use YYYY-MM-DD format.", file=sys.stderr)
        sys.exit(1)
    return parsed


def _resolve_date_range(args) -> tuple[datetime, datetime]:
    start_date = _parse_date_arg(args.start_date, 'start') if args.start_date else datetime.now()
    end_date = _parse_date_arg(args.end_date, 'end') if args.end_date else start_date + timedelta(days=180)
    return start_date, end_date


def _validate_args(args) -> None:
    if args.reschedule and not args.excel_file:
        print("Error: Excel file is required when using --reschedule", file=sys.stderr)
        print("Usage: --reschedule 2026-01-17 --excel-file schedule.xlsx", file=sys.stderr)
        sys.exit(1)

    if args.generate_season and not args.roster_file:
        print("Error: --roster-file is required when using --generate-season", file=sys.stderr)
        print("Usage: --generate-season --roster-file roster.json --season-start 2026-10-01 --season-end 2027-04-30", file=sys.stderr)
        sys.exit(1)

    if args.update_tournament:
        if not args.team_drop and not args.new_date:
            print("Error: --team-drop or --new-date is required when using --update-tournament", file=sys.stderr)
            print("Usage: --update-tournament <ID> --team-drop \"Jar 1\"", file=sys.stderr)
            print("       --update-tournament <ID> --new-date 2027-02-20", file=sys.stderr)
            sys.exit(1)

        if args.team_drop and args.new_date:
            print("Error: --team-drop and --new-date cannot be used together", file=sys.stderr)
            sys.exit(1)


def main():
    """Main CLI entry point — parses arguments and dispatches to the matching command."""
    args = build_arg_parser().parse_args()
    _validate_args(args)
    start_date, end_date = _resolve_date_range(args)

    if args.generate_season:
        SeasonCommand().run(args, start_date, end_date)
        return

    if args.update_tournament:
        UpdateCommand().run(
            tournament_id=args.update_tournament,
            team_drop=args.team_drop,
            new_date=args.new_date,
            force=args.force,
            no_cascade=args.no_cascade,
            work_dir=args.work_dir,
        )
        return

    if args.reschedule:
        reschedule_date = _parse_date_arg(args.reschedule, 'reschedule')
        RescheduleCommand().run(args, reschedule_date, start_date, end_date)
        return

    SchedulingCommand().run(args, start_date, end_date)


if __name__ == '__main__':
    main()
