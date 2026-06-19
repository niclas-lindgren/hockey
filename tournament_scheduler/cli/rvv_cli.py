"""
``rvv-miniputt`` — unified CLI for the RVV Miniputt tournament scheduler pipeline.

Provides the commands referenced by the HTML calendar viewer, scraper tools,
and pipeline logs::

    rvv-miniputt status                 Show checkpoint/log status
    rvv-miniputt calendars              Regenerate calendar HTML from cache
    rvv-miniputt calendars --refresh    Full re-scrape: clear caches, scrape, regenerate
    rvv-miniputt run                    Full pipeline: stages 1→4 + HTML views
    rvv-miniputt logs                   Show structured pipeline run logs
    rvv-miniputt cancel                 Cancel a tournament and suggest/reschedule makeup dates
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from rich.console import Console

from .args import build_parser as _build_parser
from .pipeline_orchestrator import _cmd_calendars, _cmd_run, _cmd_scrape, _cmd_scrape_llm
from .recovery_cli import _cmd_recovery_inject, _cmd_recovery_targets
from .reporting import _cmd_logs, _cmd_status

_console = Console()

# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def _cmd_cancel(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt cancel`` — cancellation and rain-check workflow."""
    from ..pipeline.state import PipelineState
    from ..pipeline.cancellation_workflow import CancellationWorkflow

    work_dir = args.work_dir
    state = PipelineState(work_dir)
    wf = CancellationWorkflow(state)

    # Load the plan first to verify we have something to work with.
    try:
        plan = wf.load_plan()
    except ValueError as exc:
        _console.print(f"[red]✗[/red] {exc}")
        return 1

    # --- No tournament ID: list available tournaments ---
    if not args.tournament_id:
        _console.print("[bold]Turneringer i sesongplanen:[/bold]\n")
        for t in plan.tournaments:
            status = ""
            if t.cancelled:
                status = f" [red](AVLYST: {t.cancellation_reason or 'ingen grunn'})[/red]"
            _console.print(
                f"  [cyan]{t.id}[/cyan]  {t.date.isoformat()}  "
                f"{t.age_group:5s}  {t.arena:20s}  "
                f"{len(t.teams)} lag{status}"
            )
        _console.print(
            f"\nBruk [bold]rvv-miniputt cancel --tournament-id <id> --reason \"...\"[/bold]"
        )
        return 0

    tid = args.tournament_id

    # --- Cancel the tournament ---
    try:
        tournament = wf._find_tournament(plan, tid)
    except ValueError as exc:
        _console.print(f"[red]✗[/red] {exc}")
        return 1

    if args.reason:
        reason = args.reason
    else:
        _console.print(
            f"[bold]Avlys turnering {tid}[/bold] "
            f"({tournament.age_group}, {tournament.arena}, {tournament.date.isoformat()})"
        )
        reason = _console.input("  Årsak: ").strip()
        if not reason:
            _console.print("[red]✗[/red] Avbrutt — ingen grunn oppgitt.")
            return 1

    cancel_result = wf.mark_cancelled(tid, reason, plan=plan)

    if not cancel_result.success:
        _console.print(f"[yellow]⚠[/yellow] {cancel_result.summary_nb}")
        return 1

    _console.print(f"[green]✓[/green] {cancel_result.summary_nb}")

    # --- Write the plan checkpoint ---
    wf.write_plan(plan, log_entry=cancel_result)
    wf.log_cancellation(cancel_result)

    # --- Handle makeup date ---
    if args.makeup_date:
        try:
            new_date = datetime.strptime(args.makeup_date, "%Y-%m-%d").date()
        except ValueError:
            _console.print(
                f"[red]✗[/red] Ugyldig datoformat '{args.makeup_date}'. Bruk YYYY-MM-DD."
            )
            return 1

        _console.print(f"\n[bold]Flytter til makeup-dato: {new_date.isoformat()}[/bold]")
        move_result = wf.apply_makeup(
            tid, new_date, plan=plan, force=args.force, cascade=True
        )

        if not move_result.success:
            _console.print(f"[red]✗[/red] {move_result.summary_nb}")
            return 1

        _console.print(f"[green]✓[/green] {move_result.summary_nb}")
        wf.write_plan(plan, log_entry=move_result)
    else:
        # Show suggested makeup dates
        _console.print("\n[bold]Foreslåtte makeup-datoer:[/bold]")
        suggestions = wf.suggest_makeup_dates(tournament, plan)

        if not suggestions:
            _console.print(
                "  [dim]Ingen ledige helger funnet i sesongvinduet.[/dim]"
            )
        else:
            for s in suggestions:
                day_nb = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
                day = day_nb[s.date.weekday()]
                delta = f"+{s.days_from_original}d" if s.days_from_original >= 0 else f"{s.days_from_original}d"
                _console.print(
                    f"  [cyan]{s.date.isoformat()}[/cyan] ({day}, {delta})"
                )
                for c in s.conflicts:
                    _console.print(f"    [dim]Advarsel: {c['reason']}[/dim]")

            _console.print(
                f"\nBruk [bold]rvv-miniputt cancel --tournament-id {tid} "
                f"--makeup-date <dato>[/bold] for å velge en makeup-dato."
            )

    # --- Re-export ---
    if not args.no_export:
        _console.print("\n[bold]Re-eksporterer...[/bold]")
        try:
            export_result = wf.re_export(
                export_dir=args.export_dir,
            )
            files = export_result.get("output_files", {})
            _console.print(f"  [green]✓[/green] {len(files)} fil(er) eksportert")
            for label, path in files.items():
                _console.print(f"    → {path}")
        except Exception as exc:
            _console.print(f"  [red]✗[/red] Eksport feilet: {exc}")
            return 1

    _console.print(f"\n[bold green]✓ Ferdig.[/bold green]")
    return 0


