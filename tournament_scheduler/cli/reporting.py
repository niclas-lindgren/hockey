"""RVV CLI log/status reporting helpers."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

_console = Console()


def _cmd_logs(args) -> int:  # noqa: ARG001
    """Handle ``rvv-miniputt logs`` — show pipeline update logs."""
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
