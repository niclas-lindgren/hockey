/**
 * rvv-miniputt pi extension
 *
 * Registers commands in the pi session:
 *
 *   /rvv-miniputt guide   — interaktiv veiviser som stiller sporsmal og guider deg
 *   /rvv-miniputt run     — run the four-stage agentic season-planning pipeline
 *   /rvv-miniputt status  — show the current stage checkpoint status
 *   /rvv-miniputt logs    — inspect pipeline run history for self-improvement
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
 *
 * Logging for self-improvement
 * -----------------------------
 * Every pipeline run writes structured JSONL entries to
 *   .pipeline/logs/run-YYYY-MM-DDTHH-mm-ss.jsonl
 *
 * Entry types:
 *   run_meta    — run ID, args, git commit, start/end time, duration, exit status
 *   stage_meta  — per-stage: name, status, duration, error, data volume hints
 *   stage_log   — full captured stdout/stderr (only when --log-level=verbose)
 *   self_improve — cross-run aggregate stats appended at end of run
 *
 * Use /rvv-miniputt logs to inspect history and trends.
 *
 * Quick start:
 *   Just type /rvv-miniputt guide and follow the prompts.
 */

import type { ExtensionAPI, ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
  appendFileSync,
} from "node:fs";
import { join, resolve, basename } from "node:path";
import { cwd } from "node:process";

const execFileAsync = promisify(execFile);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunArgs {
  input?: string;
  work_dir?: string;
  resume_from?: string;
  export_dir?: string;
  log_level?: string;
}

interface LogEntry {
  type: "run_meta" | "stage_meta" | "stage_log" | "self_improve" | "llm_interaction" | "tournament_update";
  run_id: string;
  timestamp: string;
  [key: string]: unknown;
}

interface RunMeta extends LogEntry {
  type: "run_meta";
  args: Record<string, string | undefined>;
  git_commit: string;
  git_dirty: boolean;
  start_time: string;
  end_time: string;
  duration_ms: number;
  exit_status: "success" | "failure" | "cancelled";
  stages: string[];
  resume_from: number;
}

interface StageMeta extends LogEntry {
  type: "stage_meta";
  stage_name: string;
  stage_index: number;
  status: "ok" | "skipped" | "failed";
  start_time: string;
  end_time: string;
  duration_ms: number;
  error?: string;
  data_volume?: Record<string, number>;
}

interface SelfImproveEntry extends LogEntry {
  type: "self_improve";
  run_count: number;
  avg_duration_ms: number;
  stage_stats: Record<string, {
    run_count: number;
    avg_duration_ms: number;
    failure_count: number;
    failure_rate: number;
  }>;
  total_failure_count: number;
  total_success_count: number;
  failure_rate_pct: number;
  duration_trend_ms: Array<{ run_id: string; date: string; duration_ms: number }>;
}

const LOG_LEVELS = ["info", "verbose"] as const;

// ---------------------------------------------------------------------------
// Arg parsers
// ---------------------------------------------------------------------------

function parseRunArgs(args: string): RunArgs {
  const result: RunArgs = {};
  const tokens = args.trim().split(/\s+/);
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t === "--input" && i + 1 < tokens.length) result.input = tokens[++i];
    else if (t === "--work-dir" && i + 1 < tokens.length) result.work_dir = tokens[++i];
    else if (t === "--resume-from" && i + 1 < tokens.length) result.resume_from = tokens[++i];
    else if (t === "--export-dir" && i + 1 < tokens.length) result.export_dir = tokens[++i];
    else if (t === "--log-level" && i + 1 < tokens.length) result.log_level = tokens[++i];
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
    if (tokens[i] === "--work-dir" && i + 1 < tokens.length) result.work_dir = tokens[++i];
  }
  return result;
}

interface LogsArgs {
  subcommand: "list" | "show" | "stats";
  count?: number;
  run_id?: string;
  work_dir?: string;
}

