import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { parseStatusArgs, parseLogsArgs, parseCalendarsArgs } from "../lib/parsers";
import { buildStatusText } from "../lib/pipeline-helpers";
import { buildLogsListText, buildLogsShowText, buildLogsStatsText } from "../lib/log-inspector";
import { runPipeline, type PipelineRunResult } from "../lib/pipeline-runner";
import { interactiveGuide } from "../lib/interactive-guide";
import { LOG_LEVELS } from "../lib/types";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";

/** Build the logs report text for a given args string. Shared by the command and tool. */
function buildLogsResult(rawArgs: unknown, cwd: string): { status: "success" | "failure"; text: string } {
  const params = parseLogsArgs(rawArgs);
  const workDir = resolve(cwd, params.work_dir ?? ".pipeline");
  const count = params.count ?? 10;

  switch (params.subcommand) {
    case "show":
      if (!params.run_id) {
        return { status: "failure", text: "Bruk: /rvv-miniputt logs show <run-id>" };
      }
      return { status: "success", text: buildLogsShowText(workDir, params.run_id) };
    case "stats":
      return { status: "success", text: buildLogsStatsText(workDir) };
    case "list":
    default:
      return { status: "success", text: buildLogsListText(workDir, count) };
  }
}

/** Run the calendars CLI (cache regen or full refresh). Shared by the command and tool. */
async function runCalendars(rawArgs: unknown, ctx: ExtensionContext): Promise<{ status: "success" | "failure"; text: string }> {
  const params = parseCalendarsArgs(rawArgs);
  const refresh = params.refresh ?? false;
  const workDir = params.work_dir ?? ".pipeline";

  const python = resolve(ctx.cwd, "venv", "bin", "python3");
  const exe = existsSync(python) ? python : "python3";
  const absWorkDir = resolve(ctx.cwd, workDir);

  // Use the unified Python CLI for both cache-only and full refresh.
  const cliArgs = [
    "-m", "tournament_scheduler.cli.rvv_cli",
    "calendars",
    "--work-dir", absWorkDir,
  ];
  if (refresh) cliArgs.push("--refresh");

  const lines: string[] = [];
  lines.push(refresh
    ? "🔄 Tvinger full re-skraping av kalendere (via rvv-miniputt CLI)..."
    : "Genererer kalendere fra cache...");

  try {
    const { execFile } = await import("node:child_process");
    const { promisify } = await import("node:util");
    const execFileAsync = promisify(execFile);
    const { copyFileSync } = await import("node:fs");

    const { stdout, stderr } = await execFileAsync(exe, cliArgs, {
      cwd: ctx.cwd,
      timeout: refresh ? 300_000 : 60_000,
    });

    if (stdout.trim()) lines.push(stdout.trim());

    // Copy season plan HTML next to calendars.html for navbar cross-linking
    if (!refresh) {
      try {
        const src = resolve(ctx.cwd, "export", "season_plan.html");
        const dst = resolve(absWorkDir, "season_plan.html");
        if (existsSync(src)) {
          copyFileSync(src, dst);
        }
      } catch { /* best-effort */ }
    }

    if (stderr.trim()) lines.push(`[stderr] ${stderr.trim()}`);
    return { status: "success", text: lines.join("\n") };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    lines.push(`Feil: ${msg}`);
    return { status: "failure", text: lines.join("\n") };
  }
}

function notifyPipelineResult(ctx: ExtensionContext, result: PipelineRunResult): void {
  ctx.ui.notify(result.text, result.status === "success" ? "info" : "error");
}

