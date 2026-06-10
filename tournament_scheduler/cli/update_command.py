"""--update-tournament CLI mode: modify a generated season plan.

Supports dropping a team from a tournament, moving a tournament to a
different weekend, adding a new tournament, or removing a tournament
entirely — reading from and writing back to the Stage 3 checkpoint.
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
        add_tournament: bool = False,
        age_group: Optional[str] = None,
        add_teams: Optional[str] = None,
        add_date: Optional[str] = None,
        add_arena: Optional[str] = None,
        host_club: Optional[str] = None,
        remove_tournament_id: Optional[str] = None,
        force: bool = False,
        no_cascade: bool = False,
        work_dir: str = ".pipeline",
    ) -> None:
        TournamentOutput.print_header("OPPDATER TURNERING")

        # Resolve work directory (used by all operations)
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

        # --- Validate mutually exclusive operations ---
        operations = sum([
            bool(team_drop),
            bool(new_date),
            bool(add_tournament),
            bool(remove_tournament_id),
        ])
        if operations == 0:
            TournamentOutput.print_error(
                "Angi --team-drop, --new-date, --add-tournament eller --remove-tournament."
            )
            return
        if operations > 1:
            TournamentOutput.print_error(
                "Kan ikke bruke flere operasjoner samtidig. "
                "Velg en av --team-drop, --new-date, --add-tournament eller --remove-tournament."
            )
            return

        result: Optional[UpdateResult] = None

        # --- Add tournament ---
        if add_tournament:
            if not age_group or not add_teams or not add_date or not add_arena:
                TournamentOutput.print_error(
                    "--add-tournament krever --age-group, --add-teams, --add-date og --arena."
                )
                return

            try:
                parsed_add_date = date.fromisoformat(add_date)
            except ValueError:
                TournamentOutput.print_error(
                    f"Ugyldig datoformat '{add_date}'. Bruk YYYY-MM-DD."
                )
                return

            team_labels = [t.strip() for t in add_teams.split(",") if t.strip()]
            if len(team_labels) < 2:
                TournamentOutput.print_error(
                    f"Trenger minst 2 lag for en turnering. Fikk: {team_labels}"
                )
                return

            TournamentOutput.print_info(
                f"Legger til turnering: {age_group} på {parsed_add_date.isoformat()} i {add_arena} "
                f"med {len(team_labels)} lag..."
            )
            result = updater.add_tournament(
                plan=plan,
                age_group=age_group,
                team_labels=team_labels,
                tournament_date=parsed_add_date,
                arena=add_arena,
                host_club=host_club,
                force=force,
            )

        # --- Remove tournament ---
        elif remove_tournament_id:
            TournamentOutput.print_info(f"Fjerner turnering {remove_tournament_id}...")
            result = updater.remove_tournament(plan, remove_tournament_id)

        # --- Team drop ---
        elif team_drop:
            TournamentOutput.print_info(f"Fjerner lag '{team_drop}' fra turnering {tournament_id}...")
            result = updater.drop_team(tournament_id, team_drop, plan=plan)

        # --- Date move ---
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
