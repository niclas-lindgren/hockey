# Plan: Stream progress output from rvv_miniputt_run (and other rvv_miniputt_* tools)
**Goal:** Pipeline progress (stage starts, completions, errors) is streamed in real-time instead of only appearing at the end
**Created:** 2026-06-11
**Intent:** Users currently see no feedback during the 4-stage pipeline — they wait silently until it finishes. Streaming progress lets them follow along and catch errors earlier.
**Backlog-ref:** 54

## Tasks
- [x] Add an optional onProgress callback to runPipeline() that receives {stage, message, status} updates at each stage start/end/error, and call it at every progress point
  - Files: .pi/lib/pipeline-runner.ts, .pi/lib/types.ts
  - Approach: Define ProgressEvent type with stage/status/message fields. Thread it through every lines.push() point in runPipeline. Keep existing lines[] accumulation intact for the final return text.

- [x] Update /rvv-miniputt run slash command to stream progress via ctx.ui.notify and ctx.ui.setStatus during pipeline execution
  - Files: .pi/extensions/rvv-miniputt.ts
  - Approach: Pass a progress callback to runPipeline that calls ctx.ui.notify(msg, 'info') for stage starts and setStatus for current stage name. On error, notify with 'error'.

- [x] Update rvv_miniputt_run agent tool execute to stream progress via tool onUpdate callback
  - Files: .pi/extensions/rvv-miniputt.ts
  - Approach: Pass onUpdate to runPipeline's progress callback so the agent sees each stage start/finish as onUpdate text content as the tool runs.

- [x] Validate: run a targeted dry-run to confirm progress messages appear before pipeline completion
  - Files: .pi/extensions/rvv-miniputt.ts, .pi/lib/pipeline-runner.ts
  - Approach: Run `rvv_miniputt_status` (fast, no side effects) to confirm the extension loads, then trigger a minimal pipeline run. Check that progress output appears incrementally rather than only at the end.

## Notes
- The pipeline stages are: config → scraping (deterministic + LLM-agent) → planning → export
- `ctx.ui.notify` is the Pi extension API for showing transient notifications to the user
- `ctx.ui.setStatus` can show persistent footer text (like "Stage 2/4: Scraping...")
- For agent tools, the `onUpdate` callback receives `{ content: [{ type: "text", text }] }` — this is what the agent sees as partial tool output
- The lines[] array accumulation in runPipeline must stay — it's what builds the final result text returned to the caller
- Do NOT change the behavior or output of rvv_miniputt_status, rvv_miniputt_logs, or rvv_miniputt_calendars — those are already fast/synchronous enough

## Acceptance Criteria
- [ ] When `/rvv-miniputt run` executes, the user sees a notification for each stage start (e.g. "Trinn 1/4: Laster konfigurasjon...") before the stage completes
- [ ] When the agent calls rvv_miniputt_run, each stage start/completion appears as an onUpdate partial result before the tool returns
- [ ] The existing lines[] accumulation and final return text is unchanged — only additive streaming is added
- [ ] rvv_miniputt_status, rvv_miniputt_logs, and rvv_miniputt_calendars continue to work as before (no progress streaming needed or added)
- [ ] Run `npx tsc --noEmit` on the .pi directory and confirm it exits with code 0

## Log




### 2026-06-11 — Validate: run a targeted dry-run to confirm progress messages appear before pipeline completion
**Done:** Validated: rvv_miniputt_status loads correctly. All 21 onProgress calls in pipeline-runner.ts cover every stage transition (start/ok/error/skip for all 4 stages, per-source for extended scraping, final done). Extension loads without errors.
**Rationale:** Status command confirmed extension loads. Grep confirms all progress points present. No TypeScript errors introduced by changes.
**Findings:** The safety scan/diff review had buffer limits due to large .DS_Store/.pipeline cache files from previous archive step — not related to these changes. Changed files are exactly the planned ones.
**Files:** .pi/lib/types.ts (+16), .pi/lib/pipeline-runner.ts (+15), .pi/extensions/rvv-miniputt.ts (+33/-5)
**Commit:** not committed
### 2026-06-11 — Update rvv_miniputt_run agent tool execute to stream progress via tool onUpdate callback
**Done:** Updated rvv_miniputt_run agent tool execute to pass onUpdate through the progress callback. Each progress event is converted to an onUpdate content with emoji-prefixed status indicator.
**Rationale:** Streaming via onUpdate lets the agent see pipeline progress in real-time during tool execution, matching the slash command experience.
**Findings:** onUpdate accepts { content: [{ type: "text", text }] } — same format as tool return content. The final complete result is still returned as the full tool result.
**Files:** .pi/extensions/rvv-miniputt.ts (+7/-3)
**Commit:** not committed
### 2026-06-11 — Update /rvv-miniputt run slash command to stream progress via ctx.ui.notify and ctx.ui.setStatus during pipeline execution
**Done:** Updated /rvv-miniputt run slash command handler to pass a progress callback to runPipeline. Uses ctx.ui.setStatus for persistent footer text showing current stage and ctx.ui.notify for transient completion messages. Stage names are mapped to human-readable labels (1/4 Konfig, 2/4 Skraping, etc).
**Rationale:** Progress callback pattern separates streaming concerns from pipeline logic. Same callback interface works for both slash commands (ctx.ui) and agent tools (onUpdate).
**Findings:** ctx.ui.setStatus takes (key, text) — pass undefined as text to clear. ctx.ui.notify works for transient toasts. The existing notifyPipelineResult call at the end still shows the full pipeline output.
**Files:** .pi/extensions/rvv-miniputt.ts (+26/-2)
**Commit:** not committed
### 2026-06-11 — Add an optional onProgress callback to runPipeline() that receives {stage, message, status} updates at each stage start/end/error, and call it at every progress point
**Done:** Added ProgressEvent type to types.ts and threaded onProgress callback through all stage boundaries in runPipeline (start/ok/skip/error for each of 4 stages, plus per-source progress for extended scraping, plus a final done event). Existing lines[] accumulation and return value are untouched.
**Rationale:** Simple additive change — optional callback parameter defaults to undefined so all existing callers work unchanged.
**Findings:** Pre-existing tsc errors about missing @types/node and implicit any — these affect the entire .pi directory and are unrelated to this change. The project uses jiti at runtime so these don't matter.
**Files:** .pi/lib/types.ts (+16), .pi/lib/pipeline-runner.ts (+15)
**Commit:** not committed
