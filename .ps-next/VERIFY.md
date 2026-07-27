# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Running `rvv-miniputt scrape --club Holmen` returns Sportello bookings through the deterministic pipeline without requiring `scrape-llm` or interactive browser control. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The docs and operator guidance update Holmen to scriptable status while keeping browser-tool guidance for the remaining blocked sources. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Tests pass for Sportello chunking/parsing and prove stage 2 dispatch routes Holmen through the new scraper. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
