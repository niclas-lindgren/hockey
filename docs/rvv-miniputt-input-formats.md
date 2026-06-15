# RVV Miniputt input formats

## Decision

`input.xlsx` is the standard and only supported season-planning input for the RVV Miniputt pipeline.

JSON is still used internally for stage checkpoints, caches, logs, and exports, but organizers should not maintain a root JSON pipeline config. Stage 1 reads the Excel workbook and converts its sheets into the internal config dict before validation.

## Why Excel

| Format | Decision | Reason |
| --- | --- | --- |
| Excel workbook | Standard input | Familiar for organizers, supports multiple sheets for related data, works with existing `openpyxl` dependency, and can be validated by the existing Stage 1 rules. |
| CSV | Not supported as primary input | The RVV config needs multiple related tables and per-age-group settings; a CSV bundle would be easier to break and harder to validate. |
| JSON root config | Removed as operator input | Good for machines, but too brittle for non-technical organizers and no longer the project standard. |

## Workbook sheets

The root workbook should be named `input.xlsx` by convention. `rvv-miniputt run` uses it by default.

### `Innstillinger`

Two columns: `felt`, `verdi`.

Common rows:

- `start_date` — `YYYY-MM-DD`
- `end_date` — `YYYY-MM-DD`
- `target_tournament_count` — positive integer

### `Aldersgrupper`

Columns:

- `age_group`
- `parallel_games`
- `round_length_minutes` (optional)

### `Lag`

Columns:

- `club`
- `label`
- `age_group`
- `region` (optional)
- `skill_level` (optional)

### `Kilder`

Columns:

- `name`
- `type`
- `url`

Empty rows are ignored. Stage 1 surfaces validation errors in Norwegian after importing the workbook.
