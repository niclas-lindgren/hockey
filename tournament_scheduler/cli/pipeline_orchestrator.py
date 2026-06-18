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



def _resolve_resume_stage(value: str | int | None) -> int:
    mapping = {
        "1": 1, "config": 1, "stage1": 1,
        "2": 2, "scraping": 2, "stage2": 2,
        "3": 3, "planning": 3, "plan": 3, "stage3": 3,
        "4": 4, "export": 4, "stage4": 4,
    }
    if value is None:
        return 1
    return mapping.get(str(value).lower(), 1)



def _force_refresh_stage2_inputs(work_dir: str) -> None:
    from ..pipeline.cache_manager import ScrapedDataCache
    from ..utils.calendar_cache import CalendarCache

    CalendarCache(work_dir=work_dir).clear()
    ScrapedDataCache(work_dir=work_dir).force_refresh()


def _run_approval_gate(
    args: argparse.Namespace,
    plan_checkpoint: "dict[str, Any]",
    state: "Any",
    strict: bool,
    console: "Console",
    log_fn: "Any",
) -> bool:
    """Run the plan critic and print any issues; always returns True (non-blocking)."""
    from .plan_critic import generate_critic_summary

    season_plan = plan_checkpoint.get("plan") if isinstance(plan_checkpoint, dict) else None
    if season_plan is not None:
        try:
            issues = generate_critic_summary(season_plan)
            if issues:
                console.print("[bold cyan]Plan critic:[/bold cyan]")
                for issue in issues:
                    console.print(f"  [cyan]•[/cyan] {issue}")
            else:
                console.print("[bold cyan]Plan critic:[/bold cyan] Ingen problemer oppdaget.")
        except Exception as exc:
            console.print(f"  [yellow]⚠[/yellow] Plan critic feilet: {exc}")
    return True


