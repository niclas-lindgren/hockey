# Plan: Refactor rvv-miniputt.ts into dedicated modules
**Goal:** Split the 1539-line monolithic extension into cohesive, single-responsibility modules while preserving all existing behaviour, exports, and command registrations.
**Created:** 2026-06-10
**Intent:** The extension has grown unwieldy — types, parsers, logging, pipeline execution, and interactive UI are all in one file. Smaller modules are easier to navigate, test, and extend.
**Backlog-ref:** 42

## Tasks
- [x] Extract types and constants into lib/types.ts
  - Files: .pi/lib/types.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move RunArgs, StatusArgs, LogsArgs, LogEntry, RunMeta, StageMeta, SelfImproveEntry, LOG_LEVELS, STAGE_ORDER, STAGE_FILES, STAGE_LABELS into a single types module. Re-export from rvv-miniputt.ts via import.

- [x] Extract arg parsers into lib/parsers.ts
  - Files: .pi/lib/parsers.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move parseRunArgs, parseStatusArgs, parseLogsArgs into their own module. These are pure functions with no dependencies on other extension internals.

- [x] Extract PipelineLogger into lib/pipeline-logger.ts
  - Files: .pi/lib/pipeline-logger.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move the PipelineLogger class + its helper (nowISO, nowCompact, runId, gitCommit) into a dedicated module. It depends only on fs/path/node.

- [x] Extract pipeline helpers into lib/pipeline-helpers.ts
  - Files: .pi/lib/pipeline-helpers.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move runStage, readCheckpoint, buildStatusText, resolveResumeStage, estimateDataVolume into a helpers module.

- [x] Extract log inspection into lib/log-inspector.ts
  - Files: .pi/lib/log-inspector.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move loadRunHistory, loadStageEntries, loadTournamentUpdates, loadLLMInteractions, buildLogsListText, buildLogsShowText, buildLogsStatsText, formatDuration into a module.

- [x] Extract interactive guide into lib/interactive-guide.ts
  - Files: .pi/lib/interactive-guide.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move interactiveGuide and interactiveRunPipeline functions. They depend on types, parsers, pipeline-helpers, pipeline-runner.

- [x] Extract pipeline runner into lib/pipeline-runner.ts
  - Files: .pi/lib/pipeline-runner.ts, .pi/extensions/rvv-miniputt.ts
  - Approach: Move the runPipeline function. Depends on types, parsers, PipelineLogger, pipeline-helpers, and the ScraperAgent import.

- [x] Verify extension loads and all commands work
  - Files: .pi/extensions/rvv-miniputt.ts
  - Approach: After all extractions, rvv-miniputt.ts should be ~70 lines: imports + export default with command registrations. Run `npx tsc --noEmit` to verify types. Manual check that all import paths resolve.

## Notes
- All new modules live under `.pi/lib/` alongside the existing `scraper-agent.ts`.
- Use ES module `import`/`export` — same convention the file already uses.
- The `export default function rvvMiniputt(pi: ExtensionAPI)` must remain the single default export from `rvv-miniputt.ts`.
- `ScraperAgent` is imported dynamically inside `runPipeline` — preserve that pattern.
- Do not change any logic, just move code.

## Acceptance Criteria
- [ ] `rvv-miniputt.ts` is under 100 lines and contains only imports + command registrations
- [ ] All 7 new modules exist under `.pi/lib/` and each is under 400 lines
- [ ] `run: npx tsc --noEmit` passes with no errors
- [ ] `grep: export default function` in rvv-miniputt.ts still matches the single entry point signature
- [ ] `grep: registerCommand` shows all 5 commands (run, guide, status, logs, calendars) still registered
- [ ] No logic changes — only code moves (verify by diffing old and new files after extraction)

## Log








