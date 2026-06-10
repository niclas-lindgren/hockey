# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Run `python3 -c 'from tournament_scheduler.ical.ical_exporter import ICalExporter; e = ICalExporter(); assert hasattr(e, "export_tournament_summary")'` and confirm no error. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `python3 tournament_scheduler.py --generate-season --roster-file <test-file> --export-ical /tmp/test.ics` succeeds (or exits gracefully if scraping unavailable). | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| `pytest` passes. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The generated .ics file contains one VEVENT per tournament with valid DTSTART, LOCATION, and SUMMARY fields. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| When `--ical-age-group U10` is used, only U10 tournaments appear in the .ics. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| When `--ical-per-club` is used, one .ics per club is generated alongside the main .ics. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
