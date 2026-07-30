# Plan: Club-controlled ownership and handover guide
**Goal:** Document the operational ownership inventory, least-privilege role model, annual access review, and emergency handover procedure needed to move RVV Miniputt operations away from personal accounts.
**Created:** 2026-07-30
**Intent:** GitHub issue #46 highlights a bus-factor risk: code portability is not enough if registrations, publishing, credentials, and recovery depend on one maintainer's personal accounts.

## Tasks
- [x] Add the ownership inventory and handover document
  - Files: docs/ownership-and-handover.md
  - Approach: Create a practical operations document from issue #46 covering critical dependencies, desired club-owned owners, backup owners, role permissions, managed secret storage/rotation, renewal/recovery procedures, removal/automation opportunities, annual review, emergency recovery, and a second-person dry-run checklist. Mark actual external account migration steps as MANUAL where they require club/admin action.
- [ ] Link the handover guide from operator-facing docs
  - Files: README.md, docs/rvv-miniputt-deployment-architecture.md, docs/ai-operator-product-direction.md
  - Approach: Add concise links from existing operator/deployment documentation so volunteers can find the ownership and recovery guidance without changing RVV Miniputt scheduling behavior.
- [ ] Add documentation coverage checks
  - Files: tests/test_ownership_handover_doc.py
  - Approach: Add pytest coverage that verifies the guide exists and contains the required inventory, roles, managed secrets, annual review, emergency recovery, and dry-run sections so future edits do not remove the handover-critical content.

## Notes
- Source: GitHub issue #46, "[P1] Move operational ownership and recovery to club-controlled accounts".
- External account moves, GitHub organization transfer, Microsoft 365 ownership changes, WordPress/Spond admin changes, and credential rotation need authorized club administrators; implement documented procedures and checklists, not live external changes.
- Preserve the existing untracked file `Årshjul for aktiviteter.xlsx`; it is unrelated user work.

## Acceptance Criteria
- [ ] docs/ownership-and-handover.md contains a critical ownership inventory covering GitHub/Pages, Microsoft Forms, SharePoint/List/Excel, Power Automate, Spond, WordPress, calendar credentials, domains/DNS/analytics/notifications, and release signing/notarization identities.
- [ ] docs/ownership-and-handover.md must contain an operator-role matrix that maps least-privilege permissions across GitHub, Microsoft 365, WordPress, and Spond.
- [ ] docs/ownership-and-handover.md documents managed secret storage, rotation, annual review, emergency recovery, and a second-person end-to-end dry run.
- [ ] README.md and deployment/product docs link to docs/ownership-and-handover.md.
- [ ] run: pytest tests/test_ownership_handover_doc.py

## Log

### 2026-07-30 — Add the ownership inventory and handover document
**Done:** Added docs/ownership-and-handover.md with ownership principles, critical dependency inventory, role matrix, managed secrets policy, handover procedure, annual access review, emergency recovery, second-person dry run, and private operations-record template.
**Rationale:** Issue #46 requires moving operational ownership away from personal accounts, but external account transfers are manual; the repository can make the procedure explicit and auditable.
**Findings:** External migrations require authorized club/admin action, so the document marks those steps as MANUAL and avoids committing private account details.
**Files:** docs/ownership-and-handover.md (new); .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
