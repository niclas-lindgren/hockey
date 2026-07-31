# System architecture

This document describes the intended high-level architecture and responsibility boundaries. Keep it current when workflows or canonical data locations change.

## Core flow

```text
Microsoft 365 source files and forms
        ↓
Power Automate integration
        ↓
Canonical input files in the repository
        ↓
Repository validation and generation scripts
        ↓
GitHub Actions
        ↓
Generated reports, calendars, and GitHub Pages output
        ↓
WordPress links or embeds
```

## Responsibility boundaries

### Microsoft 365 and Power Automate

Use these for lightweight integration tasks:

- Collect data through Microsoft Forms
- Store or manage working files in Teams and SharePoint
- Validate simple form conditions where necessary before storage
- Copy approved source data into the repository
- Trigger repository updates when a canonical source file changes

Keep complex scheduling, generation, and publishing logic out of Power Automate when it can live in tested repository code.

### Repository code

Use repository scripts for:

- Input validation
- Scheduling and planning logic
- Deterministic transformations
- Calendar and report generation
- Export preparation
- Reproducible local operations

Use the repository's supported command wrappers. Do not bypass them by invoking internal pipeline stages directly when that skips logging, checkpoints, or resumption behavior.

### GitHub Actions

Use GitHub Actions for:

- Running validation and tests
- Generating outputs from canonical inputs
- Publishing GitHub Pages
- Automating repeatable repository operations

### WordPress

Treat WordPress as the presentation layer for public information. Prefer linking to or embedding generated outputs instead of duplicating generation logic or manually maintaining the same data in WordPress.

## Canonical inputs and generated outputs

Canonical inputs should live under `inputs/` as the related migration work is completed. Generated files must be reproducible from canonical inputs and repository code.

Do not manually edit generated outputs. Change the canonical input or generator instead.

When adding or moving an input source, document:

- Its canonical repository path
- Its external source, if any
- How synchronization occurs
- Which command or workflow consumes it
- Which outputs it affects

## Architecture changes

Prefer extending the existing flow over creating a parallel system. Introduce new infrastructure only when a concrete requirement cannot be met reasonably by the existing repository, GitHub Actions, or Microsoft 365 tools.
