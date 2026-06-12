import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { exec, execFile } from "node:child_process";
import { promisify } from "node:util";
import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";

const execFileAsync = promisify(execFile);
const execAsync = promisify(exec);

function scriptPath(cwd: string, name: string): string {
  return join(cwd, ".agents", "skills", "pi-next", "scripts", name);
}

async function runScript(cwd: string, name: string, args: string[] = []) {
  const script = scriptPath(cwd, name);
  const { stdout, stderr } = await execFileAsync(script, args, { cwd, maxBuffer: 1024 * 1024 });
  return { stdout: stdout.trim(), stderr: stderr.trim() };
}

async function git(cwd: string, args: string[]): Promise<string> {
  const { stdout } = await execFileAsync("git", ["-C", cwd, ...args], { cwd, maxBuffer: 1024 * 1024 });
  return stdout.trim();
}

function parseState(output: string): Record<string, string> {
  const state: Record<string, string> = {};
  for (const line of output.split(/\r?\n/)) {
    const idx = line.indexOf("=");
    if (idx > -1) state[line.slice(0, idx)] = line.slice(idx + 1);
  }
  return state;
}

function getPsDir(cwd: string): string {
  const inProject = join(cwd, ".ps-next");
  if (existsSync(inProject)) return inProject;
  return resolve(process.env.HOME || "~", ".ps-next", "projects", basename(cwd));
}

