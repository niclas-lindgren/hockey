# Plan: SharePoint import workflow via GitHub issues (issue #49 follow-up)
**Goal:** Create an issue-triggered GitHub Actions workflow that imports SharePoint files into the canonical inputs/ directory, then let the existing path-triggered workflows handle generation and publishing.
**Created:** 2026-07-31
**Intent:** The issue was updated to use a GitHub-issue-based bridge instead of Power Automate directly committing via API. Power Automate creates a machine-readable issue with a temporary download URL; GitHub Actions downloads, validates, and commits the file.
**Backlog-ref:** 49 (GitHub)

## Tasks
- [x] Create .github/workflows/sharepoint-import.yml
  - Files: .github/workflows/sharepoint-import.yml
  - Approach: Trigger on `issues: types: [opened]`. Job-level `if` gates on `github.event.issue.title == 'sharepoint-sync: activities'`. Parse key=value body lines, validate required fields (source, target_path, download_url), reject duplicates/malformed/unexpected. Download file following redirects, verify XLSX magic bytes (`PK\x03\x04`), validate via Python, compare SHA-256 with existing canonical, commit only when changed, comment on issue, close on success/unchanged, leave open on failure. Use `permissions: contents: write, issues: write`. Concurrency group for import serialization. Never log/expose download_url.

- [x] Update docs/power-automate-github-sync.md for issue-based contract
  - Files: docs/power-automate-github-sync.md
  - Approach: Rewrite to document the issue-based bridge: SharePoint trigger with DriveId+DriveItemId, debounce, temporary sharing link, exact issue title and body contract, issue lifecycle, how to handle deleted/recreated files, manual recovery. Remove the old direct-PAT sections. Keep the registration flow section (still relevant). Document that Power Automate only needs the built-in GitHub connector (no premium HTTP actions).

- [x] Extend tests for the import workflow
  - Files: tests/test_github_actions_operator_workflows.py
  - Approach: Add import workflow to WORKFLOW_FILES, add tests verifying: issues trigger, title gating, body parsing, required fields, redirect following, XLSX validation, unchanged detection, bot comment/close, permission boundaries, concurrency, download URL sanitization.

## Notes
- The existing activity-publish.yml and registration-publish.yml are unchanged — they remain the path-triggered generation/publishing workflows downstream of the import.
- Power Automate uses `DriveId` + `DriveItemId` for stable file identification, not filename or path.
- The import workflow never exposes the temporary download URL in logs, artifacts, or comments.
- The flow: SharePoint → Power Automate creates issue → import workflow commits canonical file → path trigger fires activity-publish → Pages updated.

## Acceptance Criteria
- [ ] Run the import workflow by creating an issue titled exactly `sharepoint-sync: activities`.
- [ ] Validate the issue body contract and return errors for missing, duplicate, and unexpected keys.
- [ ] Download the file and verify it contains valid XLSX magic bytes; reject HTML, login pages, and empty responses.
- [ ] Show that invalid downloads never modify repository inputs.
- [ ] Show that an unchanged workbook creates no commit and closes the issue with an explanatory comment.
- [ ] Show that a changed valid workbook is committed to `inputs/activities/activities.xlsx`.
- [ ] Run the workflow and verify it comments on and closes successful trigger issues.
- [ ] Show that failed trigger issues remain open with a useful diagnostic comment.
- [ ] Show that download URLs are not exposed in logs or comments.
- [ ] Run concurrent imports and verify they are serialized safely.
- [ ] `docs/power-automate-github-sync.md` exists and contains the issue-based contract and recovery sections.
- [ ] Run tests that cover valid import, malformed body, invalid download, unchanged file, and changed file.

## Log



### 2026-07-31 — Extend tests for the import workflow
**Done:** Extended tests with 8 new test functions for sharepoint-import.yml: issues trigger, title gating, body contract validation, XLSX download/validation, URL sanitization, conditional commit, failure handling, and concurrency group.
**Rationale:** Import workflow is an infrastructure bridge, not a pipeline entrypoint. It validates and commits; downstream workflows handle generation.
**Findings:** Import workflow doesn't delegate to scripts/rvv-miniputt but uses Python inline scripts with openpyxl and requests — this is acceptable since the import step is about file transfer, not pipeline execution. The generation step still delegates via the downstream path-triggered workflow.
**Files:** tests/test_github_actions_operator_workflows.py (extended)
**Commit:** not committed
### 2026-07-31 — Update docs/power-automate-github-sync.md for issue-based contract
**Done:** Rewrote docs/power-automate-github-sync.md to document the issue-based bridge architecture: Power Automate creates issues with download URLs, GitHub Actions imports. Includes DriveId+DriveItemId filtering, issue contract specification, lifecycle, deleted/recreated file handling, and updated security model.
**Rationale:** The issue-based bridge is simpler for volunteers: Power Automate only creates issues (no file transfer, no API auth), GitHub Actions handles the rest.
**Findings:** Power Automate no longer needs PAT or premium HTTP actions — the built-in GitHub connector handles issue creation via OAuth. Import workflow uses its own concurrency group separate from routine-publish.
**Files:** docs/power-automate-github-sync.md (rewritten)
**Commit:** not committed
### 2026-07-31 — Create .github/workflows/sharepoint-import.yml
**Done:** Created .github/workflows/sharepoint-import.yml: issue-triggered (title-gated), body parsing with required/optional/unknown key validation, download with redirect following and XLSX magic byte verification, SHA-256 comparison, conditional commit, bot comment+close on success/unchanged, diagnostic comment on failure.
**Rationale:** Clean separation: import workflow only handles download→validate→commit, then the existing path-triggered activity-publish.yml handles regeneration→publish.
**Findings:** YAML parsing is fragile with inline --body strings containing markdown (**) and backticks. Solved with heredoc --body-file pattern. The issue's colon in the title requires YAML double-quoting on the if: field.
**Files:** .github/workflows/sharepoint-import.yml (new)
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
