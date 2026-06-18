"""Argument parsing for the RVV Miniputt CLI."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rvv-miniputt",
        description="RVV Miniputt — tournament scheduler pipeline CLI",
    )
    sub = parser.add_subparsers(dest="command", title="commands")

    # status
    status = sub.add_parser("status", help="Show checkpoint/log status for the pipeline work directory")
    status.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

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
        default="input.xlsx",
        help="Path to pipeline input workbook (default: input.xlsx)",
    )
    run.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )
    run.add_argument(
        "--resume-from",
        default="1",
        help="Resume from stage number or alias (1-4, config, scraping, planning, export)",
    )
    run.add_argument(
        "--log-level",
        default="info",
        choices=["info", "verbose"],
        help="Console/log verbosity hint (default: info)",
    )
    run.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force calendar cache refresh before Stage 2 when that stage runs",
    )
    run.add_argument(
        "--non-strict",
        action="store_true",
        help="Continue on blocked sources or warnings",
    )
    run.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="Treat blocked sources as an operator-approved skip and keep partial results",
    )
    run.add_argument(
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir instead of a timestamped subfolder",
    )
    run.set_defaults(timestamped_export=True)
    # Headless / CI judge backend: set RVV_JUDGE_BACKEND=claude|openai|llm_bridge
    # plus the matching API key (ANTHROPIC_API_KEY / OPENAI_API_KEY) to enable
    # inter-stage LLM judgment when no harness session is present.
    # See docs/rvv-miniputt-pipeline.md §"Headless / CI usage" for details.

    # logs
    logs = sub.add_parser("logs", help="Show structured pipeline run logs")
    logs.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    logs_sub = logs.add_subparsers(dest="logs_command")

    logs_list = logs_sub.add_parser("list", help="List recent pipeline runs")
    logs_list.add_argument("--count", type=int, default=10, help="How many recent runs to show (default: 10)")
    logs_list.add_argument("--work-dir", default=".pipeline", help=argparse.SUPPRESS)

    logs_show = logs_sub.add_parser("show", help="Show details for one run")
    logs_show.add_argument("run_id", nargs="?", default="latest", help="Run id, or 'latest' (default)")
    logs_show.add_argument("--work-dir", default=".pipeline", help=argparse.SUPPRESS)

    logs_stats = logs_sub.add_parser("stats", help="Show aggregate run statistics")
    logs_stats.add_argument("--work-dir", default=".pipeline", help=argparse.SUPPRESS)

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

    # recovery-targets — list blocked/zero-event sources from Stage 2 checkpoint
    recovery = sub.add_parser(
        "recovery-targets",
        help="List blocked or zero-event sources from the Stage 2 checkpoint as JSON",
    )
    recovery.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    # recovery-inject — inject recovered events into the unified cache from stdin
    recovery_inject = sub.add_parser(
        "recovery-inject",
        help="Inject a JSON event list from stdin into the cache for a given source",
    )
    recovery_inject.add_argument(
        "--source",
        required=True,
        help="Source name to patch (e.g. 'Sandefjord', 'Tønsberg')",
    )
    recovery_inject.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
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

    # adjust — manual organizer loop for the final plan
    adjust = sub.add_parser(
        "adjust",
        help="Apply manual organizer adjustments (lock/ban/pin/host rules) and re-export",
    )
    adjust.add_argument(
        "--lock-date",
        action="append",
        default=[],
        help="Lock a tournament date (repeatable, YYYY-MM-DD)",
    )
    adjust.add_argument(
        "--ban-date",
        action="append",
        default=[],
        help="Ban a tournament date from future planning (repeatable, YYYY-MM-DD)",
    )
    adjust.add_argument(
        "--pin-tournament",
        action="append",
        default=[],
        help="Pin a tournament ID so it is preserved during adjustments",
    )
    adjust.add_argument(
        "--force-host-club",
        action="append",
        default=[],
        help="Prefer this club as host when reapplying host rules (repeatable)",
    )
    adjust.add_argument(
        "--exclude-host-club",
        action="append",
        default=[],
        help="Exclude this club from host selection (repeatable)",
    )
    adjust.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    adjust.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )
    adjust.add_argument(
        "--timestamped-export",
        action="store_true",
        help="Write exports to a timestamped subfolder (diffable between runs)",
    )

    # review — apply club responses from review packets
    review = sub.add_parser(
        "review",
        help="Apply club review responses (accept/change-request) and re-export",
    )
    review.add_argument(
        "--response",
        action="append",
        required=True,
        help="Response file or packet directory with response_template.json (repeatable)",
    )
    review.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    review.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )
    review.add_argument(
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
