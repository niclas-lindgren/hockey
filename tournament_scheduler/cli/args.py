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
    status.add_argument(
        "--json",
        action="store_true",
        help="Print the AI-operator run manifest as JSON instead of the human-readable summary",
    )

    # sources
    sources = sub.add_parser("sources", help="Calendar source health commands")
    sources_sub = sources.add_subparsers(dest="sources_command")
    sources_status = sources_sub.add_parser(
        "status",
        help="Show per-source health: reachability, event counts, cache age, and suggested recovery actions",
    )
    sources_status.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    sources_status.add_argument(
        "--json",
        action="store_true",
        help="Print source health as a JSON array of capability results instead of a human-readable summary",
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
    run.add_argument(
        "--iterations",
        type=int,
        default=1,
        metavar="N",
        help="Run Stage 3 planner N times with different random seeds and keep the best plan (default: 1)",
    )
    run.add_argument(
        "--mid-planning-critic-iterations",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Optionally run a Stage 3 checkpoint critic loop before Stage 4 export: "
            "inspect the plan, inject structured planner hints, and re-run Stage 3 up to N times "
            "(default: 0/off)"
        ),
    )
    # Headless / CI judge backend: set RVV_JUDGE_BACKEND=claude|openai|llm_bridge
    # plus the matching API key (ANTHROPIC_API_KEY / OPENAI_API_KEY) to enable
    # inter-stage LLM judgment when no harness session is present.
    # See docs/rvv-miniputt-pipeline.md §"Headless / CI usage" for details.

    # operator — the goal-oriented AI operator entry point (see docs/ai-operator-product-direction.md)
    operator = sub.add_parser(
        "operator",
        help="Goal-oriented AI operator commands (thin wrapper around the portable pipeline)",
    )
    operator_sub = operator.add_subparsers(dest="operator_command")

    op_run = operator_sub.add_parser(
        "run",
        help="Produce the best trustworthy season plan: inspects workspace state, "
        "resumes from the earliest stale/pending capability, and reports a "
        "structured summary",
    )
    op_run.add_argument(
        "--objective",
        default=None,
        help="Explicit objective for this run (default: produce the best trustworthy season plan)",
    )
    op_run.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    op_run.add_argument(
        "--input",
        default="input.xlsx",
        help="Path to pipeline input workbook (default: input.xlsx)",
    )
    op_run.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )
    op_run.add_argument(
        "--resume-from",
        default=None,
        help="Force resuming from a specific stage number or alias, overriding auto-detection "
        "(1-4, config, scraping, planning, export)",
    )
    op_run.add_argument(
        "--force",
        action="store_true",
        help="Run the full pipeline from stage 1 even if every stage already looks done and fresh",
    )
    op_run.add_argument(
        "--log-level",
        default="info",
        choices=["info", "verbose"],
        help="Console/log verbosity hint (default: info)",
    )
    op_run.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force calendar cache refresh before Stage 2 when that stage runs",
    )
    op_run.add_argument(
        "--non-strict",
        action="store_true",
        help="Continue on blocked sources or warnings instead of escalating",
    )
    op_run.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="Treat blocked sources as an operator-approved skip and keep partial results",
    )
    op_run.add_argument(
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir instead of a timestamped subfolder",
    )
    op_run.set_defaults(timestamped_export=True)
    op_run.add_argument(
        "--iterations",
        type=int,
        default=1,
        metavar="N",
        help="Run Stage 3 planner N times with different random seeds and keep the best plan (default: 1)",
    )
    op_run.add_argument(
        "--mid-planning-critic-iterations",
        type=int,
        default=0,
        metavar="N",
        help="Optionally run a Stage 3 checkpoint critic loop before Stage 4 export (default: 0/off)",
    )

    op_questions = operator_sub.add_parser(
        "questions",
        help="List pending (unanswered) escalation questions raised by the last operator run",
    )
    op_questions.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    op_questions.add_argument(
        "--json",
        action="store_true",
        help="Print pending questions as JSON instead of a human-readable list",
    )
    op_questions.add_argument(
        "--all",
        action="store_true",
        help="Include answered and stale questions too, not just unanswered ones (issue #12)",
    )

    op_answer = operator_sub.add_parser(
        "answer",
        help="Record a durable human answer to a pending escalation question",
    )
    op_answer.add_argument("question_id", help="Question id, as shown by 'operator questions'")
    op_answer.add_argument("answer", help="The human's answer/decision")
    op_answer.add_argument(
        "--decided-by",
        default=None,
        help="Optional name/identifier of who made this decision, for the audit trail",
    )
    op_answer.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    op_promote = operator_sub.add_parser(
        "promote",
        help="Promote an answered decision to a broader scope so it is reused across runs/inputs/seasons (issue #12)",
    )
    op_promote.add_argument("question_id", help="Question id to promote, as shown by 'operator questions --all'")
    op_promote.add_argument(
        "scope",
        choices=["input_version", "season", "workspace"],
        help="Target scope — must be broader than the question's current scope",
    )
    op_promote.add_argument(
        "--scope-key",
        default="",
        help="Scope key for the target scope (required for 'season'; ignored for 'workspace')",
    )
    op_promote.add_argument(
        "--decided-by",
        default=None,
        help="Optional name/identifier of who made this promotion, for the audit trail",
    )
    op_promote.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    op_health = operator_sub.add_parser(
        "health",
        help="Check whether the run manifest is durably writable and free of unrecovered corruption (issue #14)",
    )
    op_health.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    op_health.add_argument(
        "--json",
        action="store_true",
        help="Print the health check result as JSON",
    )

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

    # scrape-merge — rebuild Stage 2 checkpoint from recovered cache data
    scrape_merge = sub.add_parser(
        "scrape-merge",
        help="Rebuild the Stage 2 checkpoint from recovered cache data",
    )
    scrape_merge.add_argument(
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
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir instead of a timestamped subfolder",
    )
    replan.set_defaults(timestamped_export=True)

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
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir instead of a timestamped subfolder",
    )
    adjust.set_defaults(timestamped_export=False)

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
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir instead of a timestamped subfolder",
    )
    review.set_defaults(timestamped_export=False)

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

    # critic
    critic = sub.add_parser(
        "critic",
        help="Run the plan critic on an existing Stage 3 checkpoint and print issues",
    )
    critic.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    # auto-adjust
    auto_adjust = sub.add_parser(
        "auto-adjust",
        help=(
            "Automatically apply auto-fixable critic issues (arena-day collisions, "
            "hosting clumps) in a loop until resolved or max iterations reached"
        ),
    )
    auto_adjust.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    auto_adjust.add_argument(
        "--export-dir",
        default="export",
        help="Export output directory (default: export)",
    )
    auto_adjust.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum number of adjustment iterations (default: 3)",
    )
    auto_adjust.add_argument(
        "--no-timestamped-export",
        dest="timestamped_export",
        action="store_false",
        help="Write exports flat into --export-dir instead of a timestamped subfolder",
    )
    auto_adjust.set_defaults(timestamped_export=True)

    # verdict
    verdict = sub.add_parser(
        "verdict",
        help="Read the Stage 3 checkpoint and print the tone (strong/mixed/rough) and key scores",
    )
    verdict.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )

    # candidates
    candidates = sub.add_parser(
        "candidates",
        help="Compare Stage 3 plan candidates (from --iterations > 1): reproducibility "
        "metadata, ranking, and the most consequential trade-offs vs. the runner-up",
    )
    candidates.add_argument(
        "--work-dir",
        default=".pipeline",
        help="Pipeline work directory (default: .pipeline)",
    )
    candidates.add_argument(
        "--json",
        action="store_true",
        help="Print candidates as JSON instead of a human-readable comparison",
    )

    return parser
