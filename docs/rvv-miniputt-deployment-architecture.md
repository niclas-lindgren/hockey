# RVV Miniputt deployment architecture (minimal)

## Goal
A small RVV organizer group should be able to run the scheduler without owning much infrastructure.

## Recommended shape

- **Frontend / UI**: a static or server-rendered web app for uploads, status, and reports.
- **Python job runner**: a separate worker that runs scraping, planning, and exports on a schedule or queue.
- **Storage**: object storage for workbooks, exports, logs, and cached artifacts.

Keep the runner stateless: it reads an input workbook, writes outputs, and stores run metadata separately.

## Practical hosting options

### Option A — Vercel / Cloudflare frontend + managed Python worker + object storage
**Example**: Cloudflare Pages or Vercel for UI, Fly.io/Render/Railway for the Python worker, S3/R2 for storage.

**Pros**
- Easy to launch.
- Frontend and worker are cleanly separated.
- Storage is cheap and durable.

**Cons**
- Two platforms to operate.
- Worker scheduling/cron can be awkward depending on host.
- More moving parts than a single VPS.

### Option B — Single small VPS
**Example**: one cheap Linux VPS running the UI, worker, and local file storage.

**Pros**
- Simplest mental model.
- Easy access to files and logs.
- Lowest integration effort.

**Cons**
- One box is a single point of failure.
- Backups and monitoring are on you.
- Less clean separation between web traffic and background jobs.

### Option C — Serverless frontend + queue + container worker
**Example**: Cloudflare/Vercel frontend, managed queue, Docker worker, object storage.

**Pros**
- Scales well.
- Strong separation of concerns.
- Good if the project grows.

**Cons**
- More complex than this project needs.
- Usually overkill for a tiny organizer team.

## Recommended choice
For a **small user group**, choose **Option A**.

Why:
- It keeps the UI easy to host.
- The Python scheduler stays in a normal runtime where Playwright and file handling are straightforward.
- Storage is explicit and portable.
- You avoid the operational burden of running everything on one VPS, while not paying for a full platform architecture.

## Tradeoffs to accept
- The worker is the real system of record for runs; the frontend should just trigger and display.
- Background jobs must be idempotent.
- Large temporary files should live in object storage or ephemeral worker disk, not inside the frontend.
- A database is optional at first; a tiny team can often start with object storage + small metadata files.

## Minimal deployment layout

```text
[Frontend]
  -> upload input.xlsx
  -> show run status / download exports

[Python job runner]
  -> scrape calendars
  -> plan season
  -> write exports
  -> update run status

[Storage]
  -> input files
  -> pipeline artifacts
  -> exports
  -> logs
```

## When to upgrade later
Move to a queue + dedicated worker pool if:
- runs become frequent,
- multiple users need concurrent planning,
- or you need stronger audit/history guarantees.
