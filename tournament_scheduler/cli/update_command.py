"""--update-tournament CLI mode: modify a generated season plan.

Supports dropping a team from a tournament or moving a tournament to a
different weekend, reading from and writing back to the Stage 3 checkpoint.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from tournament_scheduler.pipeline.state import PipelineState
from tournament_scheduler.pipeline.tournament_updater import TournamentUpdater, UpdateResult
from tournament_scheduler.utils.rich_output import TournamentOutput


class UpdateCommand:
    """Applies targeted updates to a generated season plan (--update-tournament)."""

    def run(
        self,
        tournament_id: str,
        team_drop: Optional[str] = None,
        new_date: Optional[str] = None,
        force: bool = False,
        no_cascade: bool = False,
        work_dir: str = ".pipeline",
    ) -> None:
        TournamentOutput.print_header("OPPDATER TURNERING")

        if not team_drop and not new_date:
            TournamentOutput.print_error("Angi --team-drop <lag> eller --new-date <YYYY-MM-DD>.")
            return

        if team_drop and new_date:
            TournamentOutput.print_error("Kan ikke bruke --team-drop og --new-date samtidig.")
            return

        # Resolve work directory
        work_path = Path(work_dir)
        if not (work_path / "stage3_plan.json").exists():
            TournamentOutput.print_error(
                f"Ingen Stage 3-plan funnet i {work_path}/. "
                f"Kjør pipelinen (--generate-season) forst."
            )
            return

        state = PipelineState(str(work_path))
        updater = TournamentUpdater(state=state)

        try:
            plan = updater.load_plan()
        except ValueError as exc:
            TournamentOutput.print_error(str(exc))
            return

        TournamentOutput.print_info(
            f"Laster plan med {len(plan.tournaments)} turneringer "
            f"({plan.start_date} til {plan.end_date})"
        )

        result: Optional[UpdateResult] = None

        if team_drop:
            TournamentOutput.print_info(f"Fjerner lag '{team_drop}' fra turnering {tournament_id}...")
            result = updater.drop_team(tournament_id, team_drop, plan=plan)
        elif new_date:
            try:
                parsed_date = date.fromisoformat(new_date)
            except ValueError:
                TournamentOutput.print_error(
                    f"Ugyldig datoformat '{new_date}'. Bruk YYYY-MM-DD."
                )
                return

            TournamentOutput.print_info(
                f"Flytter turnering {tournament_id} til {parsed_date.isoformat()}..."
            )
            result = updater.move_date(
                tournament_id, parsed_date,
                plan=plan,
                force=force,
                cascade=not no_cascade,
            )

        if not result:
            TournamentOutput.print_error("Ingen operasjon utført.")
            return

        if result.success:
            updater.write_updated_checkpoint(plan, log_entry=result)
            log_path = updater.log_update(result)

            TournamentOutput.print_success("Turnering oppdatert!")
            TournamentOutput.print_info(result.summary_nb)
            TournamentOutput.print_info(f"Plan oppdatert: {work_path}/stage3_plan.json")
            if log_path:
                TournamentOutput.print_info(f"Logget til: {log_path}")
        else:
            TournamentOutput.print_error(result.summary_nb)
