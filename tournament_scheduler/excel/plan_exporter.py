"""Excel exporter for season plans.

`SeasonPlanExporter` is a write-side sibling to the read-only
`ExcelTournamentReader` in `tournament_scheduler.excel.tournament_reader`. It
builds a workbook with:

  (a) a season-overview sheet — one row per tournament: date, weekday,
      age group/gender, arena/venue, and the participating teams; and
  (b) a per-tournament sheet (one sheet per tournament, falling back to a
      grouped block on a single sheet if the plan is too large for Excel's
      31-character / unique-name sheet limits) listing that tournament's
      full round-robin game schedule (home/away teams + parallel slot).

The resulting workbook is saved to a user-specified `.xlsx` path.
"""

from datetime import date
from typing import List, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from rich.console import Console

from tournament_scheduler.models import SeasonPlan, Tournament

console = Console()


# Norwegian weekday names (Monday=0 .. Sunday=6), matching the project's
# Norwegian-language interactive CLI conventions.
_NORWEGIAN_WEEKDAYS = [
    "mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag",
]

_OVERVIEW_HEADERS = ["Dato", "Ukedag", "Aldersgruppe", "Arena", "Vertsklubb", "Lag"]
_GAMES_HEADERS = ["Kamp #", "Hjemmelag", "Bortelag", "Parallellbane"]

# Excel worksheet titles cannot exceed 31 characters and must be unique.
_MAX_SHEET_TITLE_LENGTH = 31


class SeasonPlanExporter:
    """Writes a `SeasonPlan` to an Excel workbook (season overview + per-tournament games)."""

    def __init__(self):
        self.workbook: Optional[openpyxl.Workbook] = None

    def export(self, plan: SeasonPlan, output_path: str) -> str:
        """Build and save the workbook for `plan` to `output_path`.

        Returns the path the workbook was saved to.
        """
        self.workbook = openpyxl.Workbook()

        overview_sheet = self.workbook.active
        overview_sheet.title = "Sesongoversikt"
        self._write_overview_sheet(overview_sheet, plan)

        used_titles = {overview_sheet.title}
        for index, tournament in enumerate(plan.tournaments, start=1):
            sheet = self.workbook.create_sheet(title=self._unique_sheet_title(tournament, index, used_titles))
            used_titles.add(sheet.title)
            self._write_tournament_sheet(sheet, tournament)

        self.workbook.save(output_path)
        console.print(f"[green]Sesongplanen ble eksportert til[/green] [bold]{output_path}[/bold]")
        return output_path

    # ------------------------------------------------------------------
    # Season-overview sheet
    # ------------------------------------------------------------------

    def _write_overview_sheet(self, sheet: Worksheet, plan: SeasonPlan) -> None:
        sheet.append(_OVERVIEW_HEADERS)
        self._style_header_row(sheet)

        for tournament in plan.tournaments:
            sheet.append([
                self._format_date(tournament.date),
                self._weekday_name(tournament.date),
                tournament.age_group,
                tournament.arena,
                tournament.host_club or "",
                ", ".join(team.label for team in tournament.teams),
            ])

        self._autosize_columns(sheet)

    # ------------------------------------------------------------------
    # Per-tournament game-schedule sheets
    # ------------------------------------------------------------------

    def _write_tournament_sheet(self, sheet: Worksheet, tournament: Tournament) -> None:
        title_row = (
            f"{self._format_date(tournament.date)} ({self._weekday_name(tournament.date)}) — "
            f"{tournament.age_group} — {tournament.arena}"
        )
        sheet.append([title_row])
        sheet.append([])
        sheet.append([f"Deltakende lag: {', '.join(team.label for team in tournament.teams)}"])
        sheet.append([])

        sheet.append(_GAMES_HEADERS)
        header_row_index = sheet.max_row
        for cell in sheet[header_row_index]:
            cell.font = cell.font.copy(bold=True)

        for game_number, game in enumerate(tournament.games, start=1):
            sheet.append([
                game_number,
                game.home.label,
                game.away.label,
                game.parallel_slot + 1,  # 1-based for human-friendly display
            ])

        self._autosize_columns(sheet)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%d.%m.%Y")

    @staticmethod
    def _weekday_name(value: date) -> str:
        return _NORWEGIAN_WEEKDAYS[value.weekday()]

    @staticmethod
    def _style_header_row(sheet: Worksheet) -> None:
        for cell in sheet[1]:
            cell.font = cell.font.copy(bold=True)

    @staticmethod
    def _autosize_columns(sheet: Worksheet, max_width: int = 60) -> None:
        """Roughly size each column to fit its widest cell (capped at `max_width`)."""
        widths = {}
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                column_letter = cell.column_letter
                length = len(str(cell.value))
                widths[column_letter] = max(widths.get(column_letter, 0), length)

        for column_letter, width in widths.items():
            sheet.column_dimensions[column_letter].width = min(width + 2, max_width)

    @staticmethod
    def _unique_sheet_title(tournament: Tournament, index: int, used_titles) -> str:
        """Build a unique, Excel-valid (<=31 chars) sheet title for a tournament.

        Format: "<DD.MM> <age_group> <arena>" truncated as needed, with a
        numeric suffix appended if a collision would otherwise occur.
        """
        date_part = tournament.date.strftime("%d.%m")
        base = f"{date_part} {tournament.age_group} {tournament.arena}".strip()
        base = SeasonPlanExporter._sanitize_sheet_title(base)

        title = base[:_MAX_SHEET_TITLE_LENGTH]
        if title not in used_titles:
            return title

        # Collision — append a numeric suffix, trimming the base as needed.
        suffix = f" ({index})"
        trimmed_len = _MAX_SHEET_TITLE_LENGTH - len(suffix)
        title = f"{base[:trimmed_len]}{suffix}"
        return title

    @staticmethod
    def _sanitize_sheet_title(title: str) -> str:
        """Strip characters that Excel does not allow in sheet titles."""
        invalid_chars = set('[]:*?/\\')
        return "".join(ch for ch in title if ch not in invalid_chars).strip()
