"""CSV exporter — writes a flat game schedule and a season overview.

Writes two CSV files:

1. ``<output_path>`` — one row per game with columns:
   ``date, arena, age_group, home, away, parallel_slot``

2. ``<output_path_stem>_overview.csv`` — one row per tournament with columns:
   ``date, arena, age_group, host_club, team_count, game_count``
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from ..models import SeasonPlan


class CsvExporter:
    """Export a :class:`~tournament_scheduler.models.SeasonPlan` to CSV files."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        plan: SeasonPlan,
        output_path: str | os.PathLike[str],
    ) -> tuple[str, str]:
        """Write games CSV and overview CSV.

        Returns
        -------
        tuple[str, str]
            ``(games_path, overview_path)``
        """
        games_path = Path(output_path)
        games_path.parent.mkdir(parents=True, exist_ok=True)

        stem = games_path.stem
        overview_path = games_path.parent / f"{stem}_overview.csv"

        self._write_games(plan, games_path)
        self._write_overview(plan, overview_path)

        return str(games_path), str(overview_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_games(self, plan: SeasonPlan, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["date", "arena", "age_group", "home", "away", "parallel_slot"])
            for tournament in plan.tournaments:
                date_str = tournament.date.isoformat()
                for game in tournament.games:
                    writer.writerow([
                        date_str,
                        tournament.arena,
                        tournament.age_group,
                        game.home.label,
                        game.away.label,
                        game.parallel_slot,
                    ])

    def _write_overview(self, plan: SeasonPlan, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "date", "arena", "age_group", "host_club", "team_count", "game_count"
            ])
            for tournament in plan.tournaments:
                writer.writerow([
                    tournament.date.isoformat(),
                    tournament.arena,
                    tournament.age_group,
                    tournament.host_club or "",
                    len(tournament.teams),
                    len(tournament.games),
                ])
