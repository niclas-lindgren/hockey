// ---------------------------------------------------------------------------
// Pipeline runner — executes all four stages
// ---------------------------------------------------------------------------

import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseRunArgs } from "./parsers";
import { PipelineLogger } from "./pipeline-logger";
import {
  STAGE_ORDER,
  STAGE_FILES,
  runStage,
  readCheckpoint,
  buildStatusText,
  resolveResumeStage,
  estimateDataVolume,
} from "./pipeline-helpers";

export interface PipelineRunResult {
  status: "success" | "failure";
  text: string;
}

export async function runPipeline(rawArgs: unknown, ctx: ExtensionContext): Promise<PipelineRunResult> {
  const params = parseRunArgs(rawArgs);
  const cwdPath = ctx.cwd;
  const inputPath  = resolve(cwdPath, params.input     ?? "input.json");
  const workDir    = resolve(cwdPath, params.work_dir  ?? ".pipeline");
  const exportDir  = resolve(cwdPath, params.export_dir ?? "export");
  const resumeFrom = params.resume_from ? resolveResumeStage(params.resume_from) : 1;
  const verbose    = params.log_level === "verbose";

  mkdirSync(workDir, { recursive: true });

  const logger = new PipelineLogger(workDir);

  // Determine which stages to run
  const stagesToRun = STAGE_ORDER.slice(resumeFrom - 1);
  logger.logRunMeta(
    {
      input: params.input,
      work_dir: params.work_dir,
      resume_from: params.resume_from,
      export_dir: params.export_dir,
      log_level: params.log_level,
    },
    resumeFrom,
    stagesToRun,
  );

  const lines: string[] = [];
  let overallStatus: "success" | "failure" = "success";

  lines.push(`=== RVV Miniputt Pipeline ===`);
  lines.push(`Kjøring: ${logger.getRunId()}`);
  lines.push(`Logg: ${logger.getLogPath()}`);
  lines.push(`Arbeidskatalog: ${workDir}`);
  lines.push(`Input: ${inputPath}`);
  if (resumeFrom > 1) lines.push(`Gjenopptar fra: Trinn ${resumeFrom}`);
  lines.push("");

  const baseArgs = ["--work-dir", workDir];

  // -------------------------------------------------------------------
  // Stage 1 — Config
  // -------------------------------------------------------------------
  if (resumeFrom <= 1) {
    lines.push("Trinn 1: Laster og validerer konfigurasjon...");
    logger.stageStart("config");
    try {
      const { stdout, stderr } = await runStage(
        cwdPath,
        "tournament_scheduler.pipeline.stage1_config",
        [...baseArgs, "--input", inputPath],
      );
      if (verbose) logger.logStageOutput("config", stdout, stderr);
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 1: OK\n");

      // Log data volume from checkpoint
      const ckpt = readCheckpoint(workDir, "stage1_config.json");
      logger.stageEnd("config", "ok", undefined, estimateDataVolume(ckpt));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 1 FEILET:\n${msg}`);
      logger.stageEnd("config", "failed", msg);
      logger.finalize("failure");
      return { status: "failure", text: lines.join("\n") };
    }
  } else {
    lines.push("Trinn 1: Hoppet over (gjenopptatt)\n");
    logger.stageStart("config");
    logger.stageEnd("config", "skipped");
  }

  // -------------------------------------------------------------------
  // Stage 2 — Scraping + ScraperAgent for blocked sources
  // -------------------------------------------------------------------
  if (resumeFrom <= 2) {
    lines.push("Trinn 2: Skraper kalenderkilder (deterministisk)...");
    logger.stageStart("scraping");
    let stage2ok = true;
    let stage2error = "";
    try {
      const { stdout, stderr } = await runStage(
        cwdPath,
        "tournament_scheduler.pipeline.stage2_scraping",
        [...baseArgs, "--non-strict"],
      );
      if (verbose) logger.logStageOutput("scraping", stdout, stderr);
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
    } catch (err: unknown) {
      stage2ok = false;
      stage2error = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 2 deterministisk delvis: ${stage2error}\n`);
    }

    const ckpt = readCheckpoint(workDir, "stage2_scraping.json");
    let blocked: string[] = [];
    if (ckpt?.data) {
      const data = ckpt.data as Record<string, unknown>;
      blocked = (data.blocked as string[]) ?? [];
      const sources = (data.sources as Array<Record<string, unknown>>) ?? [];
      for (const s of sources) {
        lines.push(`  ${s.name}: ${s.event_count} events`);
      }
    }

    if (blocked.length > 0) {
      lines.push(`\nTrinn 2 utvidet: Skraper ${blocked.length} blokkerte kilder med Pi...`);
      try {
        const { ScraperAgent } = await import("./scraper-agent");
        const agent = new ScraperAgent(ctx);
        await agent.start();

        // Fetch strategies from Python for blocked sources
        async function fetchStrategy(clubName: string): Promise<Record<string, unknown> | null> {
          try {
            const { execFile } = await import("node:child_process");
            const { promisify } = await import("node:util");
            const efa = promisify(execFile);
            const python = resolve(cwdPath, "venv", "bin", "python3");
            const exe = existsSync(python) ? python : "python3";
            const { stdout } = await efa(exe, [
              "-m", "tournament_scheduler.pipeline.scraper_strategies",
              "--name", clubName,
            ], { cwd: cwdPath, timeout: 10_000 });
            return JSON.parse(stdout) as Record<string, unknown>;
          } catch {
            return null;
          }
        }

        for (const name of blocked) {
          const strat = await fetchStrategy(name);
          if (!strat || !strat.url) {
            lines.push(`  ${name}: ingen strategi — hopper over`);
            continue;
          }

          // Credential pre-flight: prompt for missing env vars
          const credEnvVars = (strat.credential_env_vars as string[]) ?? [];
          for (const envVar of credEnvVars) {
            if (!process.env[envVar]) {
              const value = await ctx.ui.input(
                `Innlogging kreves for ${name}. Angi ${envVar}:`,
                "",
              );
              if (value) {
                process.env[envVar] = value;
                lines.push(`  ${name}: ${envVar} satt (${value.length} tegn)`);
              } else {
                lines.push(`  ${name}: ${envVar} ikke angitt — scraping kan feile`);
              }
            }
          }

          lines.push(`  ${name}: skraper med ScraperAgent...`);
          const initialNav = (strat.initial_navigation as Array<Record<string, unknown>>) ?? [];
          const events = await agent.scrape(strat.url as string, {
            strategy: (strat.engine === "styled_calendar" ? "styledcalendar" : "auto") as any,
            iframe: (strat.has_iframe as boolean) ?? false,
            maxIterations: 25,
            initialNavigation: initialNav.length > 0 ? initialNav as any : undefined,
          });
          lines.push(`  ${name}: ${events.length} events funnet\n`);

          // Update checkpoint data by writing to cache
          if (events.length > 0) {
            const { appendFileSync, writeFileSync } = await import("node:fs");
            const cachePath = resolve(workDir, "cache", "scraped_data.json");
            let cacheData: Record<string, any> = {};
            try {
              cacheData = JSON.parse(readFileSync(cachePath, "utf-8"));
            } catch {}
            if (!cacheData.sources) cacheData.sources = {};
            cacheData.sources[name] = {
              name,
              url: strat.url,
              scrape_timestamp: new Date().toISOString(),
              event_count: events.length,
              blocked: false,
              events,
            };
            cacheData.total_events = Object.values(cacheData.sources as Record<string, any>).reduce((s: number, src: any) => s + (src.event_count || 0), 0);
            cacheData.source_count = Object.keys(cacheData.sources as Record<string, any>).length;
            writeFileSync(cachePath, JSON.stringify(cacheData, null, 2));
          }
        }

        await agent.close();
        lines.push("Trinn 2 utvidet: OK\n");

        // Regenerate viewer
        try {
          const { execFile } = await import("node:child_process");
          const { promisify } = await import("node:util");
          const execFileAsync = promisify(execFile);
          const python = resolve(cwdPath, "venv", "bin", "python3");
          const exe = existsSync(python) ? python : "python3";
          await execFileAsync(exe, ["-m", "tournament_scheduler.pipeline.calendar_viewer", "--work-dir", workDir, "--export-dir", exportDir], { cwd: cwdPath });
        } catch {}
      } catch (agentErr: unknown) {
        const msg = agentErr instanceof Error ? agentErr.message : String(agentErr);
        lines.push(`ScraperAgent feilet: ${msg}\n`);
      }
    }

    logger.stageEnd("scraping", stage2ok && blocked.length === 0 ? "ok" : "ok", undefined);
  } else {
    lines.push("Trinn 2: Hoppet over (gjenopptatt)\n");
    logger.stageStart("scraping");
    logger.stageEnd("scraping", "skipped");
  }

  // -------------------------------------------------------------------
  // Stage 3 — Planning
  // -------------------------------------------------------------------
  if (resumeFrom <= 3) {
    lines.push("Trinn 3: Bygger sesongplan...");
    logger.stageStart("planning");
    try {
      const { stdout, stderr } = await runStage(
        cwdPath,
        "tournament_scheduler.pipeline.stage3_planning",
        [...baseArgs],
      );
      if (verbose) logger.logStageOutput("planning", stdout, stderr);
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 3: OK\n");

      const ckpt = readCheckpoint(workDir, "stage3_plan.json");
      logger.stageEnd("planning", "ok", undefined, estimateDataVolume(ckpt));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 3 FEILET:\n${msg}`);
      logger.stageEnd("planning", "failed", msg);
      logger.finalize("failure");
      return { status: "failure", text: lines.join("\n") };
    }
  } else {
    lines.push("Trinn 3: Hoppet over (gjenopptatt)\n");
    logger.stageStart("planning");
    logger.stageEnd("planning", "skipped");
  }

  // -------------------------------------------------------------------
  // Stage 4 — Export
  // -------------------------------------------------------------------
  if (resumeFrom <= 4) {
    lines.push("Trinn 4: Eksporterer til Excel, iCal og CSV...");
    logger.stageStart("export");
    try {
      const { stdout, stderr } = await runStage(
        cwdPath,
        "tournament_scheduler.pipeline.stage4_export",
        [...baseArgs, "--export-dir", exportDir],
      );
      if (verbose) logger.logStageOutput("export", stdout, stderr);
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 4: OK\n");

      const ckpt = readCheckpoint(workDir, "stage4_export.json");
      logger.stageEnd("export", "ok", undefined, estimateDataVolume(ckpt));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 4 FEILET:\n${msg}`);
      logger.stageEnd("export", "failed", msg);
      logger.finalize("failure");
      return { status: "failure", text: lines.join("\n") };
    }
  } else {
    lines.push("Trinn 4: Hoppet over (gjenopptatt)\n");
    logger.stageStart("export");
    logger.stageEnd("export", "skipped");
  }

  // Copy season plan HTML next to calendars.html for navbar linking
  try {
    const seasonPlanSrc = resolve(cwdPath, "export", "season_plan.html");
    const seasonPlanDst = resolve(exportDir, "season_plan.html");
    if (existsSync(seasonPlanSrc)) {
      const { copyFileSync } = await import("node:fs");
      copyFileSync(seasonPlanSrc, seasonPlanDst);
      lines.push("Sesongplan kopiert til pipeline-katalog\n");
    }
  } catch {}

  // Regenerate viewer to include navbar with all report links
  try {
    const { execFile } = await import("node:child_process");
    const { promisify } = await import("node:util");
    const execFileAsync = promisify(execFile);
    const python = resolve(cwdPath, "venv", "bin", "python3");
    const exe = existsSync(python) ? python : "python3";
    await execFileAsync(exe, ["-m", "tournament_scheduler.pipeline.calendar_viewer", "--work-dir", workDir], { cwd: cwdPath });
  } catch {}

  // Finalize
  logger.finalize(overallStatus);

  lines.push("=== Pipeline fullfort ===");
  lines.push(buildStatusText(workDir));

  // Add a self-improvement summary
  if (overallStatus === "success") {
    lines.push("");
    lines.push("Genererte filer:");
    lines.push(`  🗓️  Skrapede kalendere:  ${resolve(exportDir, "calendars.html")}`);
    const sp = resolve(exportDir, "season_plan.html");
    if (existsSync(sp)) lines.push(`  📋 Sesongplan:         ${sp}`);
    lines.push(`  📊 Sesongplan (Excel):  ${resolve(cwdPath, "export", "season_plan.xlsx")}`);
    lines.push("");
    lines.push("For å se kjøringshistorikk og trender:");
    lines.push("  /rvv-miniputt logs list   — vis siste kjøringer");
    lines.push("  /rvv-miniputt logs stats  — vis selvforbedringsstatistikk");
    lines.push(`  /rvv-miniputt logs show ${logger.getRunId()}  — vis detaljer for denne kjøringen`);
  }

  return { status: overallStatus, text: lines.join("\n") };
}
