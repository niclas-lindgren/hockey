// ---------------------------------------------------------------------------
// Pipeline helpers — stage running, checkpoint I/O, status display
// ---------------------------------------------------------------------------

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const execFileAsync = promisify(execFile);

export const STAGE_ORDER = ["config", "scraping", "planning", "export"];

export const STAGE_FILES: Array<{ label: string; filename: string }> = [
  { label: "Stage 1 (Config)",    filename: "stage1_config.json"   },
  { label: "Stage 2 (Scraping)",  filename: "stage2_scraping.json" },
  { label: "Stage 3 (Planning)",  filename: "stage3_planning.json" },
  { label: "Stage 4 (Export)",    filename: "stage4_export.json"   },
];

/** Run a Python stage module and return stdout/stderr. */
export async function runStage(
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
export function readCheckpoint(workDir: string, filename: string): Record<string, unknown> | null {
  const candidates = filename === "stage3_planning.json"
    ? [filename, "stage3_plan.json"]
    : [filename];
  for (const candidate of candidates) {
    const p = join(workDir, candidate);
    if (!existsSync(p)) continue;
    try {
      return JSON.parse(readFileSync(p, "utf-8")) as Record<string, unknown>;
    } catch {
      return null;
    }
  }
  return null;
}

export function buildStatusText(workDir: string): string {
  const lines: string[] = [`Pipeline work-dir: ${workDir}`, ""];
  for (const { label, filename } of STAGE_FILES) {
    const ckpt = readCheckpoint(workDir, filename);
    if (!ckpt) {
      lines.push(`  ${label}: pending (no checkpoint)`);
    } else {
      const status = (ckpt.status as string) ?? "unknown";
      const updated = (ckpt.updated_at as string) ?? "";
      const stale = ckpt.stale ? `  (stale from ${(ckpt.stale_from as string) ?? "?"})` : "";
      lines.push(`  ${label}: ${status}${stale}${updated ? `  (${updated})` : ""}`);
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

  // Append log directory info
  const logDir = join(workDir, "logs");
  if (existsSync(logDir)) {
    const logFiles = readdirSync(logDir).filter((f) => f.endsWith(".jsonl")).sort().reverse();
    if (logFiles.length > 0) {
      lines.push("");
      lines.push(`Logs: ${logDir}`);
      lines.push(`  Siste ${Math.min(3, logFiles.length)} kjøringer:`);
      for (const lf of logFiles.slice(0, 3)) {
        lines.push(`    • ${lf}`);
      }
    }
  }

  return lines.join("\n");
}

/** Determine which stage to start from given --resume-from value. */
export function resolveResumeStage(resumeFrom: string): number {
  const map: Record<string, number> = {
    "1": 1, config: 1, stage1: 1,
    "2": 2, scraping: 2, stage2: 2,
    "3": 3, planning: 3, plan: 3, stage3: 3,
    "4": 4, export: 4, stage4: 4,
  };
  return map[resumeFrom.toLowerCase()] ?? 1;
}

/** Estimate data volume from a checkpoint. */
export function estimateDataVolume(ckpt: Record<string, unknown> | null): Record<string, number> | undefined {
  if (!ckpt?.data) return undefined;
  const data = ckpt.data as Record<string, unknown>;
  const vol: Record<string, number> = {};

  if (Array.isArray(data.teams)) vol.teams = data.teams.length;
  if (Array.isArray(data.sources)) vol.sources = data.sources.length;
  if (Array.isArray(data.age_groups)) vol.age_groups = data.age_groups.length;
  if (Array.isArray(data.events)) vol.events = data.events.length;
  // Stage 1 computed fields (post-consolidation, stage1_config stores only computed data)
  if (data.round_length_minutes && typeof data.round_length_minutes === "object") {
    vol.round_length_minutes = Object.keys(data.round_length_minutes as Record<string, unknown>).length;
  }
  // Stage 3 stores plan under a nested "plan" key
  const plan = data.plan as Record<string, unknown> | undefined;
  if (plan) {
    const t = plan.tournaments;
    if (Array.isArray(t)) vol.tournaments = t.length;
    if (typeof plan.total_games === "number") vol.total_games = plan.total_games;
  }
  if (Array.isArray(data.tournaments)) vol.tournaments = data.tournaments.length;
  if (typeof data.total_games === "number") vol.total_games = data.total_games;
  if (data.output_files && typeof data.output_files === "object") {
    vol.output_files = Object.keys(data.output_files as Record<string, unknown>).length;
  }

  return Object.keys(vol).length > 0 ? vol : undefined;
}
