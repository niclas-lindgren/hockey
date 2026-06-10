/**
 * rvv-miniputt pi extension
 *
 * Registers commands in the pi session:
 *
 *   /rvv-miniputt guide   — interaktiv veiviser som stiller sporsmal og guider deg
 *   /rvv-miniputt run     — run the four-stage agentic season-planning pipeline
 *   /rvv-miniputt status  — show the current stage checkpoint status
 *   /rvv-miniputt logs    — inspect pipeline run history for self-improvement
 *   /rvv-miniputt calendars — generate calendar reports
 *
 * The pipeline stages are invoked as Python modules via execFile so that the
 * Python environment (venv, Playwright) is fully available:
 *
 *   python3 -m tournament_scheduler.pipeline.stage1_config
 *   python3 -m tournament_scheduler.pipeline.stage2_scraping
 *   python3 -m tournament_scheduler.pipeline.stage3_planning
 *   python3 -m tournament_scheduler.pipeline.stage4_export
 *
 * Implementation is split across dedicated modules under .pi/lib/.
 *
 * Quick start:
 *   Just type /rvv-miniputt guide and follow the prompts.
 */

import type { ExtensionAPI, ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { LOG_LEVELS } from "../lib/types";
import { parseStatusArgs, parseLogsArgs } from "../lib/parsers";
import { buildStatusText } from "../lib/pipeline-helpers";
import { buildLogsListText, buildLogsShowText, buildLogsStatsText } from "../lib/log-inspector";
import { runPipeline } from "../lib/pipeline-runner";
import { interactiveGuide } from "../lib/interactive-guide";

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
      await runPipeline(args, ctx);
    },
  });

  // -------------------------------------------------------------------------
  // /rvv-miniputt guide — interaktiv veiviser
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt guide", {
    description:
      "\u00c5pne en interaktiv veiviser som stiller sp\u00f8rsm\u00e5l om hva du vil gj\u00f8re " +
      "og guider deg gjennom pipeline-prosessen trinn for trinn.\n" +
      "Ingen parametere n\u00f8dvendig — veiviseren spor deg om alt som trengs.\n" +
      "Anbefalt for nye brukere og \u00e9nskj\u00f8rs-kj\u00f8ringer.",
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
      const text = buildStatusText(workDir);
      ctx.ui.notify(text, "info");
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
      const params = parseLogsArgs(args);
      const workDir = resolve(ctx.cwd, params.work_dir ?? ".pipeline");
      const count = params.count ?? 10;

      let text: string;
      switch (params.subcommand) {
        case "show":
          if (!params.run_id) {
            ctx.ui.notify("Bruk: /rvv-miniputt logs show <run-id>", "error");
            return;
          }
          text = buildLogsShowText(workDir, params.run_id);
          ctx.ui.notify(text, "info");
          return;
        case "stats":
          text = buildLogsStatsText(workDir);
          ctx.ui.notify(text, "info");
          return;
        case "list":
        default:
          text = buildLogsListText(workDir, count);
          ctx.ui.notify(text, "info");
          return;
      }
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
      const tokens = args.trim().split(/\s+/);
      let refresh = false;
      let workDir = ".pipeline";
      for (let i = 0; i < tokens.length; i++) {
        if (tokens[i] === "--refresh") refresh = true;
        else if (tokens[i] === "--work-dir" && i + 1 < tokens.length) workDir = tokens[++i];
      }

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

      if (refresh) {
        ctx.ui.notify("🔄 Tvinger full re-skraping av kalendere (via rvv-miniputt CLI)...\n", "info");
      } else {
        ctx.ui.notify("Genererer kalendere fra cache...", "info");
      }

      try {
        const { execFile } = await import("node:child_process");
        const { promisify } = await import("node:util");
        const execFileAsync = promisify(execFile);
        const { copyFileSync } = await import("node:fs");

        const { stdout, stderr } = await execFileAsync(exe, cliArgs, {
          cwd: ctx.cwd,
          timeout: refresh ? 300_000 : 60_000,
        });

        if (stdout.trim()) {
          ctx.ui.notify(stdout.trim(), "info");
        }

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

        if (stderr.trim()) {
          ctx.ui.notify(stderr.trim(), "warning");
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        ctx.ui.notify(`Feil: ${msg}`, "error");
      }
    },
  });
}