export default function rvvMiniputt(pi: ExtensionAPI): void {
  // -------------------------------------------------------------------------
  // /rvv-miniputt run
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt run", {
    description:
      "Kjør den firetrinns sesongplanleggingspipelinen for RVV-hockeyklubber. " +
      "Støtter gjenopptak fra et bestemt trinn.\n" +
      "Valgfrie flagg: --input <sti> --work-dir <sti> --resume-from <trinn> --export-dir <sti> " +
      "--log-level <info|verbose>\n" +
      "Hver kjøring logges strukturelt til .pipeline/logs/run-<dato>.jsonl for selvforbedringsanalyse.",
    getArgumentCompletions: (prefix) => {
      const words = ["--input", "--work-dir", "--resume-from", "--export-dir", "--log-level"];
      const filtered = words.filter((w) => w.startsWith(prefix));
      if (prefix.startsWith("--log-level")) {
        return LOG_LEVELS.map((value) => ({ value, label: value }));
      }
      return filtered.length ? filtered.map((value) => ({ value, label: value })) : null;
    },
    handler: async (args, ctx) => {
      notifyPipelineResult(ctx, await runPipeline(args, ctx));
    },
  });

  // -------------------------------------------------------------------------
  // /rvv-miniputt guide — interaktiv veiviser
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt guide", {
    description:
      "Åpne en interaktiv veiviser som stiller spørsmål om hva du vil gjøre " +
      "og guider deg gjennom pipeline-prosessen trinn for trinn.\n" +
      "Ingen parametere nødvendig — veiviseren spor deg om alt som trengs.\n" +
      "Anbefalt for nye brukere og énskjørs-kjøringer.",
    handler: async (_args, ctx) => {
      await interactiveGuide(ctx);
    },
  });

  // -------------------------------------------------------------------------
  // /rvv-miniputt status
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt status", {
    description:
      "Vis gjeldende status for alle fire trinn i sesongplanleggingspipelinen.\n" +
      "Valgfritt flagg: --work-dir <sti>",
    handler: async (args, ctx) => {
      const params = parseStatusArgs(args);
      const workDir = resolve(ctx.cwd, params.work_dir ?? ".pipeline");
      ctx.ui.notify(buildStatusText(workDir), "info");
    },
  });

  // -------------------------------------------------------------------------
  // /rvv-miniputt logs
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt logs", {
    description:
      "Vis pipeline-logging for selvforbedring. Underspørsmål:\n" +
      "  list              — vis de siste kjøringene (standard)\n" +
      "  show <run-id>     — vis detaljer for en bestemt kjøring\n" +
      "  show latest       — vis detaljer for den nyeste kjøringen\n" +
      "  stats             — vis aggregerte selvforbedringsstatistikker\n" +
      "Viser også turneringsoppdateringer (team-drop/date-move) i show-visningen.\n" +
      "Flagg: --count <N> (standard 10), --work-dir <sti>",
    getArgumentCompletions: (prefix) => {
      const words = ["list", "show", "stats", "--count", "--work-dir"];
      return words.filter((w) => w.startsWith(prefix)).map((value) => ({ value, label: value }));
    },
    handler: async (args, ctx) => {
      const result = buildLogsResult(args, ctx.cwd);
      ctx.ui.notify(result.text, result.status === "success" ? "info" : "error");
    },
  });

  // -------------------------------------------------------------------------
  // /rvv-miniputt calendars
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt calendars", {
    description:
      "Generer kalender-rapporter. Uten flagg: rask regenerering fra cache.\n" +
      "Flagg: --refresh (full re-skraping via rvv-miniputt CLI), --work-dir <sti>\n" +
      "Rapportene ligger i .pipeline/calendars.html og .pipeline/season_plan.html.",
    getArgumentCompletions: (prefix) => {
      const words = ["--refresh", "--work-dir"];
      return words.filter((w) => w.startsWith(prefix)).map((value) => ({ value, label: value }));
    },
    handler: async (args, ctx) => {
      const result = await runCalendars(args, ctx);
      ctx.ui.notify(result.text, result.status === "success" ? "info" : "error");
    },
  });

  // ===========================================================================
  // Agent-callable tools
  //
  // The /rvv-miniputt commands above are Pi slash commands, NOT shell binaries —
  // running `/rvv-miniputt run` via the Bash tool will fail with "command not
  // found". These tools are the agent-callable equivalents: call them directly
  // instead of shelling out, and instead of reimplementing the pipeline by
  // invoking tournament_scheduler.pipeline.stageN_* Python modules by hand
  // (which skips checkpointing, resumption, and structured run logging).
  // ===========================================================================

  pi.registerTool({
    name: "rvv_miniputt_run",
    label: "RVV Miniputt: Run Pipeline",
    description:
      "Run the RVV Miniputt season-planning pipeline (config → scraping → planning → export). " +
      "This is the agent-callable equivalent of the '/rvv-miniputt run' slash command — that " +
      "command is not a shell binary and cannot be invoked via Bash.",
    promptSnippet: "Run the RVV Miniputt season-planning pipeline",
    promptGuidelines: [
      "Use rvv_miniputt_run instead of running '/rvv-miniputt run' via Bash — it is a Pi slash command, not a shell command.",
      "Do not reimplement the pipeline by calling tournament_scheduler.pipeline.stageN_* Python modules directly; rvv_miniputt_run runs the full orchestrated pipeline with checkpointing and structured logging.",
    ],
    parameters: Type.Object({
      args: Type.Optional(Type.String({
        description: "Same flags as '/rvv-miniputt run', e.g. '--resume-from 2 --log-level verbose'",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const result = await runPipeline(params.args ?? "", ctx);
      return { content: [{ type: "text", text: result.text }], details: result };
    },
  });

  pi.registerTool({
    name: "rvv_miniputt_status",
    label: "RVV Miniputt: Status",
    description:
      "Show the current status of all four RVV Miniputt pipeline stages. " +
      "Agent-callable equivalent of the '/rvv-miniputt status' slash command.",
    promptSnippet: "Show RVV Miniputt pipeline stage status",
    parameters: Type.Object({
      args: Type.Optional(Type.String({
        description: "Same flags as '/rvv-miniputt status', e.g. '--work-dir .pipeline'",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const parsed = parseStatusArgs(params.args ?? "");
      const workDir = resolve(ctx.cwd, parsed.work_dir ?? ".pipeline");
      const text = buildStatusText(workDir);
      return { content: [{ type: "text", text }], details: { text } };
    },
  });

  pi.registerTool({
    name: "rvv_miniputt_logs",
    label: "RVV Miniputt: Logs",
    description:
      "Read RVV Miniputt pipeline run logs and self-improvement statistics " +
      "('list', 'show <run-id>'/'show latest', or 'stats'). " +
      "Agent-callable equivalent of the '/rvv-miniputt logs' slash command.",
    promptSnippet: "Read RVV Miniputt pipeline run logs and stats",
    parameters: Type.Object({
      args: Type.Optional(Type.String({
        description: "Same arguments as '/rvv-miniputt logs', e.g. 'show latest', 'stats', 'list --count 5'",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const result = buildLogsResult(params.args ?? "", ctx.cwd);
      return { content: [{ type: "text", text: result.text }], details: result };
    },
  });

  pi.registerTool({
    name: "rvv_miniputt_calendars",
    label: "RVV Miniputt: Calendars",
    description:
      "Generate calendar reports from cache, or force a full re-scrape with '--refresh'. " +
      "Agent-callable equivalent of the '/rvv-miniputt calendars' slash command.",
    promptSnippet: "Generate RVV Miniputt calendar reports",
    parameters: Type.Object({
      args: Type.Optional(Type.String({
        description: "Same flags as '/rvv-miniputt calendars', e.g. '--refresh'",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const result = await runCalendars(params.args ?? "", ctx);
      return { content: [{ type: "text", text: result.text }], details: result };
    },
  });
}
