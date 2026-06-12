"""Spond Excel exporter — produces a single-sheet workbook for Spond's Season Planner import.

The workbook keeps Spond's expected core columns (Dato/Aktivitet/Sted/
Start/Slutt) but adds filter-friendly tournament metadata so organizers can
sort and filter the sheet before importing.

Two output modes are supported:

* **tournament-level** (default) — one row per tournament: ``"U10 Turnering — Jarhallen"``
* **game-level** — one row per internal game: ``"U10: Jar 1 vs Jar 2"``

The resulting ``.xlsx`` file can be imported directly into Spond Club's
Season Planner (Sesongplanlegger → Importer fra Excel).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from rich.console import Console

from ..models import SeasonPlan, Tournament

console = Console()

_SPOND_HEADERS = [
    "Dato",
    "Aktivitet",
    "Sted",
    "Start",
    "Slutt",
    "Aldersgruppe",
    "Vertsklubb",
    "Deltakende klubber",
    "Deltakende lag",
    "Import scope",
]


class SpondExporter:
    """Export a :class:`~tournament_scheduler.models.SeasonPlan` to Spond's Excel-import format.

    Parameters
    ----------
    game_level:
        If ``True``, each row is a single game (``"U10: Jar 1 vs Jar 2"``).
        If ``False`` (default), each row is a tournament summary
        (``"U10 Turnering — Jarhallen"``).
    """

    def __init__(self, *, game_level: bool = False) -> None:
        self.game_level = game_level

    def export(
        self,
        plan: SeasonPlan,
        output_path: str,
        *,
        club: str | None = None,
        round_length_for_age_group: Optional[dict[str, int]] = None,
    ) -> str:
        """Build and save a Spond-compatible Excel workbook to *output_path*."""
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = "Sesongplan"

        self._write_sheet(
            sheet,
            plan,
            club=club,
            round_length_for_age_group=round_length_for_age_group,
        )
        self._style_header_row(sheet)
        self._configure_sheet(sheet)
        self._autosize_columns(sheet)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(out))
        console.print(f"[green]Spond-eksport lagret til[/green] [bold]{out}[/bold]")
        return str(out)

    def export_for_clubs(
        self,
        plan: SeasonPlan,
        output_dir: str | os.PathLike[str],
        *,
        basename: str = "season_plan_spond",
        clubs: Iterable[str] | None = None,
        round_length_for_age_group: Optional[dict[str, int]] = None,
    ) -> dict[str, str]:
        """Write one prefiltered workbook per club and return club -> path."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        club_list = list(clubs) if clubs is not None else sorted(
            {team.club for tournament in plan.tournaments for team in tournament.teams}
        )

        written: dict[str, str] = {}
        for club in club_list:
            slug = self._slugify(club)
            path = out_dir / f"{basename}_{slug}.xlsx"
            written[club] = self.export(
                plan,
                str(path),
                club=club,
                round_length_for_age_group=round_length_for_age_group,
            )
        return written

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_sheet(
        self,
        sheet: Worksheet,
        plan: SeasonPlan,
        *,
        club: str | None = None,
        round_length_for_age_group: Optional[dict[str, int]] = None,
    ) -> None:
        round_length_for_age_group = round_length_for_age_group or {}
        sheet.append(_SPOND_HEADERS)

        for tournament in sorted(plan.tournaments, key=lambda t: t.date):
            if club and not any(team.club == club for team in tournament.teams):
                continue

            if self.game_level:
                for row in self._game_rows_for_tournament(tournament, round_length_for_age_group):
                    sheet.append(row)
            else:
                sheet.append(self._summary_row_for_tournament(tournament, round_length_for_age_group))

        if sheet.max_row:
            end_ref = sheet.cell(row=sheet.max_row, column=sheet.max_column).coordinate
            sheet.auto_filter.ref = f"A1:{end_ref}"
        sheet.freeze_panes = "A2"

    def _summary_row_for_tournament(
        self,
        tournament: Tournament,
        round_length_for_age_group: dict[str, int],
    ) -> list[str]:
        date_str = tournament.date.strftime("%d.%m.%Y")
        arena = tournament.arena
        age_group = tournament.age_group
        clubs = self._join_unique(team.club for team in tournament.teams)
        teams = ", ".join(team.label for team in tournament.teams)
        start_time = tournament.start_time or ""
        end_time = ""
        if tournament.start_time:
            round_length = round_length_for_age_group.get(tournament.age_group)
            if round_length:
                end_time = tournament.end_time(round_length) or ""

        activity = f"{age_group} Turnering — {arena}"
        if tournament.cancelled:
            activity = f"AVLYST: {activity}"

        return [
            date_str,
            activity,
            arena,
            start_time,
            end_time,
            age_group,
            tournament.host_club or "",
            clubs,
            teams,
            "turnering",
        ]

    def _game_rows_for_tournament(
        self,
        tournament: Tournament,
        round_length_for_age_group: dict[str, int],
    ) -> list[list[str]]:
        rows: list[list[str]] = []
        date_str = tournament.date.strftime("%d.%m.%Y")
        arena = tournament.arena
        age_group = tournament.age_group
        clubs = self._join_unique(team.club for team in tournament.teams)
        start_time = tournament.start_time or ""
        end_time = ""
        if tournament.start_time:
            round_length = round_length_for_age_group.get(tournament.age_group)
            if round_length:
                end_time = tournament.end_time(round_length) or ""

        for game in tournament.games:
            activity = f"{age_group}: {game.home.label} vs {game.away.label}"
            if tournament.cancelled:
                activity = f"AVLYST: {activity}"
            rows.append([
                date_str,
                activity,
                arena,
                start_time,
                end_time,
                age_group,
                tournament.host_club or "",
                clubs,
                f"{game.home.label}, {game.away.label}",
                "kamp",
            ])

        if not rows:
            rows.append(self._summary_row_for_tournament(tournament, round_length_for_age_group))
        return rows

    @staticmethod
    def _join_unique(values: Iterable[str]) -> str:
        seen: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.append(value)
        return ", ".join(seen)

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
        return slug or "club"

    # ------------------------------------------------------------------
    # Helpers (mirror SeasonPlanExporter conventions)
    # ------------------------------------------------------------------

    @staticmethod
    def _style_header_row(sheet: Worksheet) -> None:
        for cell in sheet[1]:
            cell.font = cell.font.copy(bold=True)

    @staticmethod
    def _configure_sheet(sheet: Worksheet) -> None:
        sheet.sheet_view.showGridLines = False

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
