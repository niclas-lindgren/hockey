// ---------------------------------------------------------------------------
// Log inspection — display functions for /rvv-miniputt logs
// ---------------------------------------------------------------------------

import type { RunMeta, StageMeta, LogEntry } from "./types";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, join, resolve, sep } from "node:path";

const STAGE_LABELS: Record<string, string> = {
  config: "Konfigurasjon",
  scraping: "Skraping",
  planning: "Planlegging",
  export: "Eksport",
};

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return `${m}m ${s}s`;
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
  const exportRoot = resolve(workDir, "..", "export");
  const candidates = [
    ...collectRunLogCandidates(exportRoot),
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
    const inExport = path.startsWith(`${exportRoot}${sep}`);
    const existingInExport = existing.startsWith(`${exportRoot}${sep}`);
    if (inExport && !existingInExport) {
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

export function loadRunHistory(workDir: string): Array<{ runId: string; logPath: string; meta: RunMeta | null }> {
  const runs: Array<{ runId: string; logPath: string; meta: RunMeta | null }> = [];
  for (const logPath of historicalRunLogPaths(workDir)) {
    const runId = basename(logPath).replace(/\.jsonl$/, "");
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

function resolveRunLogPath(workDir: string, runId: string): string | null {
  const paths = historicalRunLogPaths(workDir);
  if (runId === "latest") return paths[0] ?? null;
  return paths.find((path) => basename(path) === `${runId}.jsonl`) ?? null;
}

export function loadStageEntries(workDir: string, runId: string): StageMeta[] {
  const logPath = resolveRunLogPath(workDir, runId);
  if (!logPath || !existsSync(logPath)) return [];
  const entries: StageMeta[] = [];
  for (const line of readFileSync(logPath, "utf-8").trim().split("\n").filter(Boolean)) {
    try {
      const entry = JSON.parse(line) as LogEntry;
      if (entry.type === "stage_meta") entries.push(entry as StageMeta);
    } catch { /* skip */ }
  }
  return entries;
}

export function loadTournamentUpdates(workDir: string, runId: string): LogEntry[] {
  const logPath = resolveRunLogPath(workDir, runId);
  if (!logPath || !existsSync(logPath)) return [];
  const entries: LogEntry[] = [];
  for (const line of readFileSync(logPath, "utf-8").trim().split("\n").filter(Boolean)) {
    try {
      const entry = JSON.parse(line) as LogEntry;
      if (entry.type === "tournament_update") entries.push(entry);
    } catch { /* skip */ }
  }
  return entries;
}

export function loadLLMInteractions(workDir: string, runId: string): LogEntry[] {
  const logPath = resolveRunLogPath(workDir, runId);
  if (!logPath || !existsSync(logPath)) return [];
  const entries: LogEntry[] = [];
  for (const line of readFileSync(logPath, "utf-8").trim().split("\n").filter(Boolean)) {
    try {
      const entry = JSON.parse(line) as LogEntry;
      if (entry.type === "llm_interaction") entries.push(entry);
    } catch { /* skip */ }
  }
  return entries;
}

function summarizeTokenUsage(entries: LogEntry[]): { calls: number; prompt_tokens: number; completion_tokens: number; total_tokens: number } {
  let promptTokens = 0;
  let completionTokens = 0;
  let totalTokens = 0;
  let calls = 0;

  for (const entry of entries) {
    const prompt = Number(entry.prompt_tokens ?? 0) || 0;
    const completion = Number(entry.completion_tokens ?? 0) || 0;
    const total = Number(entry.total_tokens ?? entry.tokens ?? 0) || 0;
    if (!prompt && !completion && !total) continue;
    calls++;
    promptTokens += prompt;
    completionTokens += completion;
    totalTokens += total || (prompt + completion);
  }

  return { calls, prompt_tokens: promptTokens, completion_tokens: completionTokens, total_tokens: totalTokens };
}

export function summarizeRunTelemetry(workDir: string, runId: string): {
  meta: RunMeta | null;
  stages: StageMeta[];
  llmInteractions: LogEntry[];
  tokenUsage: { calls: number; prompt_tokens: number; completion_tokens: number; total_tokens: number };
} {
  const meta = loadRunHistory(workDir).find((r) => r.runId === runId)?.meta ?? null;
  const stages = loadStageEntries(workDir, runId);
  const llmInteractions = loadLLMInteractions(workDir, runId);
  const tokenUsage = summarizeTokenUsage(llmInteractions);
  return { meta, stages, llmInteractions, tokenUsage };
}

export function buildRunSummaryText(workDir: string, runId: string): string {
  const summary = summarizeRunTelemetry(workDir, runId);
  const lines: string[] = [
    "=== Run statistics ===",
    `Run:        ${runId}`,
    `Status:     ${summary.meta?.exit_status ?? "ukjent"}`,
    `Duration:   ${summary.meta ? formatDuration(summary.meta.duration_ms) : "─"}`,
    `LLM calls:  ${summary.tokenUsage.calls}`,
    `Tokens:     prompt=${summary.tokenUsage.prompt_tokens}, completion=${summary.tokenUsage.completion_tokens}, total=${summary.tokenUsage.total_tokens}`,
  ];

  const stageLines = summary.stages.filter((stage) => stage.duration_ms > 0 || stage.status !== "ok");
  if (stageLines.length > 0) {
    lines.push("", "Stage timings:");
    for (const stage of stageLines) {
      lines.push(`  ${stage.stage_index}. ${stage.stage_name} — ${stage.status} (${formatDuration(stage.duration_ms)})`);
    }
  }

  return lines.join("\n");
}

export function buildLogsListText(workDir: string, count: number): string {
  const runs = loadRunHistory(workDir).slice(0, count);
  if (runs.length === 0) {
    return `Ingen loggførte kjøringer funnet i eksporttreet.`;
  }

  const lines: string[] = [
    `=== Pipeline kjøringshistorie ===`,
    `Logg-katalog: ${dirname(runs[0].logPath)}/`,
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

export function buildLogsShowText(workDir: string, runId: string): string {
  const logPath = resolveRunLogPath(workDir, runId);
  if (!logPath || !existsSync(logPath)) return `Kjøring ${runId} ikke funnet i eksporttreet.`;

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
    const tokenUsage = summarizeTokenUsage(llms);
    lines.push("");
    lines.push(`LLM-interaksjoner (${llms.length}):`);
    lines.push(`  Tokenbruk: prompt=${tokenUsage.prompt_tokens}, completion=${tokenUsage.completion_tokens}, total=${tokenUsage.total_tokens}`);
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

export function buildLogsStatsText(workDir: string): string {
  const runs = loadRunHistory(workDir);
  if (runs.length === 0) {
    return `Ingen loggførte kjøringer funnet i eksporttreet.`;
  }

  const successRuns = runs.filter((r) => r.meta?.exit_status === "success");
  const failRuns = runs.filter((r) => r.meta?.exit_status === "failure");
  const totalDuration = runs.reduce((s, r) => s + (r.meta?.duration_ms ?? 0), 0);
  const avgDuration = runs.length > 0 ? Math.round(totalDuration / runs.length) : 0;

  let tokenCalls = 0;
  let promptTokens = 0;
  let completionTokens = 0;
  let totalTokens = 0;

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
  for (const { meta, runId: rid } of runs) {
    if (!meta) continue;
    const stages = loadStageEntries(workDir, rid);
    for (const s of stages) {
      if (!s.duration_ms) continue;
      (stageStats[s.stage_name] ??= { count: 0, totalMs: 0, fails: 0 });
      stageStats[s.stage_name].count++;
      stageStats[s.stage_name].totalMs += s.duration_ms;
      if (s.status === "failed") stageStats[s.stage_name].fails++;
    }

    const tokenUsage = summarizeTokenUsage(loadLLMInteractions(workDir, rid));
    if (tokenUsage.calls > 0) {
      tokenCalls += tokenUsage.calls;
      promptTokens += tokenUsage.prompt_tokens;
      completionTokens += tokenUsage.completion_tokens;
      totalTokens += tokenUsage.total_tokens;
    }
  }

  if (tokenCalls > 0) {
    lines.push("Tokenbruk (alle kjøringer):");
    lines.push(`  LLM-kall: ${tokenCalls}`);
    lines.push(`  Prompt:   ${promptTokens}`);
    lines.push(`  Completion: ${completionTokens}`);
    lines.push(`  Total:    ${totalTokens}`);
    lines.push("");
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
