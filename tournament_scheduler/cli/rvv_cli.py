"""
``rvv-miniputt`` — unified CLI for the RVV Miniputt tournament scheduler pipeline.

Provides the commands referenced by the HTML calendar viewer, scraper tools,
and pipeline logs::

    rvv-miniputt calendars              Regenerate calendar HTML from cache
    rvv-miniputt calendars --refresh    Full re-scrape: clear caches, scrape, regenerate
    rvv-miniputt run                    Full pipeline: stages 1→4 + HTML views
    rvv-miniputt logs                   Show pipeline update logs
    rvv-miniputt cancel                 Cancel a tournament and suggest/reschedule makeup dates
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from rich.console import Console

_console = Console()

# ---------------------------------------------------------------------------
# Top-level arg parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rvv-miniputt",
        description="RVV Miniputt — tournament scheduler pipeline CLI",
    )
    sub = parser.add_subparsers(dest="command", title="commands")

    # calendars
    cal = sub.add_parser("calendars", help="Calendar viewer commands")
    cal.add_argument(
        "--refresh",
        action="store_true",
        help="Force full re-scrape: clear all caches, re-scrape, regenerate HTML",
    )
    cal.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    # run
    run = sub.add_parser("run", help="Run the full pipeline (stages 1→4 + HTML)")
    run.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    run.add_argument(
        "--input",
        default="input.json",
        help="Path to pipeline input config (default: input.json)",
    )
    run.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )
    run.add_argument(
        "--non-strict",
        action="store_true",
        help="Continue on blocked sources or warnings",
    )

    # logs
    sub.add_parser("logs", help="Show pipeline update logs")

    # cancel
    cancel = sub.add_parser("cancel", help="Cancel a tournament and suggest/reschedule makeup dates")
    cancel.add_argument(
        "--tournament-id",
        default=None,
        help="ID of the tournament to cancel (omit to list available tournaments)",
    )
    cancel.add_argument(
        "--reason",
        default=None,
        help="Cancellation reason, e.g. 'Ishall stengt — vannlekkasje'",
    )
    cancel.add_argument(
        "--makeup-date",
        default=None,
        help="Apply a makeup date immediately (YYYY-MM-DD). If omitted, suggestions are shown.",
    )
    cancel.add_argument(
        "--no-export",
        action="store_true",
        help="Skip re-export after cancellation/makeup",
    )
    cancel.add_argument(
        "--force",
        action="store_true",
        help="Force the date move even when conflicts are detected",
    )
    cancel.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    cancel.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )

    return parser


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def _cmd_calendars(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt calendars [--refresh]``."""
    from ..pipeline.calendar_viewer import generate_html
    from ..pipeline.cache_manager import ScrapedDataCache
    from ..utils.calendar_cache import CalendarCache

    work_dir = args.work_dir

    if args.refresh:
        _console.print("[bold]🔄 Tvinger full re-skraping av kalendere...[/bold]\n")

        # 1. Clear iCal scraper cache (avoids stale cached HTTP responses)
        _console.print("  Tømmer iCal-skraper-cache...", end=" ")
        try:
            CalendarCache().clear()
            _console.print("[green]✓[/green]")
        except Exception as exc:
            _console.print(f"[yellow]⚠[/yellow] ({exc})")

        # 2. Mark unified cache stale
        _console.print("  Markerer unified-cache som utdatert...", end=" ")
        try:
            ScrapedDataCache(work_dir=work_dir).force_refresh()
            _console.print("[green]✓[/green]")
        except Exception as exc:
            _console.print(f"[yellow]⚠[/yellow] ({exc})")

        # 3. Run stage 2 scraping
        _console.print("  Skraper kalendere (Stage 2)...")
        try:
            from ..pipeline.state import PipelineState, StageName
            from ..pipeline.stage2_scraping import run as stage2_run

            state = PipelineState(work_dir)
            cfg = state.read_stage(StageName.CONFIG)
            if not cfg:
                _console.print("[red]✗[/red] Stage 1 checkpoint mangler — kjør 'rvv-miniputt run' først")
                return 1

            start = datetime.strptime(cfg["start_date"], "%Y-%m-%d")
            end = datetime.strptime(cfg["end_date"], "%Y-%m-%d")
            result = stage2_run(cfg, state, start, end, strict=False)
            n = len(result.get("sources", []))
            blocked = result.get("blocked", [])
            _console.print(f"  [green]✓[/green] Stage 2: {n} kilder, {len(blocked)} blokkert")
        except Exception as exc:
            _console.print(f"  [red]✗[/red] Stage 2 feilet: {exc}")
            return 1

        # 4. Rebuild unified cache from the fresh Stage 2 checkpoint
        _console.print("  Bygger unified-cache fra Stage 2 checkpoint...", end=" ")
        try:
            scraping_result = state.read_stage(StageName.SCRAPING)
            if scraping_result:
                ScrapedDataCache(work_dir=work_dir).build_from_checkpoint(cfg, scraping_result)
                _console.print("[green]✓[/green]")
            else:
                _console.print("[yellow]⚠[/yellow] (ingen Stage 2 checkpoint)")
        except Exception as exc:
            _console.print(f"[yellow]⚠[/yellow] ({exc})")

        # 5. Regenerate calendar HTML
        _console.print("  Genererer calendars.html...", end=" ")
        try:
            path = generate_html(work_dir=work_dir)
            _console.print(f"[green]✓[/green] {path}")
        except Exception as exc:
            _console.print(f"[red]✗[/red] {exc}")
            return 1

        _console.print(f"\n[bold green]✓ Full re-skraping fullført.[/bold green]")
        return 0

    # No --refresh: just regenerate HTML from cache
    _console.print("Genererer calendars.html fra cache...", end=" ")
    try:
        path = generate_html(work_dir=work_dir)
        _console.print(f"[green]✓[/green] {path}")
    except Exception as exc:
        _console.print(f"[red]✗[/red] {exc}")
        return 1
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt run`` — full pipeline stages 1→4 + HTML."""
    from ..pipeline.state import PipelineState, StageName, StageStatus
    from ..pipeline.stage1_config import run as stage1_run
    from ..pipeline.stage2_scraping import run as stage2_run
    from ..pipeline.stage3_planning import run as stage3_run
    from ..pipeline.stage4_export import run as stage4_run
    from ..pipeline.calendar_viewer import generate_html as generate_calendars

    strict = not args.non_strict
    state = PipelineState(args.work_dir)

    _console.print("[bold]🏒 RVV Miniputt — full pipeline[/bold]\n")

    # Stage 1: Config
    _console.print("[bold]Stage 1:[/bold] Konfigurasjon...")
    try:
        cfg = stage1_run(args.input, state, strict=strict)
        _console.print(f"  [green]✓[/green] {cfg.get('source_count', 0)} kilder, "
                       f"{cfg.get('start_date', '?')} → {cfg.get('end_date', '?')}")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        return 1

    start = datetime.strptime(cfg["start_date"], "%Y-%m-%d")
    end = datetime.strptime(cfg["end_date"], "%Y-%m-%d")

    # Stage 2: Scraping
    _console.print("[bold]Stage 2:[/bold] Skraping...")
    try:
        scraping = stage2_run(cfg, state, start, end, strict=strict)
        n = len(scraping.get("sources", []))
        blocked = scraping.get("blocked", [])
        llm_fallback = scraping.get("llm_fallback", [])
        _console.print(f"  [green]✓[/green] {n} kilder skannet, {len(blocked)} blokkert")
        if blocked:
            for b in blocked:
                _console.print(f"    [yellow]⚠[/yellow] {b}")
        if llm_fallback:
            _console.print(f"\n  [bold cyan]🤖 {len(llm_fallback)} kilde(r) kan skrapes med LLM:[/bold cyan]")
            for fb in llm_fallback:
                strategy = fb.get("llm_strategy", {})
                engine = strategy.get("engine", "?")
                creds = strategy.get("credential_env_vars", [])
                cred_hint = f" (credentials: {', '.join(creds)})" if creds else ""
                _console.print(f"    [cyan]→[/cyan] {fb['name']} — {engine}{cred_hint}")
            _console.print(f"\n  [dim]Kjør [bold]rvv-miniputt scrape-llm[/bold] for å skrape disse kildene interaktivt.[/dim]")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        if strict:
            return 1
        _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
        scraping = state.read_stage(StageName.SCRAPING) or {"sources": [], "blocked": [], "llm_fallback": []}

    # Stage 3: Planning
    _console.print("[bold]Stage 3:[/bold] Sesongplanlegging...")
    try:
        plan = stage3_run(cfg, scraping, state, start, end, strict=strict)
        n_tournaments = len(plan.get("plan", {}).get("tournaments", []))
        _console.print(f"  [green]✓[/green] {n_tournaments} turneringer planlagt")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        if strict:
            return 1
        _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
        plan = state.read_stage(StageName.PLANNING) or {}

    # Stage 4: Export
    _console.print("[bold]Stage 4:[/bold] Eksport...")
    try:
        export = stage4_run(plan, state, export_dir=args.export_dir, strict=strict)
        files = export.get("files", [])
        _console.print(f"  [green]✓[/green] {len(files)} fil(er) eksportert")
        for f in files:
            _console.print(f"    → {f}")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        if strict:
            return 1

    # Generate calendars.html
    _console.print("Genererer calendars.html...", end=" ")
    try:
        path = generate_calendars(work_dir=args.work_dir)
        _console.print(f"[green]✓[/green] {path}")
    except Exception as exc:
        _console.print(f"[red]✗[/red] {exc}")

    _console.print(f"\n[bold green]✓ Pipeline fullført.[/bold green]")
    return 0


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


def _cmd_logs(args: argparse.Namespace) -> int:  # noqa: ARG001
    """Handle ``rvv-miniputt logs`` — show pipeline update logs."""
    from pathlib import Path

    work_dir = Path(".pipeline")
    log_dir = work_dir / "logs"

    if not log_dir.exists() or not any(log_dir.iterdir()):
        _console.print("[dim]Ingen pipeline-logger funnet i .pipeline/logs/[/dim]")
        return 0

    log_files = sorted(log_dir.glob("*.log"), reverse=True)
    _console.print(f"[bold]Pipeline-logger[/bold] ({len(log_files)} fil(er)):\n")

    for log_file in log_files:
        _console.print(f"[bold cyan]{log_file.name}[/bold cyan]")
        try:
            content = log_file.read_text(encoding="utf-8").strip()
            if len(content) > 2000:
                content = content[-2000:] + f"\n\n... (trunkert, {log_file.stat().st_size} bytes)"
            for line in content.splitlines():
                _console.print(f"  {line}")
        except Exception as exc:
            _console.print(f"  [red]Kunne ikke lese: {exc}[/red]")
        _console.print()

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``rvv-miniputt`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "calendars":
        return _cmd_calendars(args)
    elif args.command == "run":
        return _cmd_run(args)
    elif args.command == "logs":
        return _cmd_logs(args)
    elif args.command == "cancel":
        return _cmd_cancel(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
