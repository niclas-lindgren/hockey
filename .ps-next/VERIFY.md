# Verification Report

STATUS: NEEDS_REVIEW

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| docs/ownership-and-handover.md contains a critical ownership inventory covering GitHub/Pages, Microsoft Forms, SharePoint/List/Excel, Power Automate, Spond, WordPress, calendar credentials, domains/DNS/analytics/notifications, and release signing/notarization identities. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| docs/ownership-and-handover.md must contain an operator-role matrix that maps least-privilege permissions across GitHub, Microsoft 365, WordPress, and Spond. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| docs/ownership-and-handover.md documents managed secret storage, rotation, annual review, emergency recovery, and a second-person end-to-end dry run. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| README.md and deployment/product docs link to docs/ownership-and-handover.md. | MANUAL | Requires model/human judgment; no embedded run:/grep: check. |
| run: pytest tests/test_ownership_handover_doc.py | PASS | exit 0; output: ============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /usr/bin/python3 |
