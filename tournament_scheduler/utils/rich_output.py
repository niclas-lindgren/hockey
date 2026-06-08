"""Rich-based output formatting for tournament scheduler."""

from datetime import date
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.text import Text

if TYPE_CHECKING:
    from tournament_scheduler.models import SeasonPlan, Tournament

console = Console()


class TournamentOutput:
    """Handles Rich-based output formatting."""

    @staticmethod
    def print_header(title: str) -> None:
        """Print section header.

        Args:
            title: Section title
        """
        console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
        console.print(f"[bold cyan]{title}[/bold cyan]")
        console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

    @staticmethod
    def print_success(message: str) -> None:
        """Print success message.

        Args:
            message: Success message
        """
        console.print(f"[green]✓[/green] {message}")

    @staticmethod
    def print_warning(message: str) -> None:
        """Print warning message.

        Args:
            message: Warning message
        """
        console.print(f"[yellow]⚠[/yellow]  {message}")

    @staticmethod
    def print_error(message: str) -> None:
        """Print error message.

        Args:
            message: Error message
        """
        console.print(f"[red]✗[/red] {message}")

    @staticmethod
    def print_info(message: str) -> None:
        """Print info message.

        Args:
            message: Info message
        """
        console.print(f"[blue]ℹ[/blue]  {message}")

    @staticmethod
    def create_progress() -> Progress:
        """Create progress indicator.

        Returns:
            Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        )

    @staticmethod
    def print_conflict_table(
        title: str,
        conflicts: List[Tuple[date, str]],
        max_rows: int = 10
    ) -> None:
        """Print conflicts in a table.

        Args:
            title: Table title
            conflicts: List of (date, reason) tuples
            max_rows: Maximum rows to display
        """
        if not conflicts:
            return

        table = Table(
            title=f"⚠️  {title} ({len(conflicts)} datoer blokkert)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Dato", style="cyan", no_wrap=True)
        table.add_column("Grunn", style="yellow")

        for conflict_date, reason in sorted(conflicts)[:max_rows]:
            table.add_row(
                conflict_date.strftime('%Y-%m-%d'),
                reason[:80]
            )

        if len(conflicts) > max_rows:
            table.add_row(
                "[dim]...[/dim]",
                f"[dim]og {len(conflicts) - max_rows} flere datoer[/dim]"
            )

        console.print(table)

    @staticmethod
    def print_available_dates(
        dates_with_slots: List[Tuple[date, str, str, bool]],
        show_details: bool = True
    ) -> None:
        """Print available dates with time slots.

        Args:
            dates_with_slots: List of (date, day_name, time_slot, has_warning) tuples
            show_details: Whether to show detailed time slot information
        """
        table = Table(
            title="✓ Ledige datoer",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold green"
        )
        table.add_column("Dato", style="green", no_wrap=True)
        table.add_column("Dag", style="cyan")
        table.add_column("Foreslått tidspunkt", style="yellow")
        table.add_column("Advarsel", style="red")

        for check_date, day_name, time_slot, has_warning in dates_with_slots:
            warning = "⚠️  HELGEKONFLIKT" if has_warning else ""
            table.add_row(
                check_date.strftime('%Y-%m-%d'),
                day_name,
                time_slot or "-",
                warning
            )

        console.print(table)

    @staticmethod
    def print_summary(
        total_checked: int,
        available_count: int,
        blocked_count: int,
        breakdown: Dict[str, int]
    ) -> None:
        """Print search summary.

        Args:
            total_checked: Total dates checked
            available_count: Number of available dates
            blocked_count: Number of blocked dates
            breakdown: Conflict breakdown by checker type
        """
        # Create summary panel
        summary_text = Text()
        summary_text.append(f"Søkte: {total_checked} helgedatoer\n", style="bold")
        summary_text.append(f"Ledige: {available_count} datoer\n", style="green")
        summary_text.append(f"Blokkert: {blocked_count} datoer\n", style="red")

        if breakdown:
            summary_text.append("\nGrunner for blokkerte datoer:\n", style="bold")
            checker_names = {
                'ice_hall': 'Ishall turneringer',
                'timeslot': 'Ingen ledige tidslukker',
                'team_conflict': 'Lag opptatt',
                'excel_team_conflict': 'Excel konflikter',
                'holiday': 'Helligdager',
                'ball_hall': 'Ballhall opptatt'
            }
            for checker_name, count in sorted(breakdown.items()):
                if checker_name != 'ball_hall_warning' and count > 0:
                    display_name = checker_names.get(checker_name, checker_name.replace('_', ' ').title())
                    summary_text.append(f"  • {display_name}: {count} datoer\n", style="yellow")

        console.print(Panel(
            summary_text,
            title="Søkeresultat",
            border_style="cyan",
            box=box.DOUBLE
        ))

    @staticmethod
    def print_no_dates_found() -> None:
        """Print no dates available message."""
        console.print(Panel(
            "[bold red]Ingen ledige datoer funnet[/bold red]\n\n"
            "Alle datoer har konflikter. Prøv:\n"
            "  • Utvid datoperioden\n"
            "  • Sjekk færre kalendere\n"
            "  • Sjekk om lag-planer kan justeres",
            title="✗ Ingen resultater",
            border_style="red",
            box=box.DOUBLE
        ))

    @staticmethod
    def print_time_slots_detail(
        dates_with_all_slots: List[Tuple[date, str, List[Tuple[str, str]]]]
    ) -> None:
        """Print detailed time slot information.

        Args:
            dates_with_all_slots: List of (date, day_name, [(start, end), ...]) tuples
        """
        console.print(f"\n[bold]{'─' * 60}[/bold]")
        console.print("[bold]Detaljert tidsluke-oversikt:[/bold]\n")

        for check_date, day_name, slots in dates_with_all_slots:
            console.print(f"[cyan]{check_date.strftime('%Y-%m-%d')} ({day_name}):[/cyan]")
            for start, end in slots:
                console.print(f"  • {start}-{end}")
            console.print()

    @staticmethod
    def print_season_overview(plan: "SeasonPlan") -> None:
        """Print a season overview table — one row per proposed tournament.

        Args:
            plan: The proposed SeasonPlan
        """
        if not plan.tournaments:
            console.print(Panel(
                "[bold red]Ingen turneringer foreslått[/bold red]",
                title="✗ Ingen sesongplan",
                border_style="red",
                box=box.DOUBLE
            ))
            return

        table = Table(
            title=f"📅 Sesongoversikt ({len(plan.tournaments)} turneringer)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Dato", style="cyan", no_wrap=True)
        table.add_column("Aldersgruppe", style="green")
        table.add_column("Arena", style="yellow")
        table.add_column("Vertsklubb", style="blue")
        table.add_column("Lag", style="white")

        for tournament in sorted(plan.tournaments, key=lambda t: t.date):
            table.add_row(
                tournament.date.strftime('%Y-%m-%d'),
                tournament.age_group,
                tournament.arena,
                tournament.host_club or "-",
                ", ".join(team.label for team in tournament.teams)
            )

        console.print(table)

    @staticmethod
    def print_tournament_schedule(tournament: "Tournament") -> None:
        """Print a single tournament's participating teams and full game schedule.

        Games are grouped by parallel slot/round so the round-robin layout
        within the tournament is easy to review.

        Args:
            tournament: The Tournament to render
        """
        console.print(
            f"\n[bold cyan]{tournament.date.strftime('%Y-%m-%d')} — "
            f"{tournament.age_group} — {tournament.arena}[/bold cyan]"
        )
        console.print(
            f"[white]Deltakende lag:[/white] "
            f"{', '.join(team.label for team in tournament.teams)}\n"
        )

        if not tournament.games:
            console.print("[dim]Ingen kamper generert ennå[/dim]")
            return

        table = Table(
            title=f"🏒 Kampoppsett ({len(tournament.games)} kamper)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Kamp #", style="dim", no_wrap=True)
        table.add_column("Parallellbane", style="cyan", no_wrap=True)
        table.add_column("Hjemmelag", style="green")
        table.add_column("Bortelag", style="yellow")

        for game_number, game in enumerate(tournament.games, start=1):
            table.add_row(
                str(game_number),
                str(game.parallel_slot + 1),
                game.home.label,
                game.away.label
            )

        console.print(table)

    @staticmethod
    def print_diversity_summary(plan: "SeasonPlan") -> None:
        """Print a summary panel of matchup-diversity metrics for a season plan.

        Args:
            plan: The proposed SeasonPlan
        """
        summary_text = Text()
        summary_text.append(f"Antall turneringer: {len(plan.tournaments)}\n", style="bold")
        summary_text.append(
            f"Mangfoldscore (andel nye lagkonstellasjoner): {plan.diversity_score:.2f}\n",
            style="green"
        )
        summary_text.append(
            f"Kampmangfold (andel ferske motstanderpar): {plan.pairwise_matchup_score:.2f}\n",
            style="green"
        )
        summary_text.append(
            f"Månedsbalanse (jevn fordeling over sesongen): {plan.month_balance_score:.2f}\n",
            style="green"
        )

        if plan.arena_counts:
            summary_text.append("\nTurneringer per arena:\n", style="bold")
            for arena, count in sorted(plan.arena_counts.items()):
                if arena.startswith("_"):
                    continue
                summary_text.append(f"  • {arena}: {count} turnering(er)\n", style="cyan")

        collisions = plan.arena_counts.get("_age_group_overlap_collisions", 0)
        if collisions:
            summary_text.append(
                f"\n⚠ {collisions} uunngåelig(e) kollisjon(er) mellom overlappende "
                "aldersgrupper samme helg\n",
                style="red"
            )
        else:
            summary_text.append(
                "\n✓ Ingen kollisjoner mellom overlappende aldersgrupper\n",
                style="green"
            )

        console.print(Panel(
            summary_text,
            title="Mangfold og fordeling",
            border_style="cyan",
            box=box.DOUBLE
        ))