def _do_re_export(work_dir: str, export_dir: str, *, timestamped_export: bool = False) -> int:
    """Re-export Stage 4 from the current plan checkpoint. Returns exit code."""
    from ..pipeline.state import PipelineState, StageName
    from ..pipeline.stage4_export import run as run_export

    state = PipelineState(work_dir)
    plan_checkpoint = state.read_stage(StageName.PLANNING)
    if not plan_checkpoint:
        _console.print("[red]✗[/red] Ingen Stage 3-plan funnet.")
        return 1

    try:
        result = run_export(plan_checkpoint, state=state, export_dir=export_dir, strict=True, timestamped_export=timestamped_export)
        files = result.get("output_files", {})
        _console.print(f"  [green]✓[/green] {len(files)} fil(er) eksportert")
        for label, path in files.items():
            _console.print(f"    → {path}")
        return 0
    except Exception as exc:
        _console.print(f"  [red]✗[/red] Eksport feilet: {exc}")
        return 1


def _load_plan_and_updater(work_dir: str):
    """Load the season plan and return (plan, updater, state). Raises SystemExit on error."""
    from ..pipeline.state import PipelineState, StageName
    from ..pipeline.tournament_updater import TournamentUpdater

    work_path = Path(work_dir)
    state = PipelineState(work_dir)
    if not state.checkpoint_path(StageName.PLANNING).exists():
        _console.print(
            f"[red]✗[/red] Ingen Stage 3-plan funnet i {work_path}/. "
            f"Kjør [bold]rvv-miniputt run[/bold] først."
        )
        sys.exit(1)

    updater = TournamentUpdater(state=state)
    try:
        plan = updater.load_plan()
    except ValueError as exc:
        _console.print(f"[red]✗[/red] {exc}")
        sys.exit(1)
    return plan, updater, state


# ---------------------------------------------------------------------------
# tournament subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_tournament(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt tournament ...`` — dispatches to sub-subcommands."""
    if args.t_command == "list":
        return _cmd_tournament_list(args)
    elif args.t_command == "add":
        return _cmd_tournament_add(args)
    elif args.t_command == "remove":
        return _cmd_tournament_remove(args)
    elif args.t_command == "cancel":
        return _cmd_cancel(args)  # reuse existing cancel handler
    else:
        _console.print("[yellow]Bruk: rvv-miniputt tournament {list|add|remove|cancel}[/yellow]")
        return 1


