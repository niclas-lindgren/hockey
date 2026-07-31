# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| Run the import workflow with the current Power Automate payload (schemaVersion=1, worksheet=Årshjul, values as 2D array) and verify it succeeds without Office Script changes. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Valid `content_json` is imported to `inputs/activities/activities.json`. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Invalid JSON, schema version, worksheet name, or `values` shape is rejected with a clear error. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| The issue-provided `target_path` cannot cause writes outside the canonical destination. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| An unchanged payload creates no commit. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| A changed payload creates a deterministic commit. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Activity generation and publishing run automatically after a changed import (via workflow_call, not push event). | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| A successful or unchanged run comments on and closes the sync issue. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| A failed run leaves the sync issue open with a useful failure comment and Actions link. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| Run `pytest tests/test_activity_export.py -v` and confirm tests pass for parsing, validation, canonical serialization, unchanged imports, changed imports, and issue-closing behavior. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
