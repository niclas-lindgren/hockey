"""Spond Excel exporter — produces a single-sheet workbook for Spond's Season Planner import.

Spond's season-plan Excel import expects these columns:

    Dato       Aktivitet            Sted          Start   Slutt
    DD.MM.YYYY <text>               <text>        HH:MM   HH:MM

Each row is one activity (game or tournament). Start/Slutt are optional
placeholders — we leave them empty since exact game times are not in the
model yet.

Two output modes are supported:

* **game-level** (default) — one row per game: ``"U10: Jar 1 vs Jar 2"``
* **tournament-level** — one row per tournament: ``"U10 Turnering — Jarhallen"``

The resulting ``.xlsx`` file can be imported directly into Spond Club's
Season Planner (Sesongplanlegger → Importer fra Excel).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from rich.console import Console

from ..models import SeasonPlan

console = Console()

_SPOND_HEADERS = ["Dato", "Aktivitet", "Sted", "Start", "Slutt"]


class SpondExporter:
    """Export a :class:`~tournament_scheduler.models.SeasonPlan` to Spond's Excel-import format.

    Parameters
    ----------
    game_level:
        If ``True`` (default), each row is a single game (``"U10: Jar 1 vs Jar 2"``).
        If ``False``, each row is a tournament summary (``"U10 Turnering — Jarhallen"``).
    """

    def __init__(self, *, game_level: bool = True) -> None:
        self.game_level = game_level

    def export(self, plan: SeasonPlan, output_path: str) -> str:
        """Build and save a Spond-compatible Excel workbook to *output_path*.

        Returns the path written (as a string).
        """
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "Sesongplan"

        self._write_sheet(sheet, plan)
        self._autosize_columns(sheet)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(out))
        console.print(f"[green]Spond-eksport lagret til[/green] [bold]{out}[/bold]")
        return str(out)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_sheet(self, sheet: Worksheet, plan: SeasonPlan) -> None:
        sheet.append(_SPOND_HEADERS)
        self._style_header_row(sheet)

        for tournament in sorted(plan.tournaments, key=lambda t: t.date):
            date_str = tournament.date.strftime("%d.%m.%Y")
            arena = tournament.arena
            age_group = tournament.age_group

            if self.game_level and tournament.games:
                for game in tournament.games:
                    activity = f"{age_group}: {game.home.label} vs {game.away.label}"
                    sheet.append([date_str, activity, arena, "", ""])
            else:
                team_list = ", ".join(t.label for t in tournament.teams)
                activity = f"{age_group} Turnering — {arena}"
                note = f"Lag: {team_list}" if team_list else ""
                sheet.append([date_str, activity, arena, "", note])

    # ------------------------------------------------------------------
    # Helpers (mirror SeasonPlanExporter conventions)
    # ------------------------------------------------------------------

    @staticmethod
    def _style_header_row(sheet: Worksheet) -> None:
        for cell in sheet[1]:
            cell.font = cell.font.copy(bold=True)

    @staticmethod
    def _autosize_columns(sheet: Worksheet, max_width: int = 60) -> None:
        widths: dict[str, int] = {}
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                col_letter = cell.column_letter
                width = len(str(cell.value))
                widths[col_letter] = max(widths.get(col_letter, 0), width)
        for col_letter, width in widths.items():
            sheet.column_dimensions[col_letter].width = min(width + 2, max_width)
