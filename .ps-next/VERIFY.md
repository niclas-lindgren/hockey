# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `Tournament` has `cancelled` and `cancellation_reason` fields, round-tripped through checkpoints | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Running `rvv-miniputt cancel --tournament-id <id> --reason "Ishall stengt"` marks the tournament as cancelled and logs the reason | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `rvv-miniputt cancel --tournament-id <id>` without `--makeup-date` lists suggested makeup weekends ranked by proximity to the original date | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Running `rvv-miniputt cancel --tournament-id <id> --makeup-date 2027-03-15` applies the makeup, re-checks conflicts, and clears cancelled state | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| After a successful makeup, the Stage 4 checkpoint is re-exported (unless `--no-export`) | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Cancelled tournaments surface distinctively: Excel rows appear greyed out, iCal events show CANCELLED status, CSV marks cancelled rows, HTML shows a cancelled badge | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| All new code passes existing and new tests | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
