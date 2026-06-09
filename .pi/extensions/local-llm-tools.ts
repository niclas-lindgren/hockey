import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { existsSync, readFileSync, statSync } from "node:fs";

const DEFAULT_BASE_URLS = ["http://localhost:1234/v1", "http://host.lima.internal:1234/v1"];
const DEFAULT_MAX_BYTES = 300_000;
const HARD_MAX_BYTES = 1_000_000;
const DEFAULT_TIMEOUT_MS = 60_000;

function clampMaxBytes(value: unknown): number {
  const parsed = typeof value === "number" && Number.isFinite(value) ? value : DEFAULT_MAX_BYTES;
  return Math.max(1_000, Math.min(Math.floor(parsed), HARD_MAX_BYTES));
}

function redactSensitive(text: string): string {
  return text
    .replace(/([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASS|KEY|AUTH|COOKIE|SESSION)[A-Z0-9_]*\s*[=:]\s*)[^\s'"`]+/gi, "$1[REDACTED]")
    .replace(/\b(?:sk|pk|rk|whsec|re)_(?:live|test)?_[A-Za-z0-9_\-]{12,}\b/g, "[REDACTED_API_KEY]")
    .replace(/Bearer\s+[A-Za-z0-9._\-]+/gi, "Bearer [REDACTED]")
    .replace(/postgres(?:ql)?:\/\/[^\s]+/gi, "postgres://[REDACTED]");
}

function readTail(path: string, maxBytes: number): { text: string; truncated: boolean; size: number } {
  if (!existsSync(path)) throw new Error(`File not found: ${path}`);
  const size = statSync(path).size;
  const buffer = readFileSync(path);
  const start = Math.max(0, buffer.length - maxBytes);
  return {
    text: redactSensitive(buffer.subarray(start).toString("utf8")),
    truncated: start > 0,
    size,
  };
}

function configuredBaseUrls(): string[] {
  const configured = process.env.LOCAL_LLM_BASE_URL;
  const raw = configured ? configured.split(",") : DEFAULT_BASE_URLS;
  return raw.map((url) => url.trim().replace(/\/$/, "")).filter(Boolean);
}

async function callLocalLlm(system: string, user: string): Promise<string> {
  const model = process.env.LOCAL_LLM_MODEL || process.env.LM_STUDIO_MODEL || "local-model";
  const errors: string[] = [];

  for (const baseUrl of configuredBaseUrls()) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    try {
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          model,
          temperature: 0.1,
          max_tokens: 1400,
          messages: [
            { role: "system", content: system },
            { role: "user", content: user },
          ],
        }),
      });

      if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`${response.status} ${response.statusText}${body ? ` — ${body.slice(0, 300)}` : ""}`);
      }

      const payload = await response.json() as {
        choices?: Array<{ message?: { content?: string } }>;
      };
      const content = payload.choices?.[0]?.message?.content?.trim();
      if (!content) throw new Error("Local LLM returned no message content");
      return content;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      errors.push(`${baseUrl}: ${message}`);
    } finally {
      clearTimeout(timeout);
    }
  }

  throw new Error(`Local LLM request failed for all configured endpoints: ${errors.join("; ")}`);
}

const logSummarySystem = `You summarize CI/test/build logs for a coding agent. Be terse and factual.
Return:
- Status: pass/fail/unknown
- Primary failures: bullet list with file/test/error when visible
- Likely cause: one sentence, say unknown if unclear
- Suggested next commands: max 3 commands
Do not invent facts. Mention if input was truncated.`;

const textSummarySystem = `You compress technical text for a coding agent. Preserve exact filenames, commands, error names, and line numbers. Be concise. Do not invent facts.`;

const failureExtractionSystem = `Extract only actionable failures from logs. Group by failing test/file/error. Ignore progress bars, repeated stack frames, and successful output. Return compact bullets plus likely owning file when visible. Do not invent facts.`;

