/**
 * rvv-miniputt pi extension
 *
 * Registers two commands in the pi session:
 *
 *   /rvv-miniputt run   — run the four-stage agentic season-planning pipeline
 *   /rvv-miniputt status — show the current stage checkpoint status
 *
 * The pipeline stages are invoked as Python modules via execFile so that the
 * Python environment (venv, Playwright) is fully available:
 *
 *   python3 -m tournament_scheduler.pipeline.stage1_config
 *   python3 -m tournament_scheduler.pipeline.stage2_scraping
 *   python3 -m tournament_scheduler.pipeline.stage3_planning
 *   python3 -m tournament_scheduler.pipeline.stage4_export
 *
 * Each stage module supports a --work-dir flag so checkpoints land in a
 * configurable directory (default: <cwd>/.pipeline).
 */

import type { ExtensionAPI, ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const execFileAsync = promisify(execFile);

// ---------------------------------------------------------------------------
// Simple arg parser for command handler (args is a raw string)
// ---------------------------------------------------------------------------

interface RunArgs {
  input?: string;
  work_dir?: string;
  resume_from?: string;
  export_dir?: string;
}

function parseRunArgs(args: string): RunArgs {
  const result: RunArgs = {};
  const tokens = args.trim().split(/\s+/);
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t === "--input" && i + 1 < tokens.length) {
      result.input = tokens[++i];
    } else if (t === "--work-dir" && i + 1 < tokens.length) {
      result.work_dir = tokens[++i];
    } else if (t === "--resume-from" && i + 1 < tokens.length) {
      result.resume_from = tokens[++i];
    } else if (t === "--export-dir" && i + 1 < tokens.length) {
      result.export_dir = tokens[++i];
    }
  }
  return result;
}

interface StatusArgs {
  work_dir?: string;
}

