// ---------------------------------------------------------------------------
// Argument parsers for rvv-miniputt slash commands
// ---------------------------------------------------------------------------

import type { RunArgs, StatusArgs, LogsArgs, CalendarsArgs } from "./types";
import { join } from "node:path";
import { existsSync, readdirSync } from "node:fs";
import { cwd } from "node:process";
import { normalizeArgs } from "./arg-utils";

export function parseRunArgs(args: unknown): RunArgs {
  const result: RunArgs = {};
  const tokens = normalizeArgs(args).split(/\s+/).filter(Boolean);
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

export function parseStatusArgs(args: unknown): StatusArgs {
  const result: StatusArgs = {};
  const tokens = normalizeArgs(args).split(/\s+/).filter(Boolean);
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i] === "--work-dir" && i + 1 < tokens.length) result.work_dir = tokens[++i];
  }
  return result;
}

export function parseLogsArgs(args: unknown): LogsArgs {
  const result: LogsArgs = { subcommand: "list" };
  const tokens = normalizeArgs(args).split(/\s+/).filter(Boolean);
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

export function parseCalendarsArgs(args: unknown): CalendarsArgs {
  const result: CalendarsArgs = {};
  const tokens = normalizeArgs(args).split(/\s+/).filter(Boolean);
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t === "--refresh") result.refresh = true;
    else if (t === "--work-dir" && i + 1 < tokens.length) result.work_dir = tokens[++i];
  }
  return result;
}

export function isVerbose(rawArgs: unknown): boolean {
  return parseRunArgs(rawArgs).log_level === "verbose";
}
