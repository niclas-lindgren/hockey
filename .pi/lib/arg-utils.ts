/**
 * Normalize whatever value the host passes as command arguments into a single
 * trimmed string suitable for tokenization. Local models (LM Studio/Qwen) may
 * hand `pi.registerCommand` handlers `undefined`/`null`, an array of tokens,
 * or a string wrapped in stray quotes, where remote models always pass a clean
 * string — this is the single point where all of those shapes converge.
 */
export function normalizeArgs(args: unknown): string {
  if (args === null || args === undefined) {
    return "";
  }

  if (Array.isArray(args)) {
    return args.map((a) => String(a)).join(" ").trim();
  }

  const str = typeof args === "string" ? args : String(args);

  // Strip a single pair of wrapping quotes some local models echo back
  // around the whole argument string (e.g. `"--refresh"`).
  return str.trim().replace(/^(["'])(.*)\1$/, "$2").trim();
}