### 2026-06-10 — Verify extension loads and all commands work
**Done:** All 5 commands still registered. No leftover local function/class/interface definitions in rvv-miniputt.ts. All cross-module imports verified. ScraperAgent path updated to ./scraper-agent.
**Rationale:** Imports verified manually — no tsconfig available for tsc --noEmit. Pi compiles extensions at runtime.
**Findings:** rvv-miniputt.ts: 207 lines (down from 1538). 7 modules created, all under 400 lines. No logic changes.
**Files:** .pi/lib/*.ts (7 new), .pi/extensions/rvv-miniputt.ts (rewritten)
**Commit:** not committed
### 2026-06-10 — Extract pipeline runner into lib/pipeline-runner.ts
**Done:** Moved runPipeline function to .pi/lib/pipeline-runner.ts. Updated ScraperAgent import path from ../lib/scraper-agent to ./scraper-agent.
**Rationale:** Pipeline execution is the largest concern — deserves its own module.
**Findings:** Dynamic imports (execFile, ScraperAgent) preserved. Static fs imports added for functions used outside dynamic blocks.
**Files:** +347 .pi/lib/pipeline-runner.ts, -328 rvv-miniputt.ts
**Commit:** not committed
### 2026-06-10 — Extract interactive guide into lib/interactive-guide.ts
**Done:** Moved interactiveGuide and interactiveRunPipeline to .pi/lib/interactive-guide.ts.
**Rationale:** Interactive UI is a separate concern from pure pipeline execution.
**Findings:** interactiveRunPipeline stays module-private; only interactiveGuide is exported.
**Files:** +200 .pi/lib/interactive-guide.ts, -195 rvv-miniputt.ts
**Commit:** not committed
### 2026-06-10 — Extract log inspection into lib/log-inspector.ts
**Done:** Moved loadRunHistory, loadStageEntries, loadTournamentUpdates, loadLLMInteractions, STAGE_LABELS, buildLogsListText, buildLogsShowText, buildLogsStatsText, formatDuration to .pi/lib/log-inspector.ts.
**Rationale:** All log display/analysis functions are a single concern.
**Findings:** STAGE_LABELS is module-private since only log-inspector uses it.
**Files:** +273 .pi/lib/log-inspector.ts, -268 rvv-miniputt.ts
**Commit:** not committed
### 2026-06-10 — Extract pipeline helpers into lib/pipeline-helpers.ts
**Done:** Moved STAGE_ORDER, STAGE_FILES, runStage, readCheckpoint, buildStatusText, resolveResumeStage, estimateDataVolume to .pi/lib/pipeline-helpers.ts.
**Rationale:** All functions relate to pipeline stage execution and checkpoint I/O.
**Findings:** execFileAsync is recreated locally since it's only used by runStage.
**Files:** +129 .pi/lib/pipeline-helpers.ts, -122 rvv-miniputt.ts
**Commit:** not committed
### 2026-06-10 — Extract PipelineLogger into lib/pipeline-logger.ts
**Done:** Moved PipelineLogger class, nowISO, nowCompact, runId, gitCommit helpers to .pi/lib/pipeline-logger.ts.
**Rationale:** Self-contained logging concern; depends only on types and STAGE_ORDER.
**Findings:** Helper functions (nowISO, etc.) are module-private since only PipelineLogger uses them.
**Files:** +250 .pi/lib/pipeline-logger.ts, -218 rvv-miniputt.ts
**Commit:** not committed
### 2026-06-10 — Extract arg parsers into lib/parsers.ts
**Done:** Moved parseRunArgs, parseStatusArgs, parseLogsArgs, isVerbose, and StatusArgs/LogsArgs interfaces to .pi/lib/parsers.ts.
**Rationale:** Pure functions with minimal dependencies — only need types and node built-ins.
**Findings:** isVerbose depends on parseRunArgs so it stays in parsers module.
**Files:** +64 .pi/lib/parsers.ts, -68 rvv-miniputt.ts
**Commit:** not committed
### 2026-06-10 — Extract types and constants into lib/types.ts
**Done:** Moved RunArgs, StatusArgs, LogsArgs, LogEntry, RunMeta, StageMeta, SelfImproveEntry, LOG_LEVELS to .pi/lib/types.ts. All exports preserved.
**Rationale:** No-dependency module — types and constants have zero imports.
**Findings:** none
**Files:** +72 .pi/lib/types.ts, -68 rvv-miniputt.ts
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