function parseLogsArgs(args: string): LogsArgs {
  const result: LogsArgs = { subcommand: "list" };
  const tokens = args.trim().split(/\s+/);
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t === "list") result.subcommand = "list";
    else if (t === "show" && i + 1 < tokens.length) {
      result.subcommand = "show";
      result.run_id = tokens[++i];
      if (result.run_id === "latest") {
        // Resolve to the most recent run log file
        const logDir = join(cwd(), ".pipeline", "logs");
        if (existsSync(logDir)) {
          const files = readdirSync(logDir)
            .filter((f) => f.startsWith("run-") && f.endsWith(".jsonl"))
            .sort()
            .reverse();
          if (files.length > 0) {
            result.run_id = files[0].replace(/\.jsonl$/, "");
          }
        }
      }
    } else if (t === "stats") result.subcommand = "stats";
    else if (t === "--count" && i + 1 < tokens.length) result.count = parseInt(tokens[++i], 10);
    else if (t === "--work-dir" && i + 1 < tokens.length) result.work_dir = tokens[++i];
  }
  return result;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isVerbose(rawArgs: string): boolean {
  return parseRunArgs(rawArgs).log_level === "verbose";
}

function nowISO(): string {
  return new Date().toISOString();
}

function nowCompact(): string {
  const d = new Date();
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}-${pad(d.getMinutes())}-${pad(d.getSeconds())}`;
}

function runId(): string {
  return `run-${nowCompact()}`;
}

function gitCommit(cwd: string): { hash: string; dirty: boolean } {
  try {
    const hash = readFileSync(join(cwd, ".git", "HEAD"), "utf-8").trim();
    // If it's a ref, resolve it
    if (hash.startsWith("ref: ")) {
      const refPath = join(cwd, ".git", hash.slice(5));
      const resolved = existsSync(refPath)
        ? readFileSync(refPath, "utf-8").trim()
        : hash;
      return { hash: resolved, dirty: true }; // can't easily check dirty without git cmd
    }
    return { hash, dirty: true };
  } catch {
    return { hash: "unknown", dirty: true };
  }
}

// ---------------------------------------------------------------------------
// Logging system
// ---------------------------------------------------------------------------

class PipelineLogger {
  private logDir: string;
  private logPath: string;
  private runId: string;
  private startTime: number;
  private stageStarts: Map<string, number> = new Map();

  constructor(workDir: string) {
    this.logDir = join(workDir, "logs");
    mkdirSync(this.logDir, { recursive: true });
    this.runId = runId();
    this.logPath = join(this.logDir, `${this.runId}.jsonl`);
    this.startTime = Date.now();
  }

  getRunId(): string { return this.runId; }
  getLogPath(): string { return this.logPath; }

  private write(entry: LogEntry): void {
    appendFileSync(this.logPath, JSON.stringify(entry) + "\n", "utf-8");
  }

  logRunMeta(args: Record<string, string | undefined>, resumeFrom: number, stages: string[]): void {
    const git = gitCommit(cwd());
    const entry: RunMeta = {
      type: "run_meta",
      run_id: this.runId,
      timestamp: nowISO(),
      args: { ...args },
      git_commit: git.hash,
      git_dirty: git.dirty,
      start_time: nowISO(),
      end_time: "",
      duration_ms: 0,
      exit_status: "cancelled",
      stages,
      resume_from: resumeFrom,
    };
    this.write(entry);
  }

  stageStart(stageName: string): void {
    this.stageStarts.set(stageName, Date.now());
    this.write({
      type: "stage_meta",
      run_id: this.runId,
      timestamp: nowISO(),
      stage_name: stageName,
      stage_index: STAGE_ORDER.indexOf(stageName) + 1,
      status: "ok",
      start_time: nowISO(),
      end_time: "",
      duration_ms: 0,
    });
  }

  stageEnd(
    stageName: string,
    status: "ok" | "skipped" | "failed",
    error?: string,
    dataVolume?: Record<string, number>,
  ): void {
    const start = this.stageStarts.get(stageName) ?? Date.now();
    const entry: StageMeta = {
      type: "stage_meta",
      run_id: this.runId,
      timestamp: nowISO(),
      stage_name: stageName,
      stage_index: STAGE_ORDER.indexOf(stageName) + 1,
      status,
      start_time: new Date(start).toISOString(),
      end_time: nowISO(),
      duration_ms: Date.now() - start,
    };
    if (error) entry.error = error;
    if (dataVolume) entry.data_volume = dataVolume;
    this.write(entry);
  }

  logStageOutput(stageName: string, stdout: string, stderr: string): void {
    if (!stdout && !stderr) return;
    this.write({
      type: "stage_log",
      run_id: this.runId,
      timestamp: nowISO(),
      stage_name: stageName,
      stdout: stdout.slice(0, 10000),
      stderr: stderr.slice(0, 5000),
    });
  }

  logLLMInteraction(stageName: string, details: Record<string, unknown>): void {
    this.write({
      type: "llm_interaction",
      run_id: this.runId,
      timestamp: nowISO(),
      stage_name: stageName,
      ...details,
    });
  }

  finalize(exitStatus: "success" | "failure" | "cancelled"): void {
    const duration = Date.now() - this.startTime;

    // Update run_meta with final state (append a final entry with end_time)
    this.write({
      type: "run_meta",
      run_id: this.runId,
      timestamp: nowISO(),
      end_time: nowISO(),
      duration_ms: duration,
      exit_status: exitStatus,
    } as Partial<RunMeta>);

    // Compute and append self-improvement stats
    this.appendSelfImproveStats();
  }

  private appendSelfImproveStats(): void {
    try {
      const files = readdirSync(this.logDir)
        .filter((f) => f.startsWith("run-") && f.endsWith(".jsonl"))
        .sort()
        .reverse();

      const allRuns: RunMeta[] = [];
      const stageRuns: Record<string, StageMeta[]> = {};

      for (const file of files) {
        const lines = readFileSync(join(this.logDir, file), "utf-8")
          .trim()
          .split("\n")
          .filter(Boolean);
        let runMeta: RunMeta | null = null;
        for (const line of lines) {
          try {
            const entry = JSON.parse(line) as LogEntry;
            if (entry.type === "run_meta" && entry.end_time) {
              runMeta = entry as RunMeta;
            } else if (entry.type === "stage_meta") {
              const sm = entry as StageMeta;
              if (sm.duration_ms > 0) {
                (stageRuns[sm.stage_name] ??= []).push(sm);
              }
            }
          } catch { /* skip malformed lines */ }
        }
        if (runMeta && runMeta.duration_ms > 0) {
          allRuns.push(runMeta);
        }
      }

      const totalCount = allRuns.length;
      if (totalCount === 0) return;

      const avgDuration = Math.round(
        allRuns.reduce((s, r) => s + r.duration_ms, 0) / totalCount,
      );
      const successCount = allRuns.filter((r) => r.exit_status === "success").length;
      const failCount = allRuns.filter((r) => r.exit_status === "failure").length;

      const stageStats: Record<string, {
        run_count: number;
        avg_duration_ms: number;
        failure_count: number;
        failure_rate: number;
      }> = {};

      for (const [name, metas] of Object.entries(stageRuns)) {
        const stageFailCount = metas.filter((m) => m.status === "failed").length;
        stageStats[name] = {
          run_count: metas.length,
          avg_duration_ms: Math.round(
            metas.reduce((s, m) => s + m.duration_ms, 0) / metas.length,
          ),
          failure_count: stageFailCount,
          failure_rate: metas.length > 0
            ? Math.round((stageFailCount / metas.length) * 100)
            : 0,
        };
      }

      const durationTrend = allRuns.slice(0, 20).map((r) => ({
        run_id: r.run_id,
        date: r.start_time?.slice(0, 10) ?? "unknown",
        duration_ms: r.duration_ms,
      }));

      const si: SelfImproveEntry = {
        type: "self_improve",
        run_id: this.runId,
        timestamp: nowISO(),
        run_count: totalCount,
        avg_duration_ms: avgDuration,
        stage_stats: stageStats,
        total_failure_count: failCount,
        total_success_count: successCount,
        failure_rate_pct: totalCount > 0
          ? Math.round((failCount / totalCount) * 100)
          : 0,
        duration_trend_ms: durationTrend,
      };

      this.write(si);
    } catch {
      // Self-improve stats are best-effort; don't crash if log parsing fails
    }
  }
}

// ---------------------------------------------------------------------------
// Pipeline helpers
// ---------------------------------------------------------------------------

const STAGE_ORDER = ["config", "scraping", "planning", "export"];

const STAGE_FILES: Array<{ label: string; filename: string }> = [
  { label: "Stage 1 (Config)",    filename: "stage1_config.json"   },
  { label: "Stage 2 (Scraping)",  filename: "stage2_scraping.json" },
  { label: "Stage 3 (Planning)",  filename: "stage3_plan.json"     },
  { label: "Stage 4 (Export)",    filename: "stage4_export.json"   },
];

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
function resolveResumeStage(resumeFrom: string): number {
  const map: Record<string, number> = {
    "1": 1, config: 1, stage1: 1,
    "2": 2, scraping: 2, stage2: 2,
    "3": 3, planning: 3, plan: 3, stage3: 3,
    "4": 4, export: 4, stage4: 4,
  };
  return map[resumeFrom.toLowerCase()] ?? 1;
}

/** Estimate data volume from a checkpoint. */
function estimateDataVolume(ckpt: Record<string, unknown> | null): Record<string, number> | undefined {
  if (!ckpt?.data) return undefined;
  const data = ckpt.data as Record<string, unknown>;
  const vol: Record<string, number> = {};

  if (Array.isArray(data.teams)) vol.teams = data.teams.length;
  if (Array.isArray(data.sources)) vol.sources = data.sources.length;
  if (Array.isArray(data.age_groups)) vol.age_groups = data.age_groups.length;
  if (Array.isArray(data.events)) vol.events = data.events.length;
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

// ---------------------------------------------------------------------------
// Log inspection (for /rvv-miniputt logs)
// ---------------------------------------------------------------------------

function loadRunHistory(workDir: string): Array<{ runId: string; logPath: string; meta: RunMeta | null }> {
  const logDir = join(workDir, "logs");
  if (!existsSync(logDir)) return [];

  const runs: Array<{ runId: string; logPath: string; meta: RunMeta | null }> = [];
  for (const file of readdirSync(logDir).filter((f) => f.startsWith("run-") && f.endsWith(".jsonl")).sort().reverse()) {
    const logPath = join(logDir, file);
    const runId = file.replace(/\.jsonl$/, "");
    try {
      const content = readFileSync(logPath, "utf-8");
      let latestMeta: RunMeta | null = null;
      for (const line of content.trim().split("\n").filter(Boolean).reverse()) {
        try {
          const entry = JSON.parse(line) as LogEntry;
          if (entry.type === "run_meta" && entry.run_id === runId && (entry as RunMeta).end_time) {
            latestMeta = entry as RunMeta;
            break;
          }
        } catch { /* skip */ }
      }
      runs.push({ runId, logPath, meta: latestMeta });
    } catch {
      runs.push({ runId, logPath, meta: null });
    }
  }
  return runs;
}

function loadStageEntries(workDir: string, runId: string): StageMeta[] {
  const logPath = join(workDir, "logs", `${runId}.jsonl`);
  if (!existsSync(logPath)) return [];
  const entries: StageMeta[] = [];
  for (const line of readFileSync(logPath, "utf-8").trim().split("\n").filter(Boolean)) {
    try {
      const entry = JSON.parse(line) as LogEntry;
      if (entry.type === "stage_meta") entries.push(entry as StageMeta);
    } catch { /* skip */ }
  }
  return entries;
}

function loadTournamentUpdates(workDir: string, runId: string): LogEntry[] {
  const logPath = join(workDir, "logs", `${runId}.jsonl`);
  if (!existsSync(logPath)) return [];
  const entries: LogEntry[] = [];
  for (const line of readFileSync(logPath, "utf-8").trim().split("\n").filter(Boolean)) {
    try {
      const entry = JSON.parse(line) as LogEntry;
      if (entry.type === "tournament_update") entries.push(entry);
    } catch { /* skip */ }
  }
  return entries;
}

function loadLLMInteractions(workDir: string, runId: string): LogEntry[] {
  const logPath = join(workDir, "logs", `${runId}.jsonl`);
  if (!existsSync(logPath)) return [];
  const entries: LogEntry[] = [];
  for (const line of readFileSync(logPath, "utf-8").trim().split("\n").filter(Boolean)) {
    try {
      const entry = JSON.parse(line) as LogEntry;
      if (entry.type === "llm_interaction") entries.push(entry);
    } catch { /* skip */ }
  }
  return entries;
}

const STAGE_LABELS: Record<string, string> = {
  config: "Konfigurasjon",
  scraping: "Skraping",
  planning: "Planlegging",
  export: "Eksport",
};

function buildLogsListText(workDir: string, count: number): string {
  const runs = loadRunHistory(workDir).slice(0, count);
  if (runs.length === 0) {
    return `Ingen loggførte kjøringer funnet i ${join(workDir, "logs")}/`;
  }

  const lines: string[] = [
    `=== Pipeline kjøringshistorie ===`,
    `Logg-katalog: ${join(workDir, "logs")}/`,
    `Viser ${runs.length} siste kjøringer`,
    "",
    `${"Kjøring".padEnd(30)} ${"Status".padEnd(12)} ${"Varighet".padEnd(12)} ${"Starter".padEnd(22)}`,
    `${"─".repeat(30)} ${"─".repeat(12)} ${"─".repeat(12)} ${"─".repeat(22)}`,
  ];

  for (const { runId, meta } of runs) {
    const status = meta?.exit_status ?? "ukjent";
    const duration = meta?.duration_ms ? formatDuration(meta.duration_ms) : "─";
    const start = meta?.start_time ? meta.start_time.slice(0, 19).replace("T", " ") : "─";
    lines.push(
      `${runId.padEnd(30)} ${status.padEnd(12)} ${duration.padEnd(12)} ${start}`,
    );
  }

  return lines.join("\n");
}

function buildLogsShowText(workDir: string, runId: string): string {
  const logPath = join(workDir, "logs", `${runId}.jsonl`);
  if (!existsSync(logPath)) return `Kjøring ${runId} ikke funnet i ${join(workDir, "logs")}/`;

  const meta = loadRunHistory(workDir).find((r) => r.runId === runId)?.meta;
  const stages = loadStageEntries(workDir, runId);
  const llms = loadLLMInteractions(workDir, runId);

  const lines: string[] = [
    `=== Kjørings-detalj: ${runId} ===`,
    `Logg-fil: ${basename(logPath)}`,
    "",
  ];

  if (meta) {
    lines.push(`Status:      ${meta.exit_status}`);
    lines.push(`Varighet:    ${formatDuration(meta.duration_ms)}`);
    lines.push(`Start:       ${meta.start_time?.slice(0, 19).replace("T", " ") ?? "─"}`);
    lines.push(`Slutt:       ${meta.end_time?.slice(0, 19).replace("T", " ") ?? "─"}`);
    lines.push(`Git commit:  ${meta.git_commit?.slice(0, 8) ?? "─"}${meta.git_dirty ? " (dirty)" : ""}`);
    lines.push(`Gjenopptok:  Trinn ${meta.resume_from}`);
    if (meta.args) {
      const argStr = Object.entries(meta.args)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => `--${k} ${v}`)
        .join(" ");
      if (argStr) lines.push(`Argv:        ${argStr}`);
    }
    lines.push("");
  }

  // Stage breakdown
  lines.push("Stadier:");
  lines.push(`${"#".padEnd(4)} ${"Stage".padEnd(16)} ${"Status".padEnd(10)} ${"Varighet".padEnd(12)} ${"Feil"}`);
  lines.push(`${"─".repeat(4)} ${"─".repeat(16)} ${"─".repeat(10)} ${"─".repeat(12)} ${"─".repeat(20)}`);
  for (const s of stages) {
    const index = `${s.stage_index}.`;
    const name = STAGE_LABELS[s.stage_name] ?? s.stage_name;
    const statusIcon = s.status === "ok" ? "✓" : s.status === "skipped" ? "─" : "✗";
    const duration = s.duration_ms ? formatDuration(s.duration_ms) : "─";
    const error = s.error ? s.error.slice(0, 40) : "";
    lines.push(
      `${index.padEnd(4)} ${name.padEnd(16)} ${statusIcon.padEnd(10)} ${duration.padEnd(12)} ${error}`,
    );
    if (s.data_volume) {
      const volStr = Object.entries(s.data_volume)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      lines.push(`    Data: ${volStr}`);
    }
  }

  // LLM interactions
  if (llms.length > 0) {
    lines.push("");
    lines.push(`LLM-interaksjoner (${llms.length}):`);
    for (const llm of llms.slice(0, 10)) {
      const stage = (llm.stage_name as string) ?? "?";
      const action = (llm.action as string) ?? "?";
      const confidence = llm.confidence !== undefined ? ` (confidence: ${llm.confidence})` : "";
      const tokens = llm.tokens !== undefined ? ` [${llm.tokens} tokens]` : "";
      lines.push(`  • ${stage}: ${action}${confidence}${tokens}`);
    }
    if (llms.length > 10) lines.push(`  ... og ${llms.length - 10} flere`);
  }

  // Tournament updates
  const updates = loadTournamentUpdates(workDir, runId);
  if (updates.length > 0) {
    lines.push("");
    lines.push(`Turneringsoppdateringer (${updates.length}):`);
    for (const u of updates.slice(0, 10)) {
      const op = (u.operation as string) ?? "?";
      const tid = (u.tournament_id as string) ?? "?";
      const success = u.success === true ? "\u2713" : u.success === false ? "\u2717" : "?";
      const summary = (u.summary_nb as string) ?? "";
      const firstLine = summary.split("\n")[0].slice(0, 80);
      lines.push(`  ${success} [${tid}] ${op === "team_drop" ? "Fjern lag" : op === "date_move" ? "Flytt dato" : op}: ${firstLine}`);
    }
    if (updates.length > 10) lines.push(`  ... og ${updates.length - 10} flere`);
  }

  return lines.join("\n");
}



function buildLogsStatsText(workDir: string): string {
  const runs = loadRunHistory(workDir);
  if (runs.length === 0) {
    return `Ingen loggførte kjøringer funnet i ${join(workDir, "logs")}/`;
  }

  const successRuns = runs.filter((r) => r.meta?.exit_status === "success");
  const failRuns = runs.filter((r) => r.meta?.exit_status === "failure");
  const totalDuration = runs.reduce((s, r) => s + (r.meta?.duration_ms ?? 0), 0);
  const avgDuration = runs.length > 0 ? Math.round(totalDuration / runs.length) : 0;

  const lines: string[] = [
    "=== Pipeline selvforbedrings-statistikk ===",
    "",
    `Totalt antall kjøringer: ${runs.length}`,
    `Vellykkede:              ${successRuns.length}`,
    `Feil:                    ${failRuns.length}`,
    `Feilrate:                ${runs.length > 0 ? Math.round((failRuns.length / runs.length) * 100) : 0}%`,
    `Gjennomsnittlig varighet: ${formatDuration(avgDuration)}`,
    `Siste kjøring:           ${runs[0]?.meta?.start_time?.slice(0, 10) ?? "─"}`,
    "",
  ];

  // Stage-level stats
  const stageStats: Record<string, { count: number; totalMs: number; fails: number }> = {};
  for (const { meta, runId: rid, logPath: lp } of runs) {
    if (!meta) continue;
    const stages = loadStageEntries(workDir, rid);
    for (const s of stages) {
      if (!s.duration_ms) continue;
      (stageStats[s.stage_name] ??= { count: 0, totalMs: 0, fails: 0 });
      stageStats[s.stage_name].count++;
      stageStats[s.stage_name].totalMs += s.duration_ms;
      if (s.status === "failed") stageStats[s.stage_name].fails++;
    }
  }

  if (Object.keys(stageStats).length > 0) {
    lines.push("Stage-statistikk:");
    lines.push(`${"Stage".padEnd(20)} ${"Kjøringer".padEnd(12)} ${"Gj.snitt".padEnd(12)} ${"Feil".padEnd(8)} ${"Feilrate"}`);
    lines.push(`${"─".repeat(20)} ${"─".repeat(12)} ${"─".repeat(12)} ${"─".repeat(8)} ${"─".repeat(8)}`);
    for (const [name, stats] of Object.entries(stageStats)) {
      const avgS = formatDuration(Math.round(stats.totalMs / stats.count));
      const failRate = stats.count > 0 ? `${Math.round((stats.fails / stats.count) * 100)}%` : "0%";
      lines.push(
        `${name.padEnd(20)} ${String(stats.count).padEnd(12)} ${avgS.padEnd(12)} ${String(stats.fails).padEnd(8)} ${failRate}`,
      );
    }
    lines.push("");
  }

  // Duration trend (last 5 runs)
  const recentRuns = runs.slice(0, 5).filter((r) => r.meta?.duration_ms);
  if (recentRuns.length >= 2) {
    lines.push("Varighetstrend (siste 5 kjøringer):");
    for (const r of recentRuns) {
      const date = r.meta!.start_time?.slice(0, 10) ?? "??";
      lines.push(`  ${date}  ${formatDuration(r.meta!.duration_ms)}  (${r.meta!.exit_status})`);
    }
    // Direction arrow
    const first = recentRuns[recentRuns.length - 1]?.meta?.duration_ms ?? 0;
    const last = recentRuns[0]?.meta?.duration_ms ?? 0;
    if (first > 0 && last > 0) {
      const pct = Math.round(((last - first) / first) * 100);
      const arrow = pct < -5 ? "↓" : pct > 5 ? "↑" : "→";
      lines.push(`  Trend: ${arrow} ${Math.abs(pct)}% (${formatDuration(first)} → ${formatDuration(last)})`);
    }
  }

  return lines.join("\n");
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return `${m}m ${s}s`;
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
}

// ---------------------------------------------------------------------------
// Pipeline runner
// ---------------------------------------------------------------------------
// Interactive guide — wizard that asks questions and dispatches
// ---------------------------------------------------------------------------

async function interactiveGuide(ctx: ExtensionCommandContext): Promise<void> {
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
      "  1. Konfigurasjon — leser input.json og validerer",
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
      "  --input <fil>            — konfigurasjonsfil (standard: input.json)",
      "  --resume-from <trinn>    — gjenoppta fra trinn 1-4",
      "",
      "Nokkel-filer:",
      "  input.json               — klubb-/lag-konfigurasjon",
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
    "Konfigurasjonsfil (standard: input.json):",
    "input.json",
  );
  const finalInput = inputFile || "input.json";

  // Step 2: Check if input.json exists
  const inputPath = resolve(ctx.cwd, finalInput);
  if (!existsSync(inputPath)) {
    ctx.ui.notify(
      `Finner ikke ${finalInput} — opprett en input.json eller angi riktig sti.`,
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

  await runPipeline(argsParts.join(" "), ctx);
}


// ---------------------------------------------------------------------------

async function runPipeline(rawArgs: string, ctx: ExtensionCommandContext): Promise<void> {
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
      overallStatus = "failure";
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
  } else {
    lines.push("Trinn 1: Hoppet over (gjenopptatt)\n");
    logger.stageStart("config");
    logger.stageEnd("config", "skipped");
  }

  // -------------------------------------------------------------------
  // Stage 2 — Scraping
  // -------------------------------------------------------------------
  if (resumeFrom <= 2) {
    lines.push("Trinn 2: Skraper kalenderkilder...");
    logger.stageStart("scraping");
    try {
      const { stdout, stderr } = await runStage(
        cwdPath,
        "tournament_scheduler.pipeline.stage2_scraping",
        [...baseArgs],
      );
      if (verbose) logger.logStageOutput("scraping", stdout, stderr);
      if (stdout) lines.push(stdout);
      if (stderr) lines.push(`[stderr] ${stderr}`);
      lines.push("Trinn 2: OK\n");

      const ckpt = readCheckpoint(workDir, "stage2_scraping.json");
      logger.stageEnd("scraping", "ok", undefined, estimateDataVolume(ckpt));

      // Log blocked sources if present
      if (ckpt?.data) {
        const data = ckpt.data as Record<string, unknown>;
        const blocked = (data.blocked as string[]) ?? [];
        if (blocked.length > 0) {
          logger.logLLMInteraction("scraping", {
            action: "blocked_sources",
            sources: blocked,
            count: blocked.length,
          });
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      lines.push(`Trinn 2 FEILET:\n${msg}`);
      logger.stageEnd("scraping", "failed", msg);
      logger.finalize("failure");
      overallStatus = "failure";
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
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
      overallStatus = "failure";
      ctx.ui.notify(lines.join("\n"), "error");
      return;
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
      overallStatus = "failure";
      ctx.ui.notify(lines.join("\n"), "error");
      return;
    }
  } else {
    lines.push("Trinn 4: Hoppet over (gjenopptatt)\n");
    logger.stageStart("export");
    logger.stageEnd("export", "skipped");
  }

  // Finalize
  logger.finalize(overallStatus);

  lines.push("=== Pipeline fullfort ===");
  lines.push(buildStatusText(workDir));

  // Add a self-improvement summary
  if (overallStatus === "success") {
    lines.push("");
    lines.push("For å se kjøringshistorikk og trender:");
    lines.push("  /rvv-miniputt logs list   — vis siste kjøringer");
    lines.push("  /rvv-miniputt logs stats  — vis selvforbedringsstatistikk");
    lines.push(`  /rvv-miniputt logs show ${logger.getRunId()}  — vis detaljer for denne kjøringen`);
  }

  ctx.ui.notify(lines.join("\n"), overallStatus === "success" ? "info" : "error");
}
