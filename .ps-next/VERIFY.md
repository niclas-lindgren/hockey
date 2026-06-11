# Verification Report

STATUS: FAIL

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| run: ls export/ | PASS | exit 0; output: calendars.html
debug-screenshots
season_plan.csv
season_plan.html
season_plan.ics
season_plan.xlsx
season_plan_overview.csv
season_plan_spond.xlsx
season_plan_t |
| grep: timestampedExportDir .pi/lib/pipeline-runner.ts | FAIL | not found .pi/lib/pipeline-runner.ts in timestampedExportDir |
| grep: input.json .pi/lib/pipeline-runner.ts | FAIL | not found .pi/lib/pipeline-runner.ts in input.json |
| grep: flatFiles .pi/lib/pipeline-runner.ts | FAIL | not found .pi/lib/pipeline-runner.ts in flatFiles |
