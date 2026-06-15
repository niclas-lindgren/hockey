// ---------------------------------------------------------------------------
// Interactive guide — wizard that asks questions and dispatches
// ---------------------------------------------------------------------------

import type { ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { resolve } from "node:path";
import { existsSync } from "node:fs";
import { cwd } from "node:process";
import { buildStatusText } from "./pipeline-helpers";
import { buildLogsListText, buildLogsShowText, buildLogsStatsText } from "./log-inspector";
import { runPipeline } from "./pipeline-runner";

export async function interactiveGuide(ctx: ExtensionCommandContext): Promise<void> {
  // ----- Step 1: Main menu -----
  const mainChoice = await ctx.ui.select(
    "Hva vil du gjore med RVV Miniputt-pipelinen?",
    [
      "1. Kjore sesongplan-pipeline (ny kjoring)",
      "2. Se status for pipeline-trinn",
      "3. Se pipeline-logging og historikk",
      "4. Hjelp — forklaring av pipeline og kommandoer",
      "(avbryt)",
    ],
  );
  if (!mainChoice || mainChoice.startsWith("(avbryt")) {
    ctx.ui.notify("Avbrutt.", "info");
    return;
  }

  if (mainChoice.startsWith("2.")) {
    // Show status
    const wd = await ctx.ui.input(
      "Arbeidskatalog (standard: .pipeline):",
      ".pipeline",
    );
    const workDir = resolve(ctx.cwd, wd || ".pipeline");
    const text = buildStatusText(workDir);
    ctx.ui.notify(text, "info");
    return;
  }

  if (mainChoice.startsWith("3.")) {
    // Logs sub-menu
    const logChoice = await ctx.ui.select(
      "Hva vil du se?",
      [
        "Vis siste kjoringer (liste)",
        "Vis detaljer for nyeste kjoring",
        "Vis aggregert statistikk",
      ],
    );
    if (!logChoice) {
      ctx.ui.notify("Avbrutt.", "info");
      return;
    }
    const workDir = resolve(ctx.cwd, ".pipeline");
    if (logChoice.startsWith("Vis siste")) {
      ctx.ui.notify(buildLogsListText(workDir, 10), "info");
    } else if (logChoice.startsWith("Vis detaljer")) {
      ctx.ui.notify(buildLogsShowText(workDir, "latest"), "info");
    } else {
      ctx.ui.notify(buildLogsStatsText(workDir), "info");
    }
    return;
  }

  if (mainChoice.startsWith("4.")) {
    // Help
    const help = [
      "=== RVV Miniputt Pipeline — Hjelp ===",
      "",
      "Pipelinen bestar av fire trinn:",
      "  1. Konfigurasjon — leser input.xlsx og validerer",
      "  2. Skraping — henter kalenderdata fra alle 9 RVV-klubber",
      "     (Kongsberg, Skien, Ringerike, Jutul, Jar, Holmen,",
      "      Frisk Asker, Tonsberg, Sandefjord Penguins)",
      "  3. Planlegging — genererer sesongplan med turneringer",
      "  4. Eksport — Excel, iCal, CSV",
      "",
      "Kommandoer:",
      "  /rvv-miniputt            — denne veiviseren",
      "  /rvv-miniputt guide      — samme som over",
      "  /rvv-miniputt run        — kjor pipelinen med flagg",
      "  /rvv-miniputt status     — se hvilke trinn som er klare",
      "  /rvv-miniputt logs       — vis logging og statistikk",
      "",
      "Vanlige flagg for /rvv-miniputt run:",
      "  --input <fil>            — konfigurasjonsfil (standard: input.xlsx)",
      "  --resume-from <trinn>    — gjenoppta fra trinn 1-4",
      "",
      "Nokkel-filer:",
      "  input.xlsx               — klubb-/lag-konfigurasjon",
      "  .pipeline/               — mellomlagring (checkpoints)",
      "  .pipeline/logs/          — kjoringslogg",
      "  export/                  — ferdige filer (Excel, iCal, CSV)",
      "",
      "For mer informasjon, se PROJECT.md og AGENTS.md.",
    ].join("\n");
    ctx.ui.notify(help, "info");
    return;
  }

  // ----- Option 1: Run pipeline -----
  await interactiveRunPipeline(ctx);
}

async function interactiveRunPipeline(ctx: ExtensionCommandContext): Promise<void> {
  // Step 1: Input file
  const inputFile = await ctx.ui.input(
    "Konfigurasjonsfil (standard: input.xlsx):",
    "input.xlsx",
  );
  const finalInput = inputFile || "input.xlsx";

  // Step 2: Check if input.xlsx exists
  const inputPath = resolve(ctx.cwd, finalInput);
  if (!existsSync(inputPath)) {
    ctx.ui.notify(
      `Finner ikke ${finalInput} — opprett en input.xlsx eller angi riktig sti.`,
      "error",
    );
    return;
  }

  // Step 3: Resume from?
  const resumeChoice = await ctx.ui.select(
    "Vil du gjenoppta fra et tidligere trinn, eller kjore alt fra start?",
    [
      "Start fra begynnelsen (trinn 1-4)",
      "Start fra trinn 2 (skraping) — hvis trinn 1 er gjort",
      "Start fra trinn 3 (planlegging) — hvis trinn 1-2 er gjort",
      "Start fra trinn 4 (eksport) — hvis trinn 1-3 er gjort",
    ],
  );
  let resumeFrom = 1;
  if (resumeChoice?.startsWith("Start fra trinn 2")) resumeFrom = 2;
  else if (resumeChoice?.startsWith("Start fra trinn 3")) resumeFrom = 3;
  else if (resumeChoice?.startsWith("Start fra trinn 4")) resumeFrom = 4;

  // Step 4: Export directory
  const customExport = await ctx.ui.confirm(
    "Eksportmappe",
    "Vil du spesifisere en egen eksportmappe? (Standard: ./export)",
  );
  let exportDir: string | undefined;
  if (customExport) {
    exportDir = await ctx.ui.input(
      "Eksportmappe (f.eks. ./sesongplan-2027):",
      "export",
    );
  }

  // Step 5: Work directory
  const customWorkDir = await ctx.ui.confirm(
    "Arbeidskatalog",
    "Vil du bruke en annen arbeidskatalog enn ./.pipeline?",
  );
  let workDir: string | undefined;
  if (customWorkDir) {
    workDir = await ctx.ui.input(
      "Arbeidskatalog (f.eks. ./mitt-prosjekt):",
      ".pipeline",
    );
  }

  // ----- Summary and confirm -----
  const summaryLines: string[] = [
    "=== Oppsummering ===",
    `  Input:        ${finalInput}`,
    `  Starter fra:  Trinn ${resumeFrom}`,
    `  Arbeidskatalog: ${workDir || ".pipeline"}`,
    `  Eksportmappe: ${exportDir || "export"}`,

    "",
    "Vil du starte pipelinen med disse innstillingene?",
  ];

  const confirmed = await ctx.ui.confirm(
    "Bekreft pipeline-kjoring",
    summaryLines.join("\n"),
  );

  if (!confirmed) {
    ctx.ui.notify("Pipeline-kjoring avbrutt.", "info");
    return;
  }

  // ----- Build args string and run -----
  const argsParts: string[] = [`--input ${finalInput}`];
  if (workDir) argsParts.push(`--work-dir ${workDir}`);
  if (exportDir) argsParts.push(`--export-dir ${exportDir}`);
  if (resumeFrom > 1) argsParts.push(`--resume-from ${resumeFrom}`);

  ctx.ui.notify(
    `Starter pipeline: /rvv-miniputt run ${argsParts.join(" ")}`,
    "info",
  );

  const result = await runPipeline(argsParts.join(" "), ctx);
  ctx.ui.notify(result.text, result.status === "success" ? "info" : "error");
}
