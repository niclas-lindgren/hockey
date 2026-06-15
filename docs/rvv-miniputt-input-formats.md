# RVV Miniputt input formats

## Recommendation

Keep the existing JSON schema as the canonical pipeline format, and supplement it with an Excel workbook input format for organizer editing. Excel should be treated as an import/export-friendly editor surface that maps into the same validated config shape as `input.json` before Stage 1 continues.

This gives organizers a familiar spreadsheet while avoiding a second internal schema. CSV is not recommended as the primary format because the RVV input has multiple related collections and nested settings.

## Comparison

| Format | Organizer editability | Validation | Nested settings | Round-trip safety | Pipeline compatibility |
| --- | --- | --- | --- | --- | --- |
| JSON | Poor for non-technical editors; commas/braces are easy to break. | Strong; current Stage 1 validation already works. | Native support for teams, sources, age-group maps, fairness thresholds, and future nested settings. | Good for machines, weaker for manual edits. | Best; current canonical format. |
| CSV | Familiar, but only for one table at a time. Multiple files would be needed. | Moderate; each file can be checked, but cross-file references become fragile. | Weak; nested dictionaries become extra files or encoded strings. | Risky when organizers rename columns or move rows between files. | Requires glue code and conventions for file bundles. |
| Excel workbook | Familiar to organizers; multiple sheets can separate settings, teams, sources, and age groups. | Strong if imported into the current Stage 1 validator; can also add workbook-level hints later. | Good enough for current schema by using one sheet per collection and key/value rows for settings. | Good if JSON remains canonical and Excel is a deliberate import/export surface; formulas/macros should not be required. | Good when workbook parsing produces the same raw dict as `input.json`. |

## Proposed workbook shape

A minimal workbook can use these sheets:

- `Innstillinger`: two columns, `felt` and `verdi`, for `start_date`, `end_date`, and `target_tournament_count`.
- `Aldersgrupper`: columns `age_group`, `parallel_games`, and optional `round_length_minutes`.
- `Lag`: columns `club`, `label`, and `age_group`.
- `Kilder`: columns `name`, `type`, and `url`.

The import layer should ignore empty rows, normalize simple numeric/date cells, and then call the existing Stage 1 validation so Norwegian error messages remain consistent.

## Decision

Favor Excel as a supported input supplement now. Do not replace `input.json` yet. Keeping JSON canonical preserves scriptability, reproducible pipeline runs, timestamped export copies, and low-risk compatibility with downstream stages. Excel support should be considered successful when a workbook can be passed to `--input` and Stage 1 produces the same validated config shape as JSON.