function parseStatusArgs(args: string): StatusArgs {
  const result: StatusArgs = {};
  const tokens = args.trim().split(/\s+/);
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i] === "--work-dir" && i + 1 < tokens.length) {
      result.work_dir = tokens[++i];
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Run a Python stage module and return stdout/stderr. */
async function runStage(
  cwd: string,
  module: string,
  args: string[],
): Promise<{ stdout: string; stderr: string }> {
  const python = resolve(cwd, "venv", "bin", "python3");
  const exe = existsSync(python) ? python : "python3";
  const { stdout, stderr } = await execFileAsync(
    exe,
    ["-m", module, ...args],
    { cwd, maxBuffer: 4 * 1024 * 1024 },
  );
  return { stdout: stdout.trim(), stderr: stderr.trim() };
}

/** Read a JSON checkpoint file; return null if it doesn't exist. */
function readCheckpoint(workDir: string, filename: string): Record<string, unknown> | null {
  const p = join(workDir, filename);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, "utf-8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

const STAGE_FILES: Array<{ label: string; filename: string }> = [
  { label: "Stage 1 (Config)",    filename: "stage1_config.json"   },
  { label: "Stage 2 (Scraping)",  filename: "stage2_scraping.json" },
  { label: "Stage 3 (Planning)",  filename: "stage3_plan.json"     },
  { label: "Stage 4 (Export)",    filename: "stage4_export.json"   },
];

/** Build a human-readable status table. */
function buildStatusText(workDir: string): string {
  const lines: string[] = [`Pipeline work-dir: ${workDir}`, ""];
  for (const { label, filename } of STAGE_FILES) {
    const ckpt = readCheckpoint(workDir, filename);
    if (!ckpt) {
      lines.push(`  ${label}: pending (no checkpoint)`);
    } else {
      const status = (ckpt.status as string) ?? "unknown";
      const updated = (ckpt.updated_at as string) ?? "";
      lines.push(`  ${label}: ${status}${updated ? `  (${updated})` : ""}`);
      // Show per-stage detail
      if (label.startsWith("Stage 2") && ckpt.data) {
        const data = ckpt.data as Record<string, unknown>;
        const blocked = (data.blocked as string[]) ?? [];
        if (blocked.length > 0) {
          lines.push(`    Blokkerte kilder: ${blocked.join(", ")}`);
        }
      }
      if (label.startsWith("Stage 4") && ckpt.data) {
        const data = ckpt.data as Record<string, unknown>;
        const files = data.output_files as Record<string, string> | undefined;
        if (files) {
          for (const [key, path] of Object.entries(files)) {
            lines.push(`    ${key}: ${path}`);
          }
        }
      }
    }
  }
  return lines.join("\n");
}

/** Determine which stage to start from given --resume-from value. */
function resolveResumeStage(resumeFrom: string): number {
  const map: Record<string, number> = {
    "1": 1, config: 1, stage1: 1,
    "2": 2, scraping: 2, stage2: 2,
    "3": 3, planning: 3, plan: 3, stage3: 3,
    "4": 4, export: 4, stage4: 4,
  };
  return map[resumeFrom.toLowerCase()] ?? 1;
}

// ---------------------------------------------------------------------------
// Extension entry point
// ---------------------------------------------------------------------------

export default function rvvMiniputt(pi: ExtensionAPI): void {
  // -------------------------------------------------------------------------
  // /rvv-miniputt run
  // -------------------------------------------------------------------------
  pi.registerCommand("rvv-miniputt run", {
    description:
      "Kjør den firetrinns sesongplanleggingspipelinen for RVV-hockeyklubber. " +
      "Hvert trinn har en LLM-kvalitetskontroll. Støtter gjenopptak fra et bestemt trinn.\n" +
      "Valgfrie flagg: --input <sti> --work-dir <sti> --resume-from <trinn> --export-dir <sti>",
    getArgumentCompletions: (prefix) => {
      const words = ["--input", "--work-dir", "--resume-from", "--export-dir"];
      const filtered = words.filter((w) => w.startsWith(prefix));
      return filtered.length ? filtered.map((value) => ({ value, label: value })) : null;
    },
    handler: async (args, ctx) => {
      await runPipeline(args, ctx);
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
}

// ---------------------------------------------------------------------------
// Pipeline runner (extracted so the handler stays lean)
// ---------------------------------------------------------------------------

async function runPipeline(rawArgs: string, ctx: ExtensionCommandContext): Promise<void> {
  const params = parseRunArgs(rawArgs);
  const cwd = ctx.cwd;
  const inputPath  = resolve(cwd, params.input     ?? "input.json");
  const workDir    = resolve(cwd, params.work_dir  ?? ".pipeline");
  const exportDir  = resolve(cwd, params.export_dir ?? "export");
  const resumeFrom = params.resume_from ? resolveResumeStage(params.resume_from) : 1;

  mkdirSync(workDir, { recursive: true });

  const lines: string[] = [];

  lines.push(`=== RVV Miniputt Pipeline ===`);
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
    try {
      const { stdout, stderr } = await runStage(
        cwd,
        "tournament_scheduler.pipeline.stage1_config",
        [...baseArgs, "--input", inputPath],
      );
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 1: OK\n");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 1 FEILET:\n${msg}`);
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
  } else {
    lines.push("Trinn 1: Hoppet over (gjenopptatt)\n");
  }

  // -------------------------------------------------------------------
  // Stage 2 — Scraping
  // -------------------------------------------------------------------
  if (resumeFrom <= 2) {
    lines.push("Trinn 2: Skraper kalenderkilder med LLM-kvalitetskontroll...");
    try {
      const { stdout, stderr } = await runStage(
        cwd,
        "tournament_scheduler.pipeline.stage2_scraping",
        [...baseArgs],
      );
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 2: OK\n");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 2 FEILET:\n${msg}`);
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
  } else {
    lines.push("Trinn 2: Hoppet over (gjenopptatt)\n");
  }

  // -------------------------------------------------------------------
  // Stage 3 — Planning
  // -------------------------------------------------------------------
  if (resumeFrom <= 3) {
    lines.push("Trinn 3: Bygger sesongplan og evaluerer med LLM...");
    try {
      const { stdout, stderr } = await runStage(
        cwd,
        "tournament_scheduler.pipeline.stage3_planning",
        [...baseArgs],
      );
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 3: OK\n");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 3 FEILET:\n${msg}`);
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
  } else {
    lines.push("Trinn 3: Hoppet over (gjenopptatt)\n");
  }

  // -------------------------------------------------------------------
  // Stage 4 — Export
  // -------------------------------------------------------------------
  if (resumeFrom <= 4) {
    lines.push("Trinn 4: Eksporterer til Excel, iCal og CSV...");
    try {
      const { stdout, stderr } = await runStage(
        cwd,
        "tournament_scheduler.pipeline.stage4_export",
        [...baseArgs, "--export-dir", exportDir],
      );
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 4: OK\n");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 4 FEILET:\n${msg}`);
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
  } else {
    lines.push("Trinn 4: Hoppet over (gjenopptatt)\n");
  }

  lines.push("=== Pipeline fullfort ===");
  lines.push(buildStatusText(workDir));

  ctx.ui.notify(lines.join("\n"), "info");
}
