"""Pipeline-oriented RVV CLI command handlers."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

_console = Console()

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
            CalendarCache(work_dir=work_dir).clear()
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
            from ..pipeline.stage1_config import load_effective_config
            from ..pipeline.stage2_scraping import run as stage2_run

            state = PipelineState(work_dir)
            cfg = load_effective_config(state)
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

        # 5. Regenerate calendar HTML (in export/ alongside season plan)
        _console.print("  Genererer calendars.html...", end=" ")
        try:
            path = generate_html(work_dir=work_dir, export_dir="export")
            _console.print(f"[green]✓[/green] {path}")
        except Exception as exc:
            _console.print(f"[red]✗[/red] {exc}")
            return 1

        _console.print(f"\n[bold green]✓ Full re-skraping fullført.[/bold green]")
        return 0

    # No --refresh: just regenerate HTML from cache (in export/)
    _console.print("Genererer calendars.html fra cache...", end=" ")
    try:
        path = generate_html(work_dir=work_dir, export_dir="export")
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
    allow_missing_sources = args.allow_missing_sources
    try:
        scraping = stage2_run(
            cfg,
            state,
            start,
            end,
            strict=strict,
            allow_missing_sources=allow_missing_sources,
        )
        n = len(scraping.get("sources", []))
        blocked = scraping.get("blocked", [])
        llm_fallback = scraping.get("llm_fallback", [])
        _console.print(f"  [green]✓[/green] {n} kilder skannet, {len(blocked)} blokkert")
        _log(f"Stage 2 OK: {n} sources scanned, {len(blocked)} blocked, {len(llm_fallback)} llm fallback")
        if blocked:
            for b in blocked:
                _console.print(f"    [yellow]⚠[/yellow] {b}")
                _log(f"  Blocked: {b}")
            if scraping.get("warning"):
                _console.print(f"  [dim]{scraping['warning']}[/dim]")
            if allow_missing_sources:
                _console.print("  [green]✓[/green] Delvise resultater er lagret og pipeline fortsetter med godkjente mangler.")
            else:
                _console.print("  [dim]Delvise resultater er lagret; kjør [bold]rvv-miniputt run --allow-missing-sources[/bold] for å fortsette med slike mangler neste gang.[/dim]")
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
        # Always check the checkpoint for blocked sources and llm_fallback, even in strict mode
        scraping = state.read_stage(StageName.SCRAPING) or {"sources": [], "blocked": [], "llm_fallback": []}
        if scraping.get("warning"):
            _console.print(f"  [dim]{scraping['warning']}[/dim]")
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

    # Generate calendars.html (in export/ alongside other files)
    _console.print("Genererer calendars.html...", end=" ")
    try:
        path = generate_calendars(work_dir=args.work_dir, export_dir=args.export_dir)
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



def _cmd_scrape(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt scrape --club <name>`` — single-source scrape."""
    from datetime import datetime as dt
    from ..pipeline.state import PipelineState, StageName
    from ..pipeline.stage1_config import load_effective_config
    from ..pipeline.stage2_scraping import _scrape_source

    state = PipelineState(args.work_dir)
    cfg = load_effective_config(state)
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
        if result.get("recovery_hint"):
            _console.print(f"  [dim]{result['recovery_hint']}[/dim]")
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
    from ..pipeline.stage1_config import load_effective_config
    from ..pipeline.scraper_strategies import get_strategy, needs_llm_agent
    from ..pipeline.llm_scraper import StrategyDrivenScraper

    state = PipelineState(args.work_dir)
    cfg = load_effective_config(state)
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


