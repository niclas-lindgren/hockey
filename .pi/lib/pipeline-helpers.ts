// ---------------------------------------------------------------------------
// Pipeline helpers — stage running, checkpoint I/O, status display
// ---------------------------------------------------------------------------

import { spawn } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { createInterface } from "node:readline";
import { basename, dirname, join, resolve } from "node:path";

export const STAGE_ORDER = ["config", "scraping", "planning", "export"];

/** Thrown by runStage() when a stage was killed via its AbortSignal rather than failing on its own. */
export class StageCancelledError extends Error {
  readonly cancelled = true as const;
  constructor(message: string) {
    super(message);
    this.name = "StageCancelledError";
  }
}

export const STAGE_FILES: Array<{ label: string; filename: string }> = [
  { label: "Stage 1 (Config)",    filename: "stage1_config.json"   },
  { label: "Stage 2 (Scraping)",  filename: "stage2_scraping.json" },
  { label: "Stage 3 (Planning)",  filename: "stage3_planning.json" },
  { label: "Stage 4 (Export)",    filename: "stage4_export.json"   },
];

/**
 * Run a Python stage module and return stdout/stderr.
 *
 * When `signal` fires (the user cancelled the agent turn), the child process
 * is killed rather than left running detached — previously there was no
 * cancellation wiring at all here, so stopping Pi mid-run never actually
 * stopped the underlying Python subprocess, and the only way to make it
 * stop was to kill Pi's own process (and everything under it) instead.
 */
export async function runStage(
  cwd: string,
  module: string,
  args: string[],
  onOutput?: (event: { stream: "stdout" | "stderr"; line: string }) => void,
  signal?: AbortSignal,
): Promise<{ stdout: string; stderr: string }> {
  if (signal?.aborted) {
    throw new StageCancelledError(`${module} ble ikke startet — kjøringen var allerede avbrutt`);
  }
  const python = resolve(cwd, "venv", "bin", "python3");
  const exe = existsSync(python) ? python : "python3";
  return await new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(exe, ["-m", module, ...args], {
      cwd,
      stdio: ["ignore", "pipe", "pipe"],
    });

    const stdoutLines: string[] = [];
    const stderrLines: string[] = [];
    let lastActivity = Date.now();
    let cancelled = false;
    const heartbeatMs = 15_000;
    const heartbeatTimer = setInterval(() => {
      if (Date.now() - lastActivity < heartbeatMs) return;
      const idleMs = Date.now() - lastActivity;
      onOutput?.({ stream: "stdout", line: `[heartbeat] ${module} kjører fortsatt (${Math.round(idleMs / 1000)}s siden siste output)` });
      lastActivity = Date.now();
    }, heartbeatMs);

    // Give the Python process a chance to exit cleanly on SIGTERM (it may be
    // mid-write to a checkpoint file); force-kill if it ignores that.
    let killTimer: ReturnType<typeof setTimeout> | undefined;
    const onAbort = () => {
      cancelled = true;
      onOutput?.({ stream: "stdout", line: `[heartbeat] ${module}: avbryter (SIGTERM)...` });
      child.kill("SIGTERM");
      killTimer = setTimeout(() => {
        try { child.kill("SIGKILL"); } catch { /* already exited */ }
      }, 5_000);
    };
    signal?.addEventListener("abort", onAbort, { once: true });

    const cleanup = () => {
      clearInterval(heartbeatTimer);
      if (killTimer) clearTimeout(killTimer);
      signal?.removeEventListener("abort", onAbort);
      stdoutInterface.close();
      stderrInterface.close();
    };

    const finish = (code: number | null) => {
      cleanup();
      if (cancelled) {
        rejectPromise(new StageCancelledError(`${module} ble avbrutt av bruker`));
        return;
      }
      if (code === 0) {
        resolvePromise({ stdout: stdoutLines.join("\n").trim(), stderr: stderrLines.join("\n").trim() });
        return;
      }
      const stderrText = stderrLines.join("\n").trim();
      rejectPromise(new Error(stderrText || `Stage module ${module} exited with code ${code ?? "unknown"}`));
    };

    const stdoutInterface = createInterface({ input: child.stdout! });
    const stderrInterface = createInterface({ input: child.stderr! });

    stdoutInterface.on("line", (line) => {
      lastActivity = Date.now();
      stdoutLines.push(line);
      onOutput?.({ stream: "stdout", line });
    });
    stderrInterface.on("line", (line) => {
      lastActivity = Date.now();
      stderrLines.push(line);
      onOutput?.({ stream: "stderr", line });
    });

    child.on("error", (err) => {
      cleanup();
      rejectPromise(err);
    });
    child.on("close", finish);
  });
}

function collectRunLogCandidates(root: string): string[] {
  if (!existsSync(root)) return [];
  const files: string[] = [];
  const stack: string[] = [root];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const fullPath = join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (entry.isFile() && entry.name.startsWith("run-") && entry.name.endsWith(".jsonl")) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

function historicalRunLogPaths(workDir: string): string[] {
  const candidates = [
    ...collectRunLogCandidates(resolve(workDir, "..", "export")),
    ...collectRunLogCandidates(join(workDir, "export")),
  ];

  const deduped = new Map<string, string>();
  for (const path of candidates) {
    const key = basename(path);
    const existing = deduped.get(key);
    if (!existing) {
      deduped.set(key, path);
      continue;
    }
    try {
      if (statSync(path).mtimeMs > statSync(existing).mtimeMs) {
        deduped.set(key, path);
      }
    } catch {
      // ignore stat failures
    }
  }

  return [...deduped.values()].sort((a, b) => {
    try {
      return statSync(b).mtimeMs - statSync(a).mtimeMs;
    } catch {
      return 0;
    }
  });
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

  const logFiles = historicalRunLogPaths(workDir);
  if (logFiles.length > 0) {
    lines.push("");
    lines.push(`Logs: ${dirname(logFiles[0])}`);
    lines.push(`  Siste ${Math.min(3, logFiles.length)} kjøringer:`);
    for (const lf of logFiles.slice(0, 3)) {
      lines.push(`    • ${basename(lf)}`);
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