def _cmd_tournament_list(args: argparse.Namespace) -> int:
    """List all tournaments in the season plan."""
    plan, _updater, _state = _load_plan_and_updater(args.work_dir)

    _console.print(f"[bold]Turneringer i sesongplanen[/bold]")
    if not plan.tournaments:
        _console.print("  [dim]Ingen turneringer i planen.[/dim]")
        return 0

    _console.print(f"  {len(plan.tournaments)} turneringer")
    if plan.start_date and plan.end_date:
        _console.print(f"  Sesong: {plan.start_date.isoformat()} → {plan.end_date.isoformat()}")
    _console.print()

    for t in plan.tournaments:
        status = ""
        if t.cancelled:
            status = f" [red](AVLYST: {t.cancellation_reason or 'ingen grunn'})[/red]"
        _console.print(
            f"  [cyan]{t.id}[/cyan]  {t.date.isoformat()}  "
            f"{t.age_group:5s}  {t.arena:20s}  "
            f"{len(t.teams)} lag  ({len(t.games)} kamper){status}"
        )
        _console.print(f"       Lag: {', '.join(t.label for t in t.teams)}")

    return 0


def _cmd_tournament_add(args: argparse.Namespace) -> int:
    """Add a new tournament to the season plan."""
    from datetime import date

    plan, updater, _state = _load_plan_and_updater(args.work_dir)

    # Parse date
    try:
        tournament_date = date.fromisoformat(args.date)
    except ValueError:
        _console.print(f"[red]✗[/red] Ugyldig datoformat '{args.date}'. Bruk YYYY-MM-DD.")
        return 1

    # Parse teams
    team_labels = [t.strip() for t in args.teams.split(",") if t.strip()]
    if len(team_labels) < 2:
        _console.print(f"[red]✗[/red] Trenger minst 2 lag. Fikk: {team_labels}")
        return 1

    _console.print(
        f"[bold]Legger til turnering:[/bold] {args.age_group} "
        f"på {tournament_date.isoformat()} i {args.arena}"
    )
    _console.print(f"  Lag ({len(team_labels)}): {', '.join(team_labels)}")

    result = updater.add_tournament(
        plan=plan,
        age_group=args.age_group,
        team_labels=team_labels,
        tournament_date=tournament_date,
        arena=args.arena,
        host_club=args.host_club,
        force=args.force,
    )

    if not result.success:
        _console.print(f"[red]✗[/red] {result.summary_nb}")
        return 1

    updater.write_updated_checkpoint(plan, log_entry=result)
    updater.log_update(result)

    _console.print(f"[green]✓[/green] {result.summary_nb}")

    # Re-export
    _console.print("\n[bold]Re-eksporterer...[/bold]")
    return _do_re_export(args.work_dir, args.export_dir, timestamped_export=getattr(args, 'timestamped_export', False))


def _cmd_tournament_remove(args: argparse.Namespace) -> int:
    """Remove a tournament entirely from the season plan."""
    plan, updater, _state = _load_plan_and_updater(args.work_dir)

    tournament_id = args.tournament_id
    _console.print(f"[bold]Fjerner turnering {tournament_id}...[/bold]")

    try:
        result = updater.remove_tournament(plan, tournament_id)
    except ValueError as exc:
        _console.print(f"[red]✗[/red] {exc}")
        return 1

    updater.write_updated_checkpoint(plan, log_entry=result)
    updater.log_update(result)

    _console.print(f"[green]✓[/green] {result.summary_nb}")

    # Re-export
    _console.print("\n[bold]Re-eksporterer...[/bold]")
    return _do_re_export(args.work_dir, args.export_dir, timestamped_export=getattr(args, 'timestamped_export', False))


