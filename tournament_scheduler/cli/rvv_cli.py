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
    run.add_argument(
        "--timestamped-export",
        action="store_true",
        help="Write exports to a timestamped subfolder (diffable between runs)",
    )

    # logs
    sub.add_parser("logs", help="Show pipeline update logs")

    # scrape — single-club troubleshooting
    scrape = sub.add_parser("scrape", help="Scrape a single club's calendar for troubleshooting")
    scrape.add_argument(
        "--club", required=True,
        help="Club/source name (e.g. 'Sandefjord Penguins', 'Jar', 'Jutul')",
    )
    scrape.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    # scrape-llm — LLM-guided browser scraper for JS-rendered SPAs
    scrape_llm = sub.add_parser(
        "scrape-llm",
        help="Scrape a single club's calendar with LLM-guided browser navigation (for BookUp SPA, StyledCalendar, etc.)",
    )
    scrape_llm.add_argument(
        "--club", required=True,
        help="Club/source name (e.g. 'Sandefjord Penguins', 'Tønsberg', 'Jutul')",
    )
    scrape_llm.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    scrape_llm.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory for screenshots (default: export)",
    )
    scrape_llm.add_argument(
        "--endpoint",
        default=None,
        help="LLM API endpoint URL (default: http://host.lima.internal:1234)",
    )
    scrape_llm.add_argument(
        "--model",
        default=None,
        help="LLM model name (default: qwen2.5-32b-instruct)",
    )
    scrape_llm.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Max LLM-guided interaction cycles (default: 20)",
    )
    scrape_llm.add_argument(
        "--cache-results",
        action="store_true",
        default=True,
        help="Cache scraped events to .pipeline/cache/scraped_data.json (default: true)",
    )
    scrape_llm.add_argument(
        "--debug-screenshots",
        action="store_true",
        default=False,
        help="Save PNG screenshots at each navigation step to export/debug-screenshots/",
    )

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

    # replan — one-shot cancel + move + re-export
    replan = sub.add_parser("replan", help="One-shot replan: move a tournament to a new date and re-export")
    replan.add_argument("--tournament-id", required=True, help="ID of the tournament to replan")
    replan.add_argument(
        "--new-date", default=None,
        help="New date for the tournament (YYYY-MM-DD). Required unless --suggest.",
    )
    replan.add_argument(
        "--suggest", action="store_true",
        help="Show suggested makeup dates instead of applying a move",
    )
    replan.add_argument("--reason", default=None, help="Reason for the replan (e.g. 'Ishall stengt')")
    replan.add_argument("--force", action="store_true", help="Force the move even when conflicts are detected")
    replan.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    replan.add_argument(
        "--export-dir", default="export",
        help="Export output directory (default: export)",
    )
    replan.add_argument(
        "--timestamped-export",
        action="store_true",
        help="Write exports to a timestamped subfolder (diffable between runs)",
    )

    # tournament — add/remove/list/cancel tournaments
    t_sub = sub.add_parser("tournament", help="Manage tournaments: list, add, remove, cancel")
    t_cmds = t_sub.add_subparsers(dest="t_command", title="tournament commands")

    t_list = t_cmds.add_parser("list", help="List all tournaments in the season plan")
    t_list.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    t_add = t_cmds.add_parser("add", help="Add a new tournament to the season plan")
    t_add.add_argument("--age-group", required=True, help="Age group (e.g. U10, JU12)")
    t_add.add_argument("--teams", required=True, help="Comma-separated team labels (e.g. 'Jar 1,Kongsberg 1')")
    t_add.add_argument("--date", required=True, help="Tournament date (YYYY-MM-DD)")
    t_add.add_argument("--arena", required=True, help="Host arena (e.g. Kongsberghallen)")
    t_add.add_argument("--host-club", default=None, help="Host club (inferred from teams if omitted)")
    t_add.add_argument("--force", action="store_true", help="Skip conflict checking")
    t_add.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    t_add.add_argument(
        "--export-dir", default="export",
        help="Export output directory (default: export)",
    )

    t_remove = t_cmds.add_parser("remove", help="Remove a tournament entirely from the season plan")
    t_remove.add_argument("--tournament-id", required=True, help="ID of the tournament to remove")
    t_remove.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    t_remove.add_argument(
        "--export-dir", default="export",
        help="Export output directory (default: export)",
    )

    t_cancel = t_cmds.add_parser("cancel", help="Cancel a tournament and suggest/reschedule makeup dates")
    t_cancel.add_argument("--tournament-id", default=None, help="ID to cancel (omit to list)")
    t_cancel.add_argument("--reason", default=None, help="Cancellation reason")
    t_cancel.add_argument("--makeup-date", default=None, help="Makeup date (YYYY-MM-DD)")
    t_cancel.add_argument("--no-export", action="store_true", help="Skip re-export")
    t_cancel.add_argument("--force", action="store_true", help="Force date move")
    t_cancel.add_argument(
        "--work-dir", default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    t_cancel.add_argument(
        "--export-dir", default="export",
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


def _write_run_log(
    work_dir: str,
    start_time: datetime,
    lines: list[str],
    *,
    success: bool,
) -> None:
    """Write a per-run log file to .pipeline/logs/."""
    log_dir = Path(work_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    status = "OK" if success else "FAILED"
    filename = f"pipeline_run_{timestamp}_{status}.log"
    log_path = log_dir / filename

    content = f"# Pipeline run log\n"
    content += f"# Started: {start_time.isoformat()}\n"
    content += f"# Status: {'SUCCESS' if success else 'FAILED'}\n\n"
    for line in lines:
        content += line + "\n"

    log_path.write_text(content, encoding="utf-8")
    _console.print(f"[dim]Run log saved: {log_path}[/dim]")


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt run`` — full pipeline stages 1→4 + HTML."""
    from pathlib import Path
    from ..pipeline.state import PipelineState, StageName, StageStatus
    from ..pipeline.stage1_config import run as stage1_run
    from ..pipeline.stage2_scraping import run as stage2_run
    from ..pipeline.stage3_planning import run as stage3_run
    from ..pipeline.stage4_export import run as stage4_run
    from ..pipeline.calendar_viewer import generate_html as generate_calendars

    strict = not args.non_strict
    state = PipelineState(args.work_dir)

    # Initialize per-run log
    log_start = datetime.now()
    log_lines: list[str] = []
    run_failed = False

    def _log(msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"[{ts}] {msg}")

    _console.print("[bold]🏒 RVV Miniputt — full pipeline[/bold]\n")
    _log(f"Pipeline started (work_dir={args.work_dir}, input={args.input}, strict={strict})")

    # Stage 1: Config
    _console.print("[bold]Stage 1:[/bold] Konfigurasjon...")
    try:
        cfg = stage1_run(args.input, state, strict=strict)
        _console.print(f"  [green]✓[/green] {cfg.get('source_count', 0)} kilder, "
                       f"{cfg.get('start_date', '?')} → {cfg.get('end_date', '?')}")
        _log(f"Stage 1 OK: {cfg.get('source_count', 0)} sources, {cfg.get('start_date', '?')} → {cfg.get('end_date', '?')}")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        _log(f"Stage 1 FAILED: {exc}")
        _write_run_log(args.work_dir, log_start, log_lines, success=False)
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
        _log(f"Stage 2 OK: {n} sources scanned, {len(blocked)} blocked, {len(llm_fallback)} llm fallback")
        if blocked:
            for b in blocked:
                _console.print(f"    [yellow]⚠[/yellow] {b}")
                _log(f"  Blocked: {b}")
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
        _log(f"Stage 2 FAILED: {exc}")
        # Always check the checkpoint for llm_fallback, even in strict mode
        scraping = state.read_stage(StageName.SCRAPING) or {"sources": [], "blocked": [], "llm_fallback": []}
        llm_fallback = scraping.get("llm_fallback", [])
        if llm_fallback:
            _console.print(f"\n  [bold cyan]🤖 {len(llm_fallback)} kilde(r) kan skrapes med LLM:[/bold cyan]")
            for fb in llm_fallback:
                strategy = fb.get("llm_strategy", {})
                engine = strategy.get("engine", "?")
                creds = strategy.get("credential_env_vars", [])
                cred_hint = f" (credentials: {', '.join(creds)})" if creds else ""
                _console.print(f"    [cyan]→[/cyan] {fb['name']} — {engine}{cred_hint}")
                _log(f"  LLM fallback: {fb['name']} ({engine})")
            _console.print(f"\n  [dim]Kjør [bold]rvv-miniputt scrape-llm[/bold] for å skrape disse kildene interaktivt.[/dim]")
        if strict:
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
        run_failed = True
        _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")

    # Stage 3: Planning
    _console.print("[bold]Stage 3:[/bold] Sesongplanlegging...")
    try:
        plan = stage3_run(cfg, scraping, state, start, end, strict=strict)
        n_tournaments = len(plan.get("plan", {}).get("tournaments", []))
        _console.print(f"  [green]✓[/green] {n_tournaments} turneringer planlagt")
        _log(f"Stage 3 OK: {n_tournaments} tournaments planned")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        _log(f"Stage 3 FAILED: {exc}")
        if strict:
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
        run_failed = True
        _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
        plan = state.read_stage(StageName.PLANNING) or {}

    # Stage 4: Export
    _console.print("[bold]Stage 4:[/bold] Eksport...")
    try:
        export = stage4_run(plan, state, export_dir=args.export_dir, strict=strict, timestamped_export=getattr(args, 'timestamped_export', False))
        files = export.get("output_files", {})
        _console.print(f"  [green]✓[/green] {len(files)} fil(er) eksportert")
        for label, f in files.items():
            _console.print(f"    → {f}")
        _log(f"Stage 4 OK: {len(files)} files exported")
    except Exception as exc:
        _console.print(f"  [red]✗[/red] {exc}")
        _log(f"Stage 4 FAILED: {exc}")
        if strict:
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
        run_failed = True
        _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")

    # Generate calendars.html
    _console.print("Genererer calendars.html...", end=" ")
    try:
        path = generate_calendars(work_dir=args.work_dir)
        _console.print(f"[green]✓[/green] {path}")
        _log(f"calendars.html generated: {path}")
    except Exception as exc:
        _console.print(f"[red]✗[/red] {exc}")
        _log(f"calendars.html FAILED: {exc}")
        run_failed = True

    if run_failed:
        _console.print(f"\n[bold yellow]⚠ Pipeline fullført med feil.[/bold yellow]")
        _log("Pipeline completed with failures")
    else:
        _console.print(f"\n[bold green]✓ Pipeline fullført.[/bold green]")
        _log("Pipeline completed successfully")
    _write_run_log(args.work_dir, log_start, log_lines, success=not run_failed)
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
    from ..pipeline.state import PipelineState
    from ..pipeline.tournament_updater import TournamentUpdater

    work_path = Path(work_dir)
    if not (work_path / "stage3_plan.json").exists():
        _console.print(
            f"[red]✗[/red] Ingen Stage 3-plan funnet i {work_path}/. "
            f"Kjør [bold]rvv-miniputt run[/bold] først."
        )
        sys.exit(1)

    state = PipelineState(work_dir)
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


def _cmd_scrape(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt scrape --club <name>`` — single-source scrape."""
    from datetime import datetime as dt
    from ..pipeline.state import PipelineState, StageName
    from ..pipeline.stage2_scraping import _scrape_source

    state = PipelineState(args.work_dir)
    cfg = state.read_stage(StageName.CONFIG)
    if not cfg:
        _console.print(
            "[red]✗[/red] Ingen Stage 1-konfigurasjon funnet. "
            "Kjør [bold]rvv-miniputt run[/bold] først."
        )
        return 1

    sources: list[dict[str, Any]] = cfg.get("sources", [])
    source_cfg = None
    for s in sources:
        if s.get("name", "").lower() == args.club.lower():
            source_cfg = s
            break

    if source_cfg is None:
        _console.print(f"[red]✗[/red] Ukjent kilde: '{args.club}'")
        _console.print("\n[bold]Tilgjengelige kilder:[/bold]")
        for s in sources:
            _console.print(f"  [cyan]{s.get('name', '?')}[/cyan] ({s.get('type', '?')})")
        return 1

    _console.print(
        f"[bold]Skraper:[/bold] {source_cfg['name']} "
        f"([dim]{source_cfg.get('type', '?')}[/dim])"
    )
    _console.print(f"  URL: [dim]{source_cfg.get('url', '')}[/dim]")

    start = dt.strptime(cfg["start_date"], "%Y-%m-%d")
    end = dt.strptime(cfg["end_date"], "%Y-%m-%d")

    result = _scrape_source(source_cfg, start_date=start, end_date=end)

    n_events = result.get("event_count", 0)
    blocked = result.get("blocked", False)
    llm_fallback = result.get("llm_fallback", False)

    _console.print()
    if n_events > 0:
        _console.print(f"  [green]✓[/green] {n_events} hendelser funnet")
    else:
        _console.print(f"  [yellow]⚠[/yellow] {n_events} hendelser — ingen data i datoperioden")

    if blocked:
        _console.print(f"  [red]✗[/red] Blokkert: {result.get('block_reason', '')}")
    if result.get("scraper_error"):
        _console.print(f"  [red]✗[/red] Scraper-feil: {result['scraper_error']}")

    if llm_fallback:
        strategy = result.get("llm_strategy", {})
        engine = strategy.get("engine", "?")
        creds = strategy.get("credential_env_vars", [])
        cred_hint = f" (credentials: {', '.join(creds)})" if creds else ""
        _console.print(f"\n  [bold cyan]🤖 LLM-fallback tilgjengelig:[/bold cyan] {engine}{cred_hint}")
        nav = strategy.get("initial_navigation", [])
        if nav:
            _console.print(f"  Navigering ({len(nav)} steg):")
            for step in nav:
                cmd = step.get("cmd", "?")
                sel = step.get("selector", "")
                txt = step.get("text", "")
                if cmd == "note":
                    _console.print(f"    [dim]ℹ {txt}[/dim]")
                else:
                    _console.print(f"    → {cmd} [dim]{sel or txt}[/dim]")
        _console.print(f"\n  [dim]Kjør [bold]rvv-miniputt scrape-llm[/bold] for å skrape denne kilden med LLM.[/dim]")

    return 0


def _cache_events(work_dir: str, name: str, url: str, events: list[Any]) -> None:
    """Cache scraped events to the unified cache."""
    from datetime import datetime
    from ..pipeline.cache_manager import ScrapedDataCache
    cache = ScrapedDataCache(work_dir=work_dir)
    data = cache.read()
    if "sources" not in data:
        data["sources"] = {}
    data["sources"][name] = {
        "name": name,
        "url": url,
        "scrape_timestamp": datetime.now().isoformat(),
        "event_count": len(events),
        "blocked": False,
        "events": [
            {
                "date": e.date,
                "name": e.name,
                "datetime": e.datetime.isoformat(),
                "duration_hours": e.duration_hours,
            }
            for e in events
        ],
    }
    data["total_events"] = sum(
        s.get("event_count", 0) for s in data["sources"].values()
    )
    data["source_count"] = len(data["sources"])
    cache.write(data)


def _cmd_scrape_llm(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt scrape-llm`` — LLM-guided browser scraping."""
    from datetime import datetime
    from ..pipeline.state import PipelineState, StageName
    from ..pipeline.scraper_strategies import get_strategy, needs_llm_agent
    from ..pipeline.llm_scraper import StrategyDrivenScraper

    state = PipelineState(args.work_dir)
    cfg = state.read_stage(StageName.CONFIG)
    if not cfg:
        _console.print(
            "[red]✗[/red] Ingen Stage 1-konfigurasjon funnet. "
            "Kjør [bold]rvv-miniputt run[/bold] først."
        )
        return 1

    sources: list[dict[str, Any]] = cfg.get("sources", [])
    source_cfg = None
    for s in sources:
        if s.get("name", "").lower() == args.club.lower():
            source_cfg = s
            break

    if source_cfg is None:
        _console.print(f"[red]✗[/red] Ukjent kilde: '{args.club}'")
        _console.print("\n[bold]Tilgjengelige kilder:[/bold]")
        for s in sources:
            _console.print(f"  [cyan]{s.get('name', '?')}[/cyan] ({s.get('type', '?')})")
        return 1

    name = source_cfg["name"]
    url = source_cfg.get("url", "")

    # Look up scraper strategy
    try:
        strategy = get_strategy(name)
    except Exception:
        strategy = None

    if strategy is None:
        _console.print(
            f"[yellow]⚠[/yellow] Ingen scraper-strategi funnet for '{name}'. "
            f"Prøv [bold]rvv-miniputt scrape --club \"{name}\"[/bold] for deterministisk skraping."
        )
        return 1

    if not needs_llm_agent(strategy):
        strat_url = strategy.url
        # For BookUp SPA with numeric Index URL, use the specialised scraper
        if strategy.engine.value == "bookup_spa" and "/Index/" in strat_url:
            start = datetime.strptime(cfg["start_date"], "%Y-%m-%d")
            end = datetime.strptime(cfg["end_date"], "%Y-%m-%d")
            _console.print(
                f"[bold]BookUp-skraper:[/bold] {name} "
                f"([dim]{strategy.engine.value}[/dim])"
            )
            _console.print(f"  URL: [dim]{url}[/dim]")
            _console.print(f"  Periode: {start.strftime('%d.%m.%Y')} → {end.strftime('%d.%m.%Y')}")

            from ..pipeline.stage2_scraping import _run_bookup_scraper
            events, _ = _run_bookup_scraper(strat_url, name, start, end)
            if events:
                _console.print(f"  [green]✓[/green] {len(events)} hendelser funnet via BookUp-skraper")
                for e in events[:10]:
                    _console.print(f"    [dim]{e.date}  {e.name}[/dim]")
                if len(events) > 10:
                    _console.print(f"    [dim]... og {len(events) - 10} flere[/dim]")
                if args.cache_results:
                    _cache_events(args.work_dir, name, url, events)
                return 0
            else:
                _console.print(f"  [yellow]⚠[/yellow] 0 hendelser funnet")
                return 0

        _console.print(
            f"[yellow]⚠[/yellow] Kilden '{name}' ({strategy.engine.value}) har en direkte skraper men "
            f"ingen spesialisert LLM-støtte. "
            f"Bruk [bold]rvv-miniputt scrape --club \"{name}\"[/bold] i stedet."
        )
        return 1

    _console.print(
        f"[bold]LLM-skraper:[/bold] {name} "
        f"([dim]{strategy.engine.value}[/dim])"
    )
    _console.print(f"  URL: [dim]{url}[/dim]")

    start = datetime.strptime(cfg["start_date"], "%Y-%m-%d")
    end = datetime.strptime(cfg["end_date"], "%Y-%m-%d")
    _console.print(f"  Periode: {start.strftime('%d.%m.%Y')} → {end.strftime('%d.%m.%Y')}")
    _console.print(f"  Månedsnavigasjon: inntil {args.max_iterations} mnd")

    # Show initial navigation steps if any
    nav = strategy.initial_navigation
    if nav:
        _console.print(f"\n  [bold cyan]Forhåndsnavigering ({len(nav)} steg):[/bold cyan]")
        for step in nav:
            cmd = step.get("cmd", "?")
            sel = step.get("selector", "")
            txt = step.get("text", "")
            if cmd == "note":
                _console.print(f"    [dim]ℹ {txt}[/dim]")
            else:
                _console.print(f"    → {cmd} [dim]{sel or txt}[/dim]")
    if strategy.month_selector:
        _console.print(f"  Månedsvelger: [dim]{strategy.month_selector}[/dim]")
    if strategy.event_pattern:
        _console.print(f"  Event-mønster: [dim]{strategy.event_pattern}[/dim]")

    _console.print(f"\n  [dim]Starter strategi-drevet nettleser...[/dim]\n")

    # Create scraper with optional endpoint/model overrides (for LLM fallback only)
    scraper_kwargs: dict[str, Any] = {
        "max_months": args.max_iterations,
    }
    if args.endpoint:
        scraper_kwargs["llm_endpoint"] = args.endpoint
    if args.model:
        scraper_kwargs["llm_model"] = args.model
    if args.debug_screenshots:
        scraper_kwargs["screenshots_dir"] = str(Path(args.export_dir or "export") / "debug-screenshots")

    scraper = StrategyDrivenScraper(**scraper_kwargs)

    try:
        events = scraper.run(
            url=url,
            name=name,
            start_date=start,
            end_date=end,
            initial_navigation=strategy.initial_navigation,
            month_selector=strategy.month_selector or "",
            event_pattern=strategy.event_pattern or "",
        )
    except RuntimeError as exc:
        _console.print(f"[red]✗[/red] Strategi-drevet skraping feilet: {exc}")
        _console.print(
            "\n[dim]Sjekk at LM Studio (eller en OpenAI-kompatibel server) kjører på "
            f"{'args.endpoint' if args.endpoint else 'http://host.lima.internal:1234'}.[/dim]"
        )
        return 1
    except Exception as exc:
        _console.print(f"[red]✗[/red] Uventet feil under strategi-drevet skraping: {exc}")
        return 1

    _console.print()
    if events:
        _console.print(f"  [green]✓[/green] {len(events)} hendelser funnet via strategi-drevet skraping")
        for e in events[:10]:
            _console.print(f"    [dim]{e.date}  {e.name}[/dim]")
        if len(events) > 10:
            _console.print(f"    [dim]... og {len(events) - 10} flere[/dim]")

        # Cache results
        if args.cache_results:
            _cache_events(args.work_dir, name, url, events)
            _console.print(f"  [dim]Cachet til .pipeline/cache/scraped_data.json[/dim]")
    else:
        _console.print(f"  [yellow]⚠[/yellow] 0 hendelser funnet — ingen kalenderdata på siden")
        _console.print(
            f"  [dim]Tips: Kjør med --max-iterations {args.max_iterations * 2} for å bla gjennom flere måneder.[/dim]"
        )

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
    elif args.command == "replan":
        return _cmd_replan(args)
    elif args.command == "tournament":
        return _cmd_tournament(args)
    elif args.command == "scrape":
        return _cmd_scrape(args)
    elif args.command == "scrape-llm":
        return _cmd_scrape_llm(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
