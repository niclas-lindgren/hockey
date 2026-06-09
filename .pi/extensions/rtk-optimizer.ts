import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType, isBashToolResult } from "@earendil-works/pi-coding-agent";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const RTK = "rtk";
const MAX_BASH_RESULT_CHARS = 12_000;
const MAX_ERROR_LINES = 220;
const LOG_READ_LIMIT = 200;
const RTK_NATIVE_PROXY_COMMANDS = new Set([
  "aws",
  "cargo",
  "curl",
  "docker",
  "find",
  "gh",
  "git",
  "glab",
  "go",
  "golangci-lint",
  "gradlew",
  "jest",
  "kubectl",
  "ls",
  "mypy",
  "next",
  "npm",
  "npx",
  "pip",
  "playwright",
  "pnpm",
  "prisma",
  "psql",
  "pytest",
  "rake",
  "rspec",
  "rubocop",
  "ruff",
  "tree",
  "tsc",
  "vitest",
  "wc",
  "wget",
]);

const RTK_COMMAND_ALIASES = new Map([
  ["eslint", "lint"],
]);

function hasRtk(command: string): boolean {
  return /^\s*rtk\b/.test(command) || /(^|[;&|]\s*)rtk\b/.test(command);
}

function hasShellControl(command: string): boolean {
  return /[;&|<>`$()]/.test(command);
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function splitShellWords(input: string): string[] | null {
  const words: string[] = [];
  let current = "";
  let quote: "'" | '"' | null = null;

  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];

    if (quote) {
      if (char === quote) {
        quote = null;
      } else if (char === "\\" && quote === '"' && i + 1 < input.length) {
        i += 1;
        current += input[i];
      } else {
        current += char;
      }
      continue;
    }

    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }

    if (/\s/.test(char)) {
      if (current) {
        words.push(current);
        current = "";
      }
      continue;
    }

    if (char === "\\" && i + 1 < input.length) {
      i += 1;
      current += input[i];
      continue;
    }

    current += char;
  }

  if (quote) return null;
  if (current) words.push(current);
  return words;
}

function rewriteSearchCommand(trimmed: string): string | null {
  const words = splitShellWords(trimmed);
  if (!words || words.length < 2) return null;

  const command = words[0];
  if (!["grep", "egrep", "fgrep", "rg"].includes(command)) return null;

  const leadingFlags: string[] = [];
  let index = 1;
  while (index < words.length && words[index].startsWith("-")) {
    leadingFlags.push(words[index]);
    index += 1;
  }

  const pattern = words[index];
  if (!pattern) return null;
  index += 1;

  const path = words[index] && !words[index].startsWith("-") ? words[index] : ".";
  if (path !== ".") index += 1;

  const extraArgs = [...leadingFlags, ...words.slice(index)];
  if (command === "egrep") extraArgs.unshift("-E");
  if (command === "fgrep") extraArgs.unshift("-F");

  return ["rtk", "grep", pattern, path, ...extraArgs].map(shellQuote).join(" ");
}

function rewriteSimpleCommand(command: string): string | null {
  const trimmed = command.trim();
  if (!trimmed || hasRtk(trimmed)) return null;

  // Keep rewrites conservative: exact/simple commands only. Complex shell pipelines
  // are left alone so semantics are not changed unexpectedly.
  if (hasShellControl(trimmed)) return null;

  if (trimmed === "npm test" || trimmed === "npm run test") return `${RTK} npm run test`;
  if (trimmed === "npm run typecheck") return `${RTK} npm run typecheck`;
  if (trimmed === "npm run lint") return `${RTK} npm run lint`;
  if (trimmed === "npm run build") return `${RTK} next build`;
  if (trimmed === "npm run test:e2e") return `${RTK} playwright test`;

  let match = trimmed.match(/^npx\s+vitest\b(.*)$/);
  if (match) return `${RTK} vitest${match[1]}`;

  match = trimmed.match(/^npx\s+playwright\b(.*)$/);
  if (match) return `${RTK} playwright${match[1]}`;

  match = trimmed.match(/^npx\s+prisma\b(.*)$/);
  if (match) return `${RTK} npx prisma${match[1]}`;

  const searchRewrite = rewriteSearchCommand(trimmed);
  if (searchRewrite) return searchRewrite;

  const words = splitShellWords(trimmed);
  if (words?.length) {
    const alias = RTK_COMMAND_ALIASES.get(words[0]);
    const rtkCommand = alias ?? words[0];
    if (alias || RTK_NATIVE_PROXY_COMMANDS.has(words[0])) {
      return [RTK, rtkCommand, ...words.slice(1)].map(shellQuote).join(" ");
    }
  }

  // Log readers can be huge, especially CI logs. Route simple reads through rtk log.
  match = trimmed.match(/^(?:cat|tail|head)\s+(.+\.(?:log|out|err))(?:\s*)$/);
  if (match) return `${RTK} log ${shellQuote(match[1].trim())}`;

  return null;
}

function isLogPath(path: string): boolean {
  return /(?:^|[/\\])(?:logs?|artifacts?|playwright-report|test-results)(?:[/\\]|$)/i.test(path)
    || /\.(?:log|out|err)$/i.test(path)
    || /(?:ci|test|vitest|playwright|junit|coverage).*\.txt$/i.test(path);
}

function textFromContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (part && typeof part === "object" && "text" in part) {
        const text = (part as { text?: unknown }).text;
        return typeof text === "string" ? text : "";
      }
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

function compactOutput(output: string, logPath: string): string {
  const lines = output.split(/\r?\n/);
  const interesting = lines.filter((line) =>
    /\b(FAIL|FAILED|ERROR|Error|TypeError|AssertionError|ReferenceError|SyntaxError|Unhandled|Exception|warning|Warning)\b/.test(line)
  );
  const selected = (interesting.length ? interesting : lines.slice(-80)).slice(0, MAX_ERROR_LINES);

  return [
    `[rtk-optimizer] Bash output compacted (${output.length.toLocaleString()} chars).`,
    `[rtk-optimizer] Full captured tool output: ${logPath}`,
    "",
    ...selected,
  ].join("\n");
}

export default function rtkOptimizer(pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    if (ctx.hasUI) ctx.ui.notify("rtk optimizer loaded: noisy commands/log reads will be compacted", "info");
  });

  pi.on("tool_call", async (event, ctx) => {
    if (isToolCallEventType("bash", event)) {
      const original = event.input.command;
      const rewritten = rewriteSimpleCommand(original);
      if (rewritten && rewritten !== original) {
        event.input.command = rewritten;
        if (ctx.hasUI) ctx.ui.notify(`rtk rewrite: ${original.trim()} → ${rewritten}`, "info");
      }
      return undefined;
    }

    if (isToolCallEventType("read", event)) {
      const path = event.input.path;
      if (typeof path === "string" && isLogPath(path)) {
        const currentLimit = event.input.limit;
        if (currentLimit === undefined || currentLimit > LOG_READ_LIMIT) {
          event.input.limit = LOG_READ_LIMIT;
          if (ctx.hasUI) ctx.ui.notify(`log read limited to ${LOG_READ_LIMIT} lines: ${path}`, "info");
        }
      }
    }

    return undefined;
  });

  pi.on("tool_result", async (event, ctx) => {
    if (!isBashToolResult(event)) return undefined;

    const output = textFromContent(event.content);
    if (output.length <= MAX_BASH_RESULT_CHARS) return undefined;

    const logDir = join(ctx.cwd, ".pi", "logs");
    if (!existsSync(logDir)) mkdirSync(logDir, { recursive: true });

    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const logPath = join(logDir, `bash-${stamp}-${event.toolCallId}.log`);
    writeFileSync(logPath, output, "utf8");

    return {
      content: [{ type: "text", text: compactOutput(output, logPath) }],
      details: event.details,
      isError: event.isError,
    };
  });
}
