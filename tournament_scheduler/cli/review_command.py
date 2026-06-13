"""CLI helpers for club review/approval responses."""

from __future__ import annotations

import json
from pathlib import Path

from tournament_scheduler.pipeline.manual_adjustment_workflow import ManualAdjustmentWorkflow
from tournament_scheduler.pipeline.state import PipelineState, StageName
from tournament_scheduler.pipeline.stage4_export import run as run_export
from tournament_scheduler.pipeline.tournament_updater import TournamentUpdater
from tournament_scheduler.review.review_packet_exporter import ReviewPacketResponse
from tournament_scheduler.utils.rich_output import TournamentOutput


class ReviewCommand:
    """Apply club review responses and re-export the season plan."""

    def run(
        self,
        responses: list[str],
        *,
        work_dir: str = ".pipeline",
        export_dir: str = "export",
        timestamped_export: bool = False,
    ) -> int:
        TournamentOutput.print_header("KLUBBREVIEW")

        if not responses:
            TournamentOutput.print_error("Angi minst én --response eller en mappe med response_template.json.")
            return 1

        work_path = Path(work_dir)
        state = PipelineState(str(work_path))
        plan_path = state.checkpoint_path(StageName.PLANNING)
        if not plan_path.exists():
            TournamentOutput.print_error(
                f"Ingen Stage 3-plan funnet i {work_path}/. Kjør pipelinen først."
            )
            return 1

        updater = TournamentUpdater(state=state)
        workflow = ManualAdjustmentWorkflow(state=state, updater=updater)

        try:
            plan = workflow.load_plan()
        except ValueError as exc:
            TournamentOutput.print_error(str(exc))
            return 1

        parsed_responses: list[ReviewPacketResponse] = []
        try:
            for response in responses:
                parsed_responses.append(ReviewPacketResponse.from_path(response))
        except FileNotFoundError as exc:
            TournamentOutput.print_error(f"Fant ikke responsfil: {exc}")
            return 1
        except json.JSONDecodeError as exc:  # type: ignore[name-defined]
            TournamentOutput.print_error(f"Ugyldig JSON i responsfil: {exc}")
            return 1

        change_requests = [resp for resp in parsed_responses if resp.is_change_request]
        for resp in parsed_responses:
            label = resp.club or "ukjent klubb"
            if resp.is_change_request:
                TournamentOutput.print_info(f"{label}: endringsønske mottatt")
            else:
                TournamentOutput.print_success(f"{label}: godkjent")

        if not change_requests:
            TournamentOutput.print_success("Alle klubber godkjente planen — ingen replanning nødvendig.")
            return 0

        requested: dict[str, list[str]] = {}
        for response in change_requests:
            requested = ManualAdjustmentWorkflow.merge_manual_adjustments(
                requested,
                response.as_manual_adjustments(),
            )

        if not any(requested.values()):
            TournamentOutput.print_warning(
                "Endringsforespørselen inneholder ingen konkrete justeringer — bruk responsmalen til å fylle inn låste/bannlyste datoer eller vertsvalg."
            )
            return 1

        plan.manual_adjustments = ManualAdjustmentWorkflow.merge_manual_adjustments(
            plan.manual_adjustments,
            requested,
        )

        try:
            result = workflow.apply(plan)
        except ValueError as exc:
            TournamentOutput.print_error(str(exc))
            return 1

        if not result.success:
            TournamentOutput.print_error(result.summary_nb)
            return 1

        log_path = updater.persist_update(plan, result)

        TournamentOutput.print_success("Klubbrespons brukt og plan oppdatert!")
        TournamentOutput.print_info(result.summary_nb)
        TournamentOutput.print_info(f"Plan oppdatert: {work_path}/stage3_plan.json")
        if log_path:
            TournamentOutput.print_info(f"Logget til: {log_path}")

        TournamentOutput.print_info("\nRe-eksporterer...")
        try:
            export_result = run_export(
                state.read_stage(StageName.PLANNING),
                state=state,
                export_dir=export_dir,
                strict=True,
                timestamped_export=timestamped_export,
            )
        except Exception as exc:  # noqa: BLE001
            TournamentOutput.print_error(f"Eksport feilet: {exc}")
            return 1

        files = export_result.get("output_files", {})
        TournamentOutput.print_success(f"{len(files)} fil(er) eksportert")
        for label, path in files.items():
            TournamentOutput.print_info(f"  → {path}")

        return 0