export default function localLlmTools(pi: ExtensionAPI) {
  pi.registerTool({
    name: "local_summarize_text",
    label: "Local summarize text",
    description: "Summarize bounded technical text with the local LM Studio/OpenAI-compatible model. Use for compression only; do not rely on it for final decisions.",
    parameters: Type.Object({
      text: Type.String({ description: "Text to summarize. Keep bounded; secrets are redacted before sending." }),
      focus: Type.Optional(Type.String({ description: "Optional focus, e.g. 'test failures' or 'CI migration error'." })),
    }),
    async execute(_toolCallId, params) {
      const text = redactSensitive(params.text).slice(0, HARD_MAX_BYTES);
      const summary = await callLocalLlm(
        textSummarySystem,
        `${params.focus ? `Focus: ${params.focus}\n\n` : ""}${text}`,
      );
      return {
        content: [{ type: "text", text: `[local-llm summary; verify before acting]\n${summary}` }],
        details: { inputChars: text.length },
      };
    },
  });

  pi.registerTool({
    name: "local_summarize_log",
    label: "Local summarize log",
    description: "Read the tail of a large log file and summarize it with the local LM Studio/OpenAI-compatible model.",
    parameters: Type.Object({
      path: Type.String({ description: "Path to the log/output file to summarize." }),
      maxBytes: Type.Optional(Type.Number({ description: `Tail bytes to read, default ${DEFAULT_MAX_BYTES}, hard max ${HARD_MAX_BYTES}.` })),
      focus: Type.Optional(Type.String({ description: "Optional focus, e.g. 'why did prisma migrate deploy fail?'." })),
    }),
    async execute(_toolCallId, params) {
      const maxBytes = clampMaxBytes(params.maxBytes);
      const { text, truncated, size } = readTail(params.path, maxBytes);
      const summary = await callLocalLlm(
        logSummarySystem,
        `Path: ${params.path}\nSize: ${size} bytes\nTail input truncated: ${truncated}\n${params.focus ? `Focus: ${params.focus}\n` : ""}\n--- LOG TAIL ---\n${text}`,
      );
      return {
        content: [{ type: "text", text: `[local-llm log summary; verify before acting]\n${summary}` }],
        details: { path: params.path, size, maxBytes, truncated },
      };
    },
  });

  pi.registerTool({
    name: "local_extract_failures",
    label: "Local extract failures",
    description: "Read the tail of a CI/test/build log and use the local model to extract only actionable failures.",
    parameters: Type.Object({
      path: Type.String({ description: "Path to the CI/test/build log file." }),
      maxBytes: Type.Optional(Type.Number({ description: `Tail bytes to read, default ${DEFAULT_MAX_BYTES}, hard max ${HARD_MAX_BYTES}.` })),
    }),
    async execute(_toolCallId, params) {
      const maxBytes = clampMaxBytes(params.maxBytes);
      const { text, truncated, size } = readTail(params.path, maxBytes);
      const summary = await callLocalLlm(
        failureExtractionSystem,
        `Path: ${params.path}\nSize: ${size} bytes\nTail input truncated: ${truncated}\n\n--- LOG TAIL ---\n${text}`,
      );
      return {
        content: [{ type: "text", text: `[local-llm failure extraction; verify before acting]\n${summary}` }],
        details: { path: params.path, size, maxBytes, truncated },
      };
    },
  });

  pi.registerCommand("local-llm-status", {
    description: "Check whether the configured local LM Studio/OpenAI-compatible endpoint is reachable",
    handler: async (_args, ctx) => {
      const results: string[] = [];
      for (const baseUrl of configuredBaseUrls()) {
        try {
          const response = await fetch(`${baseUrl}/models`, { signal: AbortSignal.timeout(5_000) });
          if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
          results.push(`✓ ${baseUrl}`);
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          results.push(`✗ ${baseUrl}: ${message}`);
        }
      }
      const reachable = results.some((line) => line.startsWith("✓"));
      ctx.ui.notify(`Local LLM endpoints:\n${results.join("\n")}`, reachable ? "info" : "warning");
    },
  });
}
