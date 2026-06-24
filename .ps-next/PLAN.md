# Plan: Minimal RVV deployment architecture
**Goal:** Document a small, practical deployment setup for RVV Miniputt with a frontend, Python job runner, and storage, including tradeoffs and recommended hosting options.
**Created:** 2026-06-24
**Intent:** Help a small organizer group choose a simple production shape without over-engineering the stack.
**Backlog-ref:** 202

## Tasks
- [ ] Write the deployment architecture note and hosting recommendation
  - Files: docs/rvv-miniputt-deployment-architecture.md
  - Approach: Describe a minimal 3-part setup (frontend, background job runner, storage), compare 2-3 realistic hosting combinations such as Vercel/Cloudflare + managed Python worker + object storage, call out tradeoffs (cost, ops burden, cron/background limits, state handling), and end with a clear recommendation for a small user group.

## Notes
- Keep this as a concise architecture sketch, not a full platform design.
- Align terminology with the existing RVV docs and the Python/file-based workflow.
- Prefer pragmatic options that work for a tiny organizer team and do not require a database-first rewrite.

## Acceptance Criteria
- [ ] Confirm `docs/rvv-miniputt-deployment-architecture.md` exists and names at least one recommended stack plus its main tradeoffs.
- [ ] Show that the note mentions a frontend, a Python job runner, and storage as separate concerns.
- [ ] State a clear recommendation for a small user group.

## Log
<!-- pi-next appends entries here after each task -->