def _check_stage2_checkpoint(
    scraping_checkpoint: "dict[str, Any]",
    strict: bool,
    console: "Console",
    log_fn: "Any",
    *,
    harness_active: bool = False,
) -> bool:
    """Deterministic Stage 2 gate: inspect checkpoint fields directly.

    Reads ``sources[].event_count``, ``sources[].blocked``, and ``blocked[]``
    from *scraping_checkpoint* to decide whether the pipeline should proceed
    to Stage 3.

    When *harness_active* is True the gate auto-proceeds if at least one
    source returned events (threshold check), avoiding any interactive prompt.
    When *harness_active* is False and strict mode is on, the operator is
    prompted to confirm before proceeding despite warnings.

    Args:
        scraping_checkpoint: Stage 2 checkpoint dict written by stage2_scraping.run().
        strict: Whether the pipeline is running in strict mode.
        console: Rich ``Console`` for interactive output.
        log_fn: Callable that appends a message to the run log.
        harness_active: True when running headless under a harness (no LLM judge
            configured) — skips interactive prompts and uses threshold logic only.

    Returns:
        ``True`` if the pipeline should proceed to Stage 3, ``False`` if it should
        halt.
    """
    sources: list[dict[str, Any]] = scraping_checkpoint.get("sources", [])
    blocked_names: list[str] = scraping_checkpoint.get("blocked", [])

    total_events = sum(s.get("event_count", 0) for s in sources if not s.get("blocked"))
    sources_with_events = sum(
        1 for s in sources if not s.get("blocked") and s.get("event_count", 0) > 0
    )
    blocked_count = len(blocked_names)

    log_fn(
        f"Stage 2 checkpoint check: {sources_with_events} sources with events, "
        f"{total_events} total events, {blocked_count} blocked"
    )

    # No sources configured — nothing to validate; let the pipeline proceed.
    if not sources:
        log_fn("Stage 2 gate: no sources configured — skipping threshold check")
        return True

    if sources_with_events == 0:
        console.print(
            "  [red]✗[/red] Stage 2-sjekkpunkt: ingen kilder returnerte hendelser"
        )
        log_fn("Stage 2 gate FAIL: zero sources with events")
        if not strict:
            console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
            return True
        return False

    if blocked_count > 0:
        console.print(
            f"  [yellow]⚠[/yellow] Stage 2-sjekkpunkt: {blocked_count} kilde(r) blokkert, "
            f"men {sources_with_events} kilde(r) returnerte hendelser"
        )
        log_fn(f"Stage 2 gate WARN: {blocked_count} blocked sources")

        if harness_active:
            # Harness mode: threshold met (at least one source with events) — auto-proceed
            log_fn("Stage 2 gate: harness active, threshold met — auto-proceeding")
            return True

        if not strict:
            console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
            return True

        # strict + interactive: ask the operator
        try:
            answer = input("\n  Vil du fortsette til planlegging likevel? (j/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        log_fn(f"Operator confirmation answer (stage2 gate): {answer!r}")
        if answer in ("j", "y", "ja", "yes"):
            console.print("  [yellow]⚠[/yellow] Operatør har overstyrt advarsel — fortsetter")
            log_fn("Stage 2 gate WARN overridden by operator")
            return True
        return False

    # All sources OK
    log_fn("Stage 2 gate PASS: all sources returned events")
    return True


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle ``rvv-miniputt run`` — full pipeline stages 1→4 + HTML."""
    from ..llm_judge import build_stage_prompt, get_judge_if_headless
    from ..pipeline.calendar_viewer import generate_html as generate_calendars
    from ..pipeline.stage1_config import load_effective_config, run as stage1_run
    from ..pipeline.stage2_scraping import run as stage2_run
    from ..pipeline.stage3_planning import run as stage3_run
    from ..pipeline.stage4_export import run as stage4_run
    from ..pipeline.state import PipelineState, StageName, StageStatus

    strict = not args.non_strict
    resume_from = _resolve_resume_stage(getattr(args, "resume_from", None))
    state = PipelineState(args.work_dir)

    log_start = datetime.now()
    log_lines: list[str] = []
    run_failed = False

    def _log(msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"[{ts}] {msg}")

    _STAGE_NAMES = {1: "stage1", 2: "stage2", 3: "stage3"}

    def _judge_stage(
        stage_num: int,
        checkpoint_summary: dict[str, Any],
        stage_name: "StageName | None" = None,
    ) -> bool:
        """Ask the headless judge whether to proceed after a stage.

        Returns True if the pipeline should continue, False if it should abort.
        When no judge is present (harness active or RVV_JUDGE_BACKEND unset)
        always returns True so the pipeline continues unchanged.

        The verdict is persisted into the stage checkpoint via
        ``state.write_judgment`` so it appears in ``.pipeline/stage*.json``.
        """
        import os as _os

        try:
            judge = get_judge_if_headless()
        except ValueError:
            # RVV_JUDGE_BACKEND not set — headless but no backend configured.
            # Treat as "proceed" so the pipeline is not silently broken.
            return True
        if judge is None:
            return True  # harness is active — it will judge interactively

        backend_name = _os.environ.get("RVV_JUDGE_BACKEND", "unknown")
        stage_key = _STAGE_NAMES.get(stage_num, f"stage{stage_num}")
        try:
            prompt = build_stage_prompt(stage_key, checkpoint_summary)
        except ValueError:
            # Unknown stage — fall back to a generic prompt.
            prompt = (
                f"Pipeline stage {stage_num} completed. "
                f"Summary: {checkpoint_summary}. "
                "Respond PROCEED or ABORT."
            )
        try:
            verdict_raw = judge.judge(prompt).strip()
        except RuntimeError as exc:
            _log(f"Stage {stage_num} judge call failed: {exc}")
            _console.print(f"  [yellow]⚠[/yellow] Dommerkall feilet: {exc} — fortsetter")
            if stage_name is not None:
                try:
                    state.write_judgment(stage_name, "ERROR", reasoning=str(exc), backend=backend_name)
                except Exception:
                    pass
            return True

        # Split verdict keyword from any trailing reasoning text.
        lines = verdict_raw.splitlines()
        verdict_keyword = lines[0].strip() if lines else verdict_raw
        reasoning = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        _log(f"Stage {stage_num} judge verdict: {verdict_raw[:200]}")
        _log(f"Stage {stage_num} judge backend: {backend_name}")

        if stage_name is not None:
            try:
                state.write_judgment(
                    stage_name,
                    verdict=verdict_keyword,
                    reasoning=reasoning,
                    backend=backend_name,
                )
            except Exception as exc:
                _log(f"Stage {stage_num} write_judgment failed: {exc}")

        if verdict_keyword.upper().startswith("ABORT"):
            _console.print(f"  [red]✗ Headless dommer avbrøt etter Stage {stage_num}:[/red] {verdict_raw}")
            return False
        return True

    _console.print("[bold]🏒 RVV Miniputt — full pipeline[/bold]\n")
    _log(
        f"Pipeline started (work_dir={args.work_dir}, input={args.input}, strict={strict}, "
        f"resume_from={resume_from}, log_level={getattr(args, 'log_level', 'info')})"
    )
    if resume_from > 1:
        _console.print(f"[dim]Gjenopptar fra Stage {resume_from}[/dim]")

    cfg: dict[str, Any] | None = None
    scraping: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None

    if resume_from <= 1:
        _console.print("[bold]Stage 1:[/bold] Konfigurasjon...")
        try:
            stage1_run(args.input, state, strict=strict)
            cfg = load_effective_config(state, input_path=args.input)
            _console.print(f"  [green]✓[/green] {len(cfg.get('sources', []))} kilder, {cfg.get('start_date', '?')} → {cfg.get('end_date', '?')}")
            _log(f"Stage 1 OK: {cfg.get('source_count', 0)} sources, {cfg.get('start_date', '?')} → {cfg.get('end_date', '?')}")
            stage1_summary = {
                "sources": len(cfg.get("sources", [])),
                "start_date": cfg.get("start_date", "?"),
                "end_date": cfg.get("end_date", "?"),
                "age_groups": cfg.get("age_groups", []),
                "clubs": cfg.get("clubs", []),
            }
            if not _judge_stage(1, stage1_summary, stage_name=StageName.CONFIG):
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
        except Exception as exc:
            _console.print(f"  [red]✗[/red] {exc}")
            _log(f"Stage 1 FAILED: {exc}")
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
    else:
        cfg = load_effective_config(state)
        if not cfg:
            _console.print("[red]✗[/red] Kan ikke gjenoppta: Stage 1-checkpoint mangler.")
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
        _console.print("[bold]Stage 1:[/bold] Hoppet over (gjenopptatt)")
        _log("Stage 1 skipped via --resume-from")

    start = datetime.strptime(cfg["start_date"], "%Y-%m-%d")
    end = datetime.strptime(cfg["end_date"], "%Y-%m-%d")

    if resume_from <= 2:
        _console.print("[bold]Stage 2:[/bold] Skraping...")
        allow_missing_sources = args.allow_missing_sources
        if getattr(args, "force_refresh", False):
            try:
                _force_refresh_stage2_inputs(args.work_dir)
                _console.print("  [green]✓[/green] Cache tvangsoppdatert før Stage 2")
                _log("Stage 2 inputs force-refreshed")
            except Exception as exc:
                _console.print(f"  [yellow]⚠[/yellow] Cache-refresh feilet: {exc}")
                _log(f"Stage 2 force-refresh warning: {exc}")
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
            _console.print(f"  [green]✓[/green] {n} kilder skannet, {len(blocked)} blokkert")
            _log(f"Stage 2 OK: {n} sources scanned, {len(blocked)} blocked")
            if blocked:
                for blocked_name in blocked:
                    _console.print(f"    [yellow]⚠[/yellow] {blocked_name}")
                    _log(f"  Blocked: {blocked_name}")
                if scraping.get("warning"):
                    _console.print(f"  [dim]{scraping['warning']}[/dim]")
                if allow_missing_sources:
                    _console.print("  [green]✓[/green] Delvise resultater er lagret og pipeline fortsetter med godkjente mangler.")
                else:
                    _console.print("  [dim]Delvise resultater er lagret; kjør [bold]rvv-miniputt run --allow-missing-sources[/bold] for å fortsette med slike mangler neste gang.[/dim]")
            stage2_summary = {
                "sources_scanned": n,
                "blocked": blocked,
            }
            if not _judge_stage(2, stage2_summary, stage_name=StageName.SCRAPING):
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
            # Deterministic checkpoint inspection — runs regardless of judge backend.
            try:
                _harness_active = get_judge_if_headless() is None
            except ValueError:
                _harness_active = True  # no backend configured — treat as harness
            if not _check_stage2_checkpoint(
                scraping, strict, _console, _log, harness_active=_harness_active
            ):
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
        except Exception as exc:
            _console.print(f"  [red]✗[/red] {exc}")
            _log(f"Stage 2 FAILED: {exc}")
            scraping = state.read_stage(StageName.SCRAPING) or {"sources": [], "blocked": []}
            if scraping.get("warning"):
                _console.print(f"  [dim]{scraping['warning']}[/dim]")
            if strict:
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
            run_failed = True
            _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
    else:
        scraping = state.read_stage(StageName.SCRAPING)
        if not scraping:
            _console.print("[red]✗[/red] Kan ikke gjenoppta: Stage 2-checkpoint mangler.")
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
        _console.print("[bold]Stage 2:[/bold] Hoppet over (gjenopptatt)")
        _log("Stage 2 skipped via --resume-from")

    if resume_from <= 3:
        _console.print("[bold]Stage 3:[/bold] Sesongplanlegging...")
        try:
            plan = stage3_run(cfg, scraping, state, start, end, strict=strict)
            n_tournaments = len(plan.get("plan", {}).get("tournaments", []))
            _console.print(f"  [green]✓[/green] {n_tournaments} turneringer planlagt")
            _log(f"Stage 3 OK: {n_tournaments} tournaments planned")
            stage3_summary = {
                "tournaments_planned": n_tournaments,
                "warnings": plan.get("warnings", []),
            }
            if not _judge_stage(3, stage3_summary, stage_name=StageName.PLANNING):
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
        except Exception as exc:
            _console.print(f"  [red]✗[/red] {exc}")
            _log(f"Stage 3 FAILED: {exc}")
            if strict:
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
            run_failed = True
            _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
            plan = state.read_stage(StageName.PLANNING) or {}
    else:
        plan = state.read_stage(StageName.PLANNING)
        if not plan:
            _console.print("[red]✗[/red] Kan ikke gjenoppta: Stage 3-checkpoint mangler.")
            _write_run_log(args.work_dir, log_start, log_lines, success=False)
            return 1
        _console.print("[bold]Stage 3:[/bold] Hoppet over (gjenopptatt)")
        _log("Stage 3 skipped via --resume-from")

    # ── LLM approval gate (between Stage 3 and Stage 4) ──────────────────────
    # Only runs when RVV_APPROVAL_ENDPOINT is set (opt-in).  If not configured
    # the gate is skipped silently so non-LLM deployments are unaffected.
    if not _run_approval_gate(args, plan, state, strict, _console, _log):
        _write_run_log(args.work_dir, log_start, log_lines, success=False)
        return 1

    if resume_from <= 4:
        _console.print("[bold]Stage 4:[/bold] Eksport...")
        try:
            export = stage4_run(plan, state, export_dir=args.export_dir, strict=strict, timestamped_export=getattr(args, "timestamped_export", False))
            files = export.get("output_files", {})
            _console.print(f"  [green]✓[/green] {len(files)} fil(er) eksportert")
            for label, file_path in files.items():
                _console.print(f"    → {file_path}")
            _log(f"Stage 4 OK: {len(files)} files exported")
        except Exception as exc:
            _console.print(f"  [red]✗[/red] {exc}")
            _log(f"Stage 4 FAILED: {exc}")
            if strict:
                _write_run_log(args.work_dir, log_start, log_lines, success=False)
                return 1
            run_failed = True
            _console.print("  [yellow]⚠[/yellow] Fortsetter pga --non-strict")
    else:
        _console.print("[bold]Stage 4:[/bold] Hoppet over (gjenopptatt)")
        _log("Stage 4 skipped via --resume-from")

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
        _console.print("\n[bold yellow]⚠ Pipeline fullført med feil.[/bold yellow]")
        _log("Pipeline completed with failures")
    else:
        _console.print("\n[bold green]✓ Pipeline fullført.[/bold green]")
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
            f"{args.endpoint if args.endpoint else 'http://host.lima.internal:1234'}.[/dim]"
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


