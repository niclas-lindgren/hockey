# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Running `rvv-miniputt run` with `deltakelser_per_lag=6` in `Innstillinger` produces the same plan as `target_tournament_count=6`. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Running with `target_tournament_count` (old name) still works for backward compatibility. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Running with `deltakelser_per_lag` and `target_tournament_count` both set uses `deltakelser_per_lag`. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Running with an invalid value for either field produces a Norwegian validation error. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| All docs list the Norwegian field name `deltakelser_per_lag` as the recommended workbook key. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The rules report and docstrings describe the value as a soft per-team participation target, not as total tournaments. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| An age group that cannot reasonably meet the target produces a warning (not a hard failure). | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
