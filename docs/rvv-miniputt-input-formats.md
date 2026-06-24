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
- `deltakelser_per_lag` — mykt mål for turneringsdeltakelser per lag (positivt heltall, standard 6)

  Det interne config-nøkkelen er `target_tournament_count` for bakoverkompatibilitet.
  Begge feltnavn aksepteres i `Innstillinger`-arket, men `deltakelser_per_lag` har
  prioritet dersom begge er satt.

### `Aldersgrupper`

Columns:

- `age_group`
- `parallel_games`
- `round_length_minutes` (optional)
- `deltakelser_per_lag_før_jul` / `deltakelser_per_lag_etter_jul` (optional) — split the age-group target before and after Christmas; both values are required when an age-group target is set
- `preferanse_vekt` (optional) — age-group-specific date preference weight

The English aliases `target_tournament_count`, `target_tournament_count_before_christmas`, and `target_tournament_count_after_christmas` are also accepted for compatibility.

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
