# RVV Miniputt input formats

## Decision

`input.xlsx` is the standard and only supported season-planning input for the RVV Miniputt pipeline.

JSON is still used internally for stage checkpoints, caches, logs, and exports, but organizers should not maintain a root JSON pipeline config. Stage 1 reads the Excel workbook and converts its sheets into the internal config dict before validation.

## Why Excel

| Format | Decision | Reason |
| --- | --- | --- |
| Excel workbook | Standard input | Familiar for organizers, supports multiple sheets for related data, works with the existing `openpyxl` dependency, and matches the current Stage 1 parser. |
| CSV | Not used as the primary input | The RVV config needs multiple related tables and per-age-group settings; the Excel workbook fits that shape better. |
| JSON root config | Internal format only | Good for machines, but the workbook is the operator-facing standard. |

## Workbook sheets

The root workbook should be named `input.xlsx` by convention. `rvv-miniputt run` uses it by default.

### `Innstillinger`

Two columns: `felt`, `verdi`.

Current rows:

| felt | Status | Notes |
| --- | --- | --- |
| `start_date` | Required | `YYYY-MM-DD`. Used by Stage 1. |
| `end_date` | Required | `YYYY-MM-DD`. Used by Stage 1. |
| `vekt_cap` | Optional | Caps absolute `preferanse_vekt` values when the workbook is parsed. Useful for keeping preference weights from dominating scoring. |
| `deltakelser_per_lag` | Optional / ignored by Stage 1 | Present in the workbook as a human-facing default, but the current Stage 1 pipeline does not consume it. Per-age-group targets should be set in `Aldersgrupper` instead. |
| `max_hosting_days_per_month` | Optional / ignored by Stage 1 | Reserved scalar knob in the workbook, but not currently wired into the standard Stage 1 → Stage 3 path. |

If you add other scalar rows, the loader will read them, but the current pipeline ignores unknown `Innstillinger` keys.

### `Aldersgrupper`

Columns:

- `age_group`
- `parallel_games`
- `round_length_minutes` (optional)
- `deltakelser_per_lag_før_jul` / `target_tournament_count_before_christmas` (optional)
- `deltakelser_per_lag_etter_jul` / `target_tournament_count_after_christmas` (optional)
- `preferanse_vekt` (optional) — age-group-specific date preference weight

Notes:

- When `Aldersgrupper` is present, it becomes the declared set of age groups.
- If a before/after-Christmas target is set for an age group, both halves should be provided.
- The English aliases are accepted for compatibility.

### `Lag`

Columns:

- `club`
- `label`
- `age_group`
- `target_tournament_count` (optional override per team)

Notes:

- Empty rows are ignored.
- Duplicate `label` values are allowed across different age groups, but not within the same age group.
- If `teams` is supplied as a file reference in a lower-level config, the pipeline resolves it relative to the workbook directory.

### `Kilder`

Columns:

- `name`
- `type`
- `url`

Notes:

- Empty rows are ignored.
- Sources with empty URLs are dropped.
- This sheet is optional, but it is the normal place to declare the calendar sources used by Stage 2.

### `Datopreferanser`

Columns:

- `fra`
- `til`
- `vekt`

Notes:

- Optional.
- Positive values penalise dates; negative values reward dates.
- The loader accepts date cells and common date strings.
- Values whose absolute size exceeds `vekt_cap` emit a warning.

## Validation summary

- `start_date` and `end_date` are required.
- `Aldersgrupper` is optional, but when present it constrains the allowed age groups.
- `Lag` is required.
- `Kilder` and `Datopreferanser` are optional.
- Stage 1 currently consumes `start_date`, `end_date`, `vekt_cap`, the age-group sheet values, team roster rows, and optional date preferences; other scalar rows in `Innstillinger` are retained in the workbook for reference but ignored by the current pipeline.