function getPlanFile(cwd: string): string {
  return join(getPsDir(cwd), "PLAN.md");
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function extractCurrentTask(plan: string) {
  const lines = plan.split(/\r?\n/);
  const idx = lines.findIndex((line) => /^- \[ \] /.test(line));
  if (idx === -1) return null;

  const taskLine = lines[idx];
  const block: string[] = [taskLine];
  for (let i = idx + 1; i < lines.length; i++) {
    const line = lines[i];
    if (/^- \[[ x]\] /.test(line) || /^## /.test(line)) break;
    block.push(line);
  }

  const task = taskLine.replace(/^- \[ \] /, "").trim();
  const filesLine = block.find((line) => /^\s*- Files:/.test(line));
  const approachLine = block.find((line) => /^\s*- Approach:/.test(line));
  const lessons = block
    .filter((line) => /^\s*- Lesson:/.test(line))
    .map((line) => line.replace(/^\s*- Lesson:\s*/, "").trim());
  const files = filesLine
    ? filesLine.replace(/^\s*- Files:\s*/, "").split(",").map((f) => f.trim()).filter(Boolean)
    : [];
  const approach = approachLine ? approachLine.replace(/^\s*- Approach:\s*/, "").trim() : "";

  return { task, taskLine, taskPrefix: task.slice(0, 80), files, approach, lessons, block: block.join("\n") };
}

function validatePlan(plan: string): string[] {
  const errors: string[] = [];
  const required = ["# Plan:", "**Goal:**", "## Tasks", "## Acceptance Criteria", "## Log"];
  for (const token of required) if (!plan.includes(token)) errors.push(`Missing ${token}`);

  const taskLines = plan.match(/^- \[[ x]\] .+$/gm) ?? [];
  if (taskLines.length === 0) errors.push("No task checkbox lines found");

  const taskSection = plan.split("## Tasks")[1]?.split(/\n## /)[0] ?? "";
  const uncheckedOrChecked = [...taskSection.matchAll(/^- \[[ x]\] .+$/gm)];
  for (const match of uncheckedOrChecked) {
    const start = match.index ?? 0;
    const rest = taskSection.slice(start);
    const next = rest.search(/\n- \[[ x]\] /);
    const block = next === -1 ? rest : rest.slice(0, next);
    const name = match[0].replace(/^- \[[ x]\] /, "");
    if (!/^\s*- Files:/m.test(block)) errors.push(`Task missing Files: ${name}`);
    if (!/^\s*- Approach:/m.test(block)) errors.push(`Task missing Approach: ${name}`);
  }

  const criteria = plan.split("## Acceptance Criteria")[1]?.split(/\n## /)[0]?.split(/\r?\n/).filter((l) => /^- \[[ x]\] /.test(l)) ?? [];
  if (criteria.length === 0) errors.push("No acceptance criteria found");
  const verbs = /(exit|output|return|contain|creat|produc|write|emit|install|print|fail|match|list|show|delet|updat|read|open|complet|\bis\b|\bare\b|has|have|\bno\b|\bnot\b|run|pass|report|call|replac|remov)/i;
  for (const criterion of criteria) if (!verbs.test(criterion)) errors.push(`Acceptance criterion lacks observable verb: ${criterion}`);

  return errors;
}

function appendLogAndCheckTask(plan: string, taskPrefix: string, logEntry: string): string {
  const lines = plan.split(/\r?\n/);
  const idx = lines.findIndex((line) => line.startsWith("- [ ] ") && line.slice(6).startsWith(taskPrefix));
  if (idx === -1) throw new Error(`Unchecked task starting with '${taskPrefix}' not found`);
  lines[idx] = lines[idx].replace("- [ ] ", "- [x] ");
  const updated = lines.join("\n");
  if (!updated.includes("## Log")) throw new Error("PLAN.md is missing ## Log");
  return updated.replace(/(## Log\s*)/, `$1\n${logEntry.trim()}\n`);
}

function lockFile(cwd: string): string {
  return join(getPsDir(cwd), ".lock");
}

function continueFile(cwd: string): string {
  return join(getPsDir(cwd), ".continue-here.md");
}

function appendFixTask(plan: string, task: string, files: string, approach: string): string {
  const block = `- [ ] [Fix] ${task.trim()}\n  - Files: ${files.trim() || "TBD"}\n  - Approach: ${approach.trim() || "Investigate the failing criterion, patch the smallest relevant surface, and rerun verification."}\n`;
  if (!plan.includes("## Tasks")) throw new Error("PLAN.md is missing ## Tasks");
  const nextSection = plan.indexOf("\n## ", plan.indexOf("## Tasks") + 1);
  if (nextSection === -1) return `${plan.trim()}\n${block}`;
  return `${plan.slice(0, nextSection).trim()}\n${block}${plan.slice(nextSection)}`;
}

function extractCriteria(plan: string): string[] {
  return plan
    .split("## Acceptance Criteria")[1]
    ?.split(/\n## /)[0]
    ?.split(/\r?\n/)
    .filter((line) => /^- \[[ x]\] /.test(line))
    .map((line) => line.replace(/^- \[[ x]\] /, "").trim()) ?? [];
}

export default function piNextExtension(pi: ExtensionAPI) {
  pi.registerCommand("pi-next", {
    description: "Run the pi-next autonomous .ps-next workflow (alias for /skill:pi-next)",
    getArgumentCompletions: (prefix) => {
      const words = ["auto", "fresh", "plan", "backlog list", "backlog add", "backlog done"];
      const filtered = words.filter((w) => w.startsWith(prefix));
      return filtered.length ? filtered.map((value) => ({ value, label: value })) : null;
    },
    handler: async (args, ctx) => {
      const trimmed = args.trim();
      if (trimmed === "fresh" || trimmed.startsWith("fresh ")) {
        const freshArgs = trimmed.replace(/^fresh\s*/, "");
        await ctx.waitForIdle();
        const parentSession = ctx.sessionManager.getSessionFile();
        await ctx.newSession({
          parentSession,
          withSession: async (newCtx) => {
            await newCtx.sendUserMessage(`/skill:pi-next ${freshArgs}`.trim());
          },
        });
        return;
      }
      if (!ctx.isIdle()) {
        ctx.ui.notify("Agent is busy; queueing pi-next as a follow-up.", "info");
        pi.sendUserMessage(`/skill:pi-next ${args}`.trim(), { deliverAs: "followUp" });
        return;
      }
      pi.sendUserMessage(`/skill:pi-next ${args}`.trim());
    },
  });

  pi.registerCommand("pi-next-fresh", {
    description: "Start a fresh Pi session and run pi-next there; useful after each completed task/backlog item",
    getArgumentCompletions: (prefix) => {
      const words = ["auto", "plan", "backlog list"];
      const filtered = words.filter((w) => w.startsWith(prefix));
      return filtered.length ? filtered.map((value) => ({ value, label: value })) : null;
    },
    handler: async (args, ctx) => {
      await ctx.waitForIdle();
      const parentSession = ctx.sessionManager.getSessionFile();
      await ctx.newSession({
        parentSession,
        withSession: async (newCtx) => {
          await newCtx.sendUserMessage(`/skill:pi-next ${args}`.trim());
        },
      });
    },
  });

  pi.registerCommand("pi-next-loop", {
    description: "Start a fresh session and ask pi-next to process up to N backlog items autonomously",
    handler: async (args, ctx) => {
      const count = Number.parseInt(args.trim() || "1", 10);
      const limit = Number.isFinite(count) && count > 0 ? Math.min(count, 10) : 1;
      await ctx.waitForIdle();
      const parentSession = ctx.sessionManager.getSessionFile();
      await ctx.newSession({
        parentSession,
        withSession: async (newCtx) => {
          await newCtx.sendUserMessage(`/skill:pi-next auto\n\nProcess up to ${limit} backlog item(s). After each archive, re-check .ps-next state and continue only if there is another open backlog item. Stop on any blocker, failed quality gate, or unsafe handoff state.`);
        },
      });
    },
  });

  pi.registerCommand("pi-next-status", {
    description: "Show .ps-next state without invoking the model",
    handler: async (_args, ctx) => {
      try {
        const { stdout } = await runScript(ctx.cwd, "pi-next-state.sh", [ctx.cwd]);
        const state = parseState(stdout);
        ctx.ui.notify(
          `PLAN=${state.PLAN} UNCHECKED=${state.UNCHECKED} OPEN_BACKLOG=${state.OPEN_BACKLOG} TOP=${state.BACKLOG_TOP_ID || "-"}`,
          "info",
        );
      } catch (err) {
        ctx.ui.notify(`pi-next status failed: ${err instanceof Error ? err.message : String(err)}`, "error");
      }
    },
  });

  pi.registerCommand("pi-next-handoff", {
    description: "Show whether the current .ps-next state is safe to hand off to Claude or Pi",
    handler: async (_args, ctx) => {
      try {
        const { stdout } = await runScript(ctx.cwd, "pi-next-state.sh", [ctx.cwd]);
        const state = parseState(stdout);
        const dirty = await git(ctx.cwd, ["status", "--short"]);
        const planFile = getPlanFile(ctx.cwd);
        const current = existsSync(planFile) ? extractCurrentTask(readFileSync(planFile, "utf8")) : null;
        const cont = join(getPsDir(ctx.cwd), ".continue-here.md");
        const lock = lockFile(ctx.cwd);
        const safe = !dirty && !existsSync(lock);
        ctx.ui.notify(
          `Safe handoff: ${safe ? "yes" : "no"}\nPLAN=${state.PLAN} unchecked=${state.UNCHECKED}\nNext=${current?.task ?? "-"}\nDirty=${dirty ? "yes" : "no"}\nLock=${existsSync(lock) ? "yes" : "no"}\nContinue marker=${existsSync(cont) ? "yes" : "no"}`,
          safe ? "info" : "warning",
        );
      } catch (err) {
        ctx.ui.notify(`pi-next handoff failed: ${err instanceof Error ? err.message : String(err)}`, "error");
      }
    },
  });

  pi.registerTool({
    name: "pi_next_state",
    label: "Pi Next State",
    description: "Read .ps-next workflow state: plan status, unchecked task count, open backlog count, top backlog item.",
    promptSnippet: "Read .ps-next workflow state for pi-next automation",
    promptGuidelines: ["Use pi_next_state before planning or resuming pi-next work."],
    parameters: Type.Object({ args: Type.Optional(Type.String({ description: "Optional user args to pass to state detection" })) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { stdout, stderr } = await runScript(ctx.cwd, "pi-next-state.sh", [ctx.cwd, params.args ?? ""]);
      return { content: [{ type: "text", text: stdout }], details: { state: parseState(stdout), stderr } };
    },
  });

  pi.registerTool({
    name: "pi_next_current_task",
    label: "Pi Next Current Task",
    description: "Return the first unchecked task from .ps-next/PLAN.md with Files, Approach, and Lesson bullets.",
    promptSnippet: "Extract the first unchecked PLAN.md task as structured data",
    promptGuidelines: ["Use pi_next_current_task before implementing pi-next tasks."],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const file = getPlanFile(ctx.cwd);
      if (!existsSync(file)) throw new Error(`PLAN.md not found at ${file}`);
      const task = extractCurrentTask(readFileSync(file, "utf8"));
      if (!task) return { content: [{ type: "text", text: "No unchecked tasks." }], details: { task: null } };
      return { content: [{ type: "text", text: task.block }], details: task };
    },
  });

  pi.registerTool({
    name: "pi_next_mark_task_done",
    label: "Pi Next Mark Task Done",
    description: "Atomically check off a PLAN.md task and append a structured log entry.",
    promptSnippet: "Mark a pi-next task done and append its log entry",
    promptGuidelines: ["Use pi_next_mark_task_done after a task is implemented and checked."],
    parameters: Type.Object({
      taskPrefix: Type.String({ description: "Leading text of the unchecked task, enough to be unique" }),
      done: Type.String(),
      rationale: Type.String(),
      findings: Type.String(),
      files: Type.String({ description: "Compact changed-files summary" }),
      commit: Type.Optional(Type.String({ description: "Short commit hash, or omit for not committed" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const file = getPlanFile(ctx.cwd);
      if (!existsSync(file)) throw new Error(`PLAN.md not found at ${file}`);
      const task = extractCurrentTask(readFileSync(file, "utf8"));
      const taskName = task?.task ?? params.taskPrefix;
      const log = `### ${today()} — ${taskName}\n**Done:** ${params.done}\n**Rationale:** ${params.rationale}\n**Findings:** ${params.findings}\n**Files:** ${params.files}\n**Commit:** ${params.commit || "not committed"}`;
      const updated = appendLogAndCheckTask(readFileSync(file, "utf8"), params.taskPrefix, log);
      writeFileSync(file, updated);
      return { content: [{ type: "text", text: `Marked done: ${taskName}` }], details: { task: taskName } };
    },
  });

  pi.registerTool({
    name: "pi_next_plan_validate",
    label: "Pi Next Plan Validate",
    description: "Validate PLAN.md structure for Claude PS:next/Pi compatibility.",
    promptSnippet: "Validate .ps-next/PLAN.md structure",
    promptGuidelines: ["Use pi_next_plan_validate after writing or editing PLAN.md."],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const file = getPlanFile(ctx.cwd);
      if (!existsSync(file)) throw new Error(`PLAN.md not found at ${file}`);
      const errors = validatePlan(readFileSync(file, "utf8"));
      const text = errors.length ? `INVALID\n${errors.map((e) => `- ${e}`).join("\n")}` : "VALID";
      return { content: [{ type: "text", text }], details: { valid: errors.length === 0, errors } };
    },
  });

  pi.registerTool({
    name: "pi_next_lock",
    label: "Pi Next Lock",
    description: "Acquire, release, or inspect a .ps-next lock file to prevent concurrent Claude/Pi execution.",
    promptSnippet: "Coordinate Claude/Pi handoff with a .ps-next lock",
    promptGuidelines: ["Use pi_next_lock action=status before starting long pi-next work; acquire while executing and release when done."],
    parameters: Type.Object({
      action: Type.Union([Type.Literal("status"), Type.Literal("acquire"), Type.Literal("release")]),
      owner: Type.Optional(Type.String({ description: "Owner label, e.g. pi or claude" })),
      task: Type.Optional(Type.String({ description: "Current task description" })),
      force: Type.Optional(Type.Boolean({ description: "Force acquire/release stale lock" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const psDir = getPsDir(ctx.cwd);
      mkdirSync(psDir, { recursive: true });
      const file = lockFile(ctx.cwd);
      if (params.action === "status") {
        const locked = existsSync(file);
        return { content: [{ type: "text", text: locked ? readFileSync(file, "utf8") : "unlocked" }], details: { locked } };
      }
      if (params.action === "acquire") {
        if (existsSync(file) && !params.force) throw new Error(`Lock exists at ${file}:\n${readFileSync(file, "utf8")}`);
        const text = `locked_by=${params.owner || "pi"}\npid=${process.pid}\nstarted=${new Date().toISOString()}\ntask=${params.task || ""}\n`;
        writeFileSync(file, text);
        return { content: [{ type: "text", text }], details: { locked: true, file } };
      }
      if (params.action === "release") {
        if (existsSync(file)) unlinkSync(file);
        return { content: [{ type: "text", text: "unlocked" }], details: { locked: false, file } };
      }
      throw new Error("Unhandled lock action");
    },
  });

  pi.registerTool({
    name: "pi_next_handoff_status",
    label: "Pi Next Handoff Status",
    description: "Report whether it is safe to hand off .ps-next work between Pi and Claude.",
    promptSnippet: "Check .ps-next handoff safety",
    promptGuidelines: ["Use pi_next_handoff_status before telling the user it is safe to switch between Claude and Pi."],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const { stdout } = await runScript(ctx.cwd, "pi-next-state.sh", [ctx.cwd]);
      const state = parseState(stdout);
      const dirty = await git(ctx.cwd, ["status", "--short"]);
      const planFile = getPlanFile(ctx.cwd);
      const current = existsSync(planFile) ? extractCurrentTask(readFileSync(planFile, "utf8")) : null;
      const cont = join(getPsDir(ctx.cwd), ".continue-here.md");
      const lock = lockFile(ctx.cwd);
      const safe = !dirty && !existsSync(lock);
      const text = [
        `Safe handoff: ${safe ? "yes" : "no"}`,
        `PLAN=${state.PLAN}`,
        `UNCHECKED=${state.UNCHECKED}`,
        `Next task=${current?.task ?? "-"}`,
        `Uncommitted changes=${dirty ? "yes" : "no"}`,
        dirty ? dirty : "",
        `Lock=${existsSync(lock) ? readFileSync(lock, "utf8").trim().replace(/\n/g, "; ") : "none"}`,
        `Continue marker=${existsSync(cont) ? cont : "none"}`,
      ].filter(Boolean).join("\n");
      return { content: [{ type: "text", text }], details: { safe, state, currentTask: current, dirty } };
    },
  });

  pi.registerTool({
    name: "pi_next_quality_gate",
    label: "Pi Next Quality Gate",
    description: "Run standard project quality checks such as typecheck, lint, tests, and build.",
    promptSnippet: "Run pi-next quality gates before task completion or archive",
    promptGuidelines: ["Use pi_next_quality_gate before marking substantial pi-next tasks done and before archiving."],
    parameters: Type.Object({
      level: Type.Optional(Type.Union([Type.Literal("quick"), Type.Literal("standard"), Type.Literal("full")], { description: "quick=typecheck/lint, standard=typecheck/lint/test, full=typecheck/lint/test/build" })),
    }),
    async execute(_toolCallId, params, _signal, onUpdate, ctx) {
      const pkgFile = join(ctx.cwd, "package.json");
      const pkg = existsSync(pkgFile) ? JSON.parse(readFileSync(pkgFile, "utf8")) as { scripts?: Record<string, string> } : {};
      const scripts = pkg.scripts ?? {};
      const level = params.level ?? "standard";
      const wanted = level === "quick" ? ["typecheck", "lint"] : level === "full" ? ["typecheck", "lint", "test", "build"] : ["typecheck", "lint", "test"];
      const commands = wanted.filter((script) => scripts[script]).map((script) => `npm run ${script}`);
      if (commands.length === 0) commands.push("npm test");

      const results: Array<{ command: string; ok: boolean; output: string }> = [];
      for (const command of commands) {
        onUpdate?.({ content: [{ type: "text", text: `Running ${command}...` }] });
        try {
          const { stdout, stderr } = await execAsync(command, { cwd: ctx.cwd, maxBuffer: 2 * 1024 * 1024 });
          results.push({ command, ok: true, output: `${stdout}\n${stderr}`.trim().slice(-4000) });
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : String(err);
          results.push({ command, ok: false, output: message.slice(-4000) });
          break;
        }
      }
      const ok = results.every((r) => r.ok);
      const text = [`STATUS: ${ok ? "PASS" : "FAIL"}`, ...results.map((r) => `\n## ${r.command}\n${r.ok ? "PASS" : "FAIL"}\n${r.output}`)].join("\n");
      return { content: [{ type: "text", text }], details: { ok, level, results } };
    },
  });

  pi.registerTool({
    name: "pi_next_safety_scan",
    label: "Pi Next Safety Scan",
    description: "Scan staged or working diff for secrets, dangerous files, and accidental sensitive changes.",
    promptSnippet: "Scan diffs for secrets and unsafe changes before commit",
    promptGuidelines: ["Use pi_next_safety_scan before autonomous commits."],
    parameters: Type.Object({
      staged: Type.Optional(Type.Boolean({ description: "Scan staged diff instead of working diff" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const diff = await git(ctx.cwd, params.staged ? ["diff", "--cached"] : ["diff"]);
      const nameOutput = await git(ctx.cwd, params.staged ? ["diff", "--cached", "--name-only"] : ["diff", "--name-only"]);
      const files = nameOutput.split(/\r?\n/).filter(Boolean);
      const findings: string[] = [];
      const blockedFiles = [/^\.env(\.|$)/, /\.pem$/, /id_rsa/, /auth\.json$/, /credentials\.json$/];
      for (const file of files) if (blockedFiles.some((re) => re.test(file))) findings.push(`Sensitive file changed: ${file}`);
      const secretPatterns = [
        /sk_live_[A-Za-z0-9]+/,
        /sk_test_[A-Za-z0-9]+/,
        /AKIA[0-9A-Z]{16}/,
        /-----BEGIN (RSA |OPENSSH |EC |)PRIVATE KEY-----/,
        /(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}/i,
      ];
      for (const pattern of secretPatterns) if (pattern.test(diff)) findings.push(`Potential secret pattern: ${pattern}`);
      const ok = findings.length === 0;
      const text = ok ? "STATUS: PASS\nNo sensitive files or obvious secret patterns found." : `STATUS: FAIL\n${findings.map((f) => `- ${f}`).join("\n")}`;
      return { content: [{ type: "text", text }], details: { ok, findings, files } };
    },
  });

  pi.registerTool({
    name: "pi_next_diff_review",
    label: "Pi Next Diff Review",
    description: "Run deterministic review checks over staged or working diff before commit/archive.",
    promptSnippet: "Review current diff for common autonomous-work issues",
    promptGuidelines: ["Use pi_next_diff_review before committing pi-next task results."],
    parameters: Type.Object({
      staged: Type.Optional(Type.Boolean({ description: "Review staged diff instead of working diff" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const diff = await git(ctx.cwd, params.staged ? ["diff", "--cached"] : ["diff"]);
      const stat = await git(ctx.cwd, params.staged ? ["diff", "--cached", "--stat"] : ["diff", "--stat"]);
      const nameOutput = await git(ctx.cwd, params.staged ? ["diff", "--cached", "--name-only"] : ["diff", "--name-only"]);
      const files = nameOutput.split(/\r?\n/).filter(Boolean);
      const warnings: string[] = [];
      if (!diff.trim()) warnings.push("No diff to review.");
      if (files.length > 20) warnings.push(`Large change set: ${files.length} files changed.`);
      if (/\.only\(/.test(diff)) warnings.push("Focused test marker found: .only(...)");
      if (/console\.log\(/.test(diff)) warnings.push("console.log found in diff.");
      if (/TODO|FIXME|placeholder|not implemented/i.test(diff)) warnings.push("TODO/FIXME/placeholder text found in diff.");
      if (/as any\b|: any\b/.test(diff)) warnings.push("TypeScript any usage found in diff.");
      if (files.some((f) => f.includes("node_modules/") || f.includes(".next/"))) warnings.push("Generated/vendor directory changed.");
      const ok = warnings.length === 0 || (warnings.length === 1 && warnings[0] === "No diff to review.");
      const text = [`STATUS: ${ok ? "PASS" : "WARN"}`, stat, ...warnings.map((w) => `- ${w}`)].filter(Boolean).join("\n");
      return { content: [{ type: "text", text }], details: { ok, warnings, files, stat } };
    },
  });

  pi.registerTool({
    name: "pi_next_plan_drift",
    label: "Pi Next Plan Drift",
    description: "Compare changed files to the current PLAN.md task Files list and flag implementation drift.",
    promptSnippet: "Detect drift between current task plan and actual changed files",
    promptGuidelines: ["Use pi_next_plan_drift before marking a pi-next task done."],
    parameters: Type.Object({
      staged: Type.Optional(Type.Boolean({ description: "Compare staged files instead of working tree files" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const planFile = getPlanFile(ctx.cwd);
      if (!existsSync(planFile)) throw new Error(`PLAN.md not found at ${planFile}`);
      const task = extractCurrentTask(readFileSync(planFile, "utf8"));
      if (!task) return { content: [{ type: "text", text: "STATUS: PASS\nNo unchecked current task." }], details: { ok: true } };
      const nameOutput = await git(ctx.cwd, params.staged ? ["diff", "--cached", "--name-only"] : ["diff", "--name-only"]);
      const changed = nameOutput.split(/\r?\n/).filter(Boolean).filter((f) => f !== ".ps-next/PLAN.md");
      const planned = task.files.map((f) => f.replace(/^\.\//, ""));
      const unplanned = changed.filter((file) => !planned.some((p) => p === file || file.startsWith(p.replace(/\/$/, "") + "/")));
      const missing = planned.filter((file) => file !== "TBD" && !changed.some((c) => c === file || c.startsWith(file.replace(/\/$/, "") + "/")));
      const ok = unplanned.length === 0;
      const text = [
        `STATUS: ${ok ? "PASS" : "WARN"}`,
        `Task: ${task.task}`,
        `Planned files: ${planned.join(", ") || "none"}`,
        `Changed files: ${changed.join(", ") || "none"}`,
        unplanned.length ? `Unplanned changes:\n${unplanned.map((f) => `- ${f}`).join("\n")}` : "",
        missing.length ? `Planned files not changed:\n${missing.map((f) => `- ${f}`).join("\n")}` : "",
      ].filter(Boolean).join("\n");
      return { content: [{ type: "text", text }], details: { ok, task, planned, changed, unplanned, missing } };
    },
  });

  pi.registerTool({
    name: "pi_next_verify_plan",
    label: "Pi Next Verify Plan",
    description: "Parse PLAN.md acceptance criteria, run embedded run:/grep: checks, and write .ps-next/VERIFY.md.",
    promptSnippet: "Verify a completed pi-next plan mechanically where possible",
    promptGuidelines: ["Use pi_next_verify_plan when PLAN.md has no unchecked tasks before archiving."],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const psDir = getPsDir(ctx.cwd);
      const planFile = getPlanFile(ctx.cwd);
      if (!existsSync(planFile)) throw new Error(`PLAN.md not found at ${planFile}`);
      const criteria = extractCriteria(readFileSync(planFile, "utf8"));
      if (criteria.length === 0) {
        const report = `# Verification Report\n\nSTATUS: NEEDS_REVIEW\n\nNo acceptance criteria found.\n`;
        writeFileSync(join(psDir, "VERIFY.md"), report);
        return { content: [{ type: "text", text: report }], details: { status: "NEEDS_REVIEW" } };
      }

      const rows: string[] = [];
      let failed = false;
      let manual = false;
      for (const criterion of criteria) {
        if (criterion.startsWith("run:")) {
          const command = criterion.slice(4).trim();
          try {
            const { stdout, stderr } = await execAsync(command, { cwd: ctx.cwd, maxBuffer: 1024 * 1024 });
            rows.push(`| ${criterion.replace(/\|/g, "\\|")} | PASS | exit 0${stdout.trim() ? `; output: ${stdout.trim().slice(0, 160)}` : ""}${stderr.trim() ? `; stderr: ${stderr.trim().slice(0, 160)}` : ""} |`);
          } catch (err: unknown) {
            failed = true;
            const message = err instanceof Error ? err.message : String(err);
            rows.push(`| ${criterion.replace(/\|/g, "\\|")} | FAIL | ${message.replace(/\n/g, " ").slice(0, 220)} |`);
          }
        } else if (criterion.startsWith("grep:")) {
          const body = criterion.slice(5).trim();
          const containsMatch = body.match(/^(.*?)\s+contains\s+(.+)$/);
          const parts = body.split(/\s+/);
          const file = containsMatch?.[1]?.trim() || parts.shift();
          const pattern = containsMatch?.[2]?.trim() || parts.join(" ");
          if (!file || !pattern) {
            failed = true;
            rows.push(`| ${criterion.replace(/\|/g, "\\|")} | FAIL | malformed grep criterion |`);
          } else {
            const target = join(ctx.cwd, file);
            const ok = existsSync(target) && readFileSync(target, "utf8").includes(pattern);
            if (!ok) failed = true;
            rows.push(`| ${criterion.replace(/\|/g, "\\|")} | ${ok ? "PASS" : "FAIL"} | ${ok ? `found ${pattern} in ${file}` : `not found ${pattern} in ${file}`} |`);
          }
        } else {
          manual = true;
          rows.push(`| ${criterion.replace(/\|/g, "\\|")} | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |`);
        }
      }

      const status = failed ? "FAIL" : manual ? "NEEDS_REVIEW" : "PASS";
      const report = `# Verification Report\n\nSTATUS: ${status}\n\n| Criterion | Verdict | Evidence |\n| --- | --- | --- |\n${rows.join("\n")}\n`;
      writeFileSync(join(psDir, "VERIFY.md"), report);
      return { content: [{ type: "text", text: report }], details: { status, failed, manual } };
    },
  });

  pi.registerTool({
    name: "pi_next_git_checkpoint",
    label: "Pi Next Git Checkpoint",
    description: "Inspect git state before/after autonomous pi-next work and optionally create a checkpoint commit.",
    promptSnippet: "Inspect or create git checkpoints for pi-next work",
    promptGuidelines: ["Use pi_next_git_checkpoint before starting autonomous work and before handoff."],
    parameters: Type.Object({
      action: Type.Union([Type.Literal("status"), Type.Literal("commit")]),
      message: Type.Optional(Type.String({ description: "Commit message for action=commit" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const branch = await git(ctx.cwd, ["branch", "--show-current"]).catch(() => "unknown");
      const status = await git(ctx.cwd, ["status", "--short"]);
      const conflicts = status.split(/\r?\n/).filter((l) => /^UU|^AA|^DD|^AU|^UA|^DU|^UD/.test(l));
      if (params.action === "status") {
        const text = `branch=${branch}\ndirty=${status ? "yes" : "no"}\nconflicts=${conflicts.length}\n${status}`.trim();
        return { content: [{ type: "text", text }], details: { branch, dirty: Boolean(status), conflicts, status } };
      }
      if (conflicts.length) throw new Error(`Cannot commit with merge conflicts:\n${conflicts.join("\n")}`);
      if (!status) return { content: [{ type: "text", text: "No changes to commit." }], details: { committed: false } };
      await git(ctx.cwd, ["add", "-A"]);
      await git(ctx.cwd, ["commit", "-m", params.message || "pi-next checkpoint"]);
      const hash = await git(ctx.cwd, ["rev-parse", "--short", "HEAD"]);
      return { content: [{ type: "text", text: `Committed ${hash}` }], details: { committed: true, hash } };
    },
  });

  pi.registerTool({
    name: "pi_next_append_fix_task",
    label: "Pi Next Append Fix Task",
    description: "Append a structured [Fix] task under ## Tasks in PLAN.md.",
    promptSnippet: "Append remediation tasks after verification failures",
    promptGuidelines: ["Use pi_next_append_fix_task instead of manual PLAN.md edits when verification fails."],
    parameters: Type.Object({
      task: Type.String({ description: "Imperative fix task text" }),
      files: Type.String({ description: "Comma-separated expected files" }),
      approach: Type.String({ description: "Concrete approach for the fix" }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const file = getPlanFile(ctx.cwd);
      if (!existsSync(file)) throw new Error(`PLAN.md not found at ${file}`);
      const updated = appendFixTask(readFileSync(file, "utf8"), params.task, params.files, params.approach);
      writeFileSync(file, updated);
      return { content: [{ type: "text", text: `Appended fix task: ${params.task}` }], details: params };
    },
  });

  pi.registerTool({
    name: "pi_next_continue_marker",
    label: "Pi Next Continue Marker",
    description: "Read, write, or clear .ps-next/.continue-here.md for mid-task recovery.",
    promptSnippet: "Manage pi-next continue-here checkpoint markers",
    promptGuidelines: ["Use pi_next_continue_marker to inspect Claude/Pi recovery checkpoints before resuming blocked work."],
    parameters: Type.Object({
      action: Type.Union([Type.Literal("read"), Type.Literal("write"), Type.Literal("clear")]),
      source: Type.Optional(Type.String()),
      stage: Type.Optional(Type.String()),
      task: Type.Optional(Type.String()),
      reason: Type.Optional(Type.String()),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const psDir = getPsDir(ctx.cwd);
      mkdirSync(psDir, { recursive: true });
      const file = continueFile(ctx.cwd);
      if (params.action === "read") {
        const exists = existsSync(file);
        return { content: [{ type: "text", text: exists ? readFileSync(file, "utf8") : "no continue marker" }], details: { exists, file } };
      }
      if (params.action === "clear") {
        if (existsSync(file)) unlinkSync(file);
        return { content: [{ type: "text", text: "continue marker cleared" }], details: { file } };
      }
      const text = `# Continue Here\n\nsource=${params.source || "pi"}\nstage=${params.stage || "unknown"}\ntask=${params.task || ""}\nreason=${params.reason || ""}\nwritten=${new Date().toISOString()}\n`;
      writeFileSync(file, text);
      return { content: [{ type: "text", text }], details: { file } };
    },
  });

  pi.registerTool({
    name: "pi_next_backlog",
    label: "Pi Next Backlog",
    description: "List, get, add, or mark done items in .ps-next/BACKLOG.md.",
    promptSnippet: "Manage .ps-next backlog items",
    promptGuidelines: ["Use pi_next_backlog instead of ad-hoc sed/grep when manipulating BACKLOG.md."],
    parameters: Type.Object({
      action: Type.Union([Type.Literal("list"), Type.Literal("get"), Type.Literal("add"), Type.Literal("done")]),
      id: Type.Optional(Type.Number({ description: "Backlog item id for get/done" })),
      text: Type.Optional(Type.String({ description: "Backlog text for add" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const runBacklog = async (action: string, extra: string[] = []) => {
        const { stdout } = await runScript(ctx.cwd, "pi-next-backlog.sh", [ctx.cwd, action, ...extra]);
        return stdout;
      };

      if (params.action === "list") {
        const stdout = await runBacklog("list");
        const lines = stdout.split(/\r?\n/).filter(Boolean);
        return { content: [{ type: "text", text: stdout || "No open backlog items." }], details: { count: lines.length } };
      }
      if (params.action === "get") {
        if (params.id == null) throw new Error("id is required for get");
        const stdout = await runBacklog("get", [String(params.id)]);
        return { content: [{ type: "text", text: stdout.replace(/^- \[\d+\] \[ \] /, "") }], details: { id: params.id, block: stdout } };
      }
      if (params.action === "add") {
        if (!params.text?.trim()) throw new Error("text is required for add");
        const stdout = await runBacklog("add", [params.text.trim()]);
        const match = stdout.match(/^- \[(\d+)\] \[ \] /);
        return { content: [{ type: "text", text: stdout }], details: { id: match ? Number(match[1]) : undefined } };
      }
      if (params.action === "done") {
        if (params.id == null) throw new Error("id is required for done");
        const stdout = await runBacklog("done", [String(params.id)]);
        return { content: [{ type: "text", text: stdout }], details: { id: params.id } };
      }
      throw new Error("Unhandled action");
    },
  });

  pi.registerTool({
    name: "pi_next_archive",
    label: "Pi Next Archive",
    description: "Archive .ps-next/PLAN.md and optionally mark its backlog-ref done.",
    promptSnippet: "Archive a completed pi-next plan",
    promptGuidelines: ["Use pi_next_archive after pi-next verification passes."],
    parameters: Type.Object({ backlogId: Type.Optional(Type.Number({ description: "Backlog id to mark done; omit to infer manually from PLAN.md first" })) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const psDir = getPsDir(ctx.cwd);
      const { stdout, stderr } = await runScript(ctx.cwd, "pi-next-archive.sh", [psDir, params.backlogId ? String(params.backlogId) : ""]);
      return { content: [{ type: "text", text: `Archived to ${stdout}` }], details: { archivedPlan: stdout, stderr } };
    },
  });
}
