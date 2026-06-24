# RVV Miniputt input formats

## Decision

`input.xlsx` is the standard and only supported season-planning input for the RVV Miniputt pipeline.

JSON is still used internally for stage checkpoints, caches, logs, and exports, but organizers should not maintain a root JSON pipeline config. Stage 1 reads the Excel workbook and converts its sheets into the internal config dict before validation.

## Why Excel

| Format | Decision | Reason |
| --- | --- | --- |
| Excel workbook | Standard input | Familiar for organizers, supports multiple sheets for related data, works with existing `openpyxl` dependency, and can be validated by the existing Stage 1 rules. |
| CSV | Not used as the primary input | The RVV config needs multiple related tables and per-age-group settings; the Excel workbook fits that shape better. |
| JSON root config | Internal format only | Good for machines, but the Excel workbook is the operator-facing standard. |

## Workbook sheets

The root workbook should be named `input.xlsx` by convention. `rvv-miniputt run` uses it by default.

### `Innstillinger`

Two columns: `felt`, `verdi`.

Common rows:

- `start_date` — `YYYY-MM-DD`
- `end_date` — `YYYY-MM-DD`

### `Aldersgrupper`

Columns:

- `age_group`
- `parallel_games`
- `round_length_minutes` (optional)
- `deltakelser_per_lag_før_jul` / `deltakelser_per_lag_etter_jul` (optional) — split the age-group target before and after Christmas; both values are required when an age-group target is set
- `preferanse_vekt` (optional) — age-group-specific date preference weight

When `Aldersgrupper` is present, it becomes the declared set of age groups and Stage 1 checks that the other sheets reference those values.

The English aliases `target_tournament_count_before_christmas` and `target_tournament_count_after_christmas` are also accepted for compatibility.

### `Lag`

Columns:

- `club`
- `label`
- `age_group`

### `Kilder`

Columns:

- `name`
- `type`
- `url`

Empty rows are ignored. Stage 1 surfaces validation errors in Norwegian after importing the workbook.