def _cmd_replan(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt replan`` — one-shot cancel + move + re-export."""
    from datetime import date
    from ..pipeline.cancellation_workflow import CancellationWorkflow

    if not args.new_date and not args.suggest:
        _console.print("[red]✗[/red] Angi --new-date <YYYY-MM-DD> eller --suggest.")
        return 1

    plan, _updater, state = _load_plan_and_updater(args.work_dir)
    wf = CancellationWorkflow(state)

    tid = args.tournament_id

    # Find and describe the tournament
    try:
        tournament = wf._find_tournament(plan, tid)
    except ValueError as exc:
        _console.print(f"[red]✗[/red] {exc}")
        return 1

    _console.print(
        f"[bold]Replan:[/bold] {tid} ({tournament.age_group}, {tournament.arena}, "
        f"{tournament.date.isoformat()})"
    )

    # --- Suggest mode ---
    if args.suggest:
        _console.print("\n[bold]Foreslåtte datoer:[/bold]")
        suggestions = wf.suggest_makeup_dates(tournament, plan)
        if not suggestions:
            _console.print("  [dim]Ingen ledige helger funnet.[/dim]")
        else:
            for s in suggestions:
                day_nb = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
                day = day_nb[s.date.weekday()]
                delta = f"+{s.days_from_original}d" if s.days_from_original >= 0 else f"{s.days_from_original}d"
                _console.print(f"  [cyan]{s.date.isoformat()}[/cyan] ({day}, {delta})")
                for c in s.conflicts:
                    _console.print(f"    [dim]Advarsel: {c['reason']}[/dim]")
        _console.print(f"\nBruk --new-date <dato> for å velge en dato.")
        return 0

    # --- Apply move mode ---
    try:
        new_date_obj = date.fromisoformat(args.new_date)
    except ValueError:
        _console.print(f"[red]✗[/red] Ugyldig datoformat '{args.new_date}'. Bruk YYYY-MM-DD.")
        return 1

    _console.print(f"  Ny dato: {new_date_obj.isoformat()}")

    reason = args.reason or "Replan via rvv-miniputt replan"

    # Apply the date move directly (does not require cancellation first —
    # just moves the tournament to the new date with conflict checking).
    move_result = wf.apply_makeup(
        tid, new_date_obj, plan=plan, force=args.force, cascade=True
    )

    if not move_result.success:
        _console.print(f"[red]✗[/red] {move_result.summary_nb}")
        return 1

    _console.print(f"[green]✓[/green] {move_result.summary_nb}")

    wf.write_plan(plan, log_entry=move_result)

    # Re-export
    _console.print("\n[bold]Re-eksporterer...[/bold]")
    return _do_re_export(args.work_dir, args.export_dir, timestamped_export=getattr(args, 'timestamped_export', False))


def _cmd_adjust(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt adjust`` — manual organizer adjustment loop."""
    from .update_command import AdjustmentCommand

    cmd = AdjustmentCommand()
    return cmd.run(
        lock_dates=args.lock_date,
        ban_dates=args.ban_date,
        pin_tournaments=args.pin_tournament,
        force_host_clubs=args.force_host_club,
        exclude_host_clubs=args.exclude_host_club,
        work_dir=args.work_dir,
        export_dir=args.export_dir,
        timestamped_export=args.timestamped_export,
    )


def _cmd_review(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt review`` — apply club responses and re-export."""
    from .review_command import ReviewCommand

    cmd = ReviewCommand()
    return cmd.run(
        args.response,
        work_dir=args.work_dir,
        export_dir=args.export_dir,
        timestamped_export=args.timestamped_export,
    )


def _cmd_critic(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt critic`` — print plan critic issues for existing Stage 3 checkpoint."""
    from ..pipeline.state import PipelineState, StageName
    from .plan_critic import generate_critic_summary

    state = PipelineState(args.work_dir)
    plan_checkpoint = state.read_stage(StageName.PLANNING)
    if not plan_checkpoint:
        _console.print(
            f"[red]✗[/red] Ingen Stage 3-checkpoint funnet i '{args.work_dir}'. "
            "Kjør ``rvv-miniputt run`` først."
        )
        return 1

    season_plan = plan_checkpoint.get("plan") if isinstance(plan_checkpoint, dict) else None
    if season_plan is None:
        _console.print("[red]✗[/red] Stage 3-checkpoint mangler 'plan'-nøkkelen.")
        return 1

    issues = generate_critic_summary(season_plan)
    if issues:
        _console.print("[bold cyan]Plan critic — problemer funnet:[/bold cyan]")
        for issue in issues:
            _console.print(f"  [cyan]•[/cyan] {issue}")
    else:
        _console.print("[bold cyan]Plan critic:[/bold cyan] [green]Ingen problemer oppdaget.[/green]")
    return 0


def _cmd_auto_adjust(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt auto-adjust`` — automated adjustment loop.

    Loads the Stage 3 checkpoint, runs the plan critic, translates auto-fixable
    issues to concrete moves via ``suggest_moves``, applies each move by
    calling ``_cmd_replan`` internally, and re-evaluates.  Repeats until either
    all auto-fixable issues are resolved or ``--max-iterations`` is reached.
    Non-auto-fixable issues are printed as manual-review items at the end.
    """
    from ..pipeline.state import PipelineState, StageName
    from .plan_critic import generate_critic_summary, suggest_moves

    state = PipelineState(args.work_dir)
    max_iter = getattr(args, "max_iterations", 3)

    _console.print(
        f"[bold cyan]Auto-adjust:[/bold cyan] starter justeringsløkke "
        f"(max {max_iter} iterasjoner)…"
    )

    applied_total = 0
    manual_issues: list = []

    for iteration in range(1, max_iter + 1):
        plan_checkpoint = state.read_stage(StageName.PLANNING)
        if not plan_checkpoint:
            _console.print(
                f"[red]✗[/red] Ingen Stage 3-checkpoint funnet i '{args.work_dir}'. "
                "Kjør ``rvv-miniputt run`` først."
            )
            return 1

        season_plan = plan_checkpoint.get("plan") if isinstance(plan_checkpoint, dict) else None
        if season_plan is None:
            _console.print("[red]✗[/red] Stage 3-checkpoint mangler 'plan'-nøkkelen.")
            return 1

        issues = generate_critic_summary(season_plan)
        if not issues:
            _console.print(
                f"[green]✓[/green] Ingen problemer funnet etter {iteration - 1} iterasjon(er)."
            )
            break

        moves = suggest_moves(season_plan, issues)
        auto_moves = [m for m in moves if m["can_auto_fix"] and m["tournament_id"]]
        manual_moves = [m for m in moves if not m["can_auto_fix"]]

        # Collect manual-review issues (deduplicated)
        for m in manual_moves:
            if m["issue"] not in [mi["issue"] for mi in manual_issues]:
                manual_issues.append(m)

        if not auto_moves:
            _console.print(
                f"[yellow]![/yellow] Iterasjon {iteration}: ingen auto-fikserbare problemer gjenstår."
            )
            break

        _console.print(
            f"\n[bold]Iterasjon {iteration}/{max_iter}[/bold] — "
            f"{len(issues)} problem(er) funnet, {len(auto_moves)} auto-fikserbar(e):"
        )

        applied_this_iter = 0
        for move in auto_moves:
            tid = move["tournament_id"]
            new_date = move["new_date"]
            reason = move["reason"]

            _console.print(f"  [cyan]→[/cyan] Turneringsid {tid}: flyttes til {new_date}")
            _console.print(f"    [dim]{reason}[/dim]")

            # Build a synthetic Namespace matching what _cmd_replan expects
            replan_args = argparse.Namespace(
                tournament_id=tid,
                new_date=new_date,
                suggest=False,
                reason=reason,
                force=True,
                work_dir=args.work_dir,
                export_dir=args.export_dir,
                timestamped_export=getattr(args, "timestamped_export", False),
            )
            rc = _cmd_replan(replan_args)
            if rc == 0:
                applied_this_iter += 1
                applied_total += 1
            else:
                _console.print(
                    f"  [red]✗[/red] Kunne ikke flytte {tid} — hopper over."
                )

        if applied_this_iter == 0:
            _console.print(
                "[yellow]![/yellow] Ingen endringer ble brukt i denne iterasjonen — avbryter."
            )
            break
    else:
        _console.print(
            f"[yellow]![/yellow] Maks iterasjoner ({max_iter}) nådd — "
            "noen problemer kan gjenstå."
        )

    # Summary
    _console.print(f"\n[bold]Auto-adjust ferdig:[/bold] {applied_total} endring(er) brukt totalt.")

    if manual_issues:
        _console.print(
            "\n[bold yellow]Problemer som krever manuell gjennomgang:[/bold yellow]"
        )
        for mi in manual_issues:
            _console.print(f"  [yellow]•[/yellow] {mi['issue']}")
            _console.print(f"    [dim]{mi['reason']}[/dim]")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``rvv-miniputt`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        return _cmd_status(args)
    elif args.command == "calendars":
        return _cmd_calendars(args)
    elif args.command == "run":
        return _cmd_run(args)
    elif args.command == "logs":
        return _cmd_logs(args)
    elif args.command == "cancel":
        return _cmd_cancel(args)
    elif args.command == "replan":
        return _cmd_replan(args)
    elif args.command == "adjust":
        return _cmd_adjust(args)
    elif args.command == "review":
        return _cmd_review(args)
    elif args.command == "tournament":
        return _cmd_tournament(args)
    elif args.command == "scrape":
        return _cmd_scrape(args)
    elif args.command == "scrape-llm":
        return _cmd_scrape_llm(args)
    elif args.command == "recovery-targets":
        return _cmd_recovery_targets(args)
    elif args.command == "recovery-inject":
        return _cmd_recovery_inject(args)
    elif args.command == "critic":
        return _cmd_critic(args)
    elif args.command == "auto-adjust":
        return _cmd_auto_adjust(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
