# Plan: Sanitize dead Pages links in public bundles
**Goal:** Public Pages bundles no longer ship clickable links to files that were intentionally excluded, and the privacy report records the rewrites.
**Created:** 2026-07-26
**Intent:** Close GitHub issue #25 by making the public-bundle sanitizer strip or disable dead links that point at excluded files, then documenting the behavior for operators.

## Tasks
- [x] Rewrite or disable links to excluded bundle files
  - Files: tournament_scheduler/pipeline/pages_bundle.py, tests/test_pages_bundle.py
  - Approach: add a small sanitizer for included text assets that detects `href`/`src` values targeting files excluded from the same bundle, removes or disables those links instead of leaving dead 404s, and records each rewrite in the privacy report; add regression tests for excluded-file links, included-file links, and external links.
- [x] Update operator-facing docs to describe link sanitization
  - Files: docs/ai-operator-roadmap.md, README.md
  - Approach: revise the public-bundle docs to mention that excluded-file references inside included HTML are rewritten/disabled, and note that the privacy report includes those rewrites alongside exclusions, redactions, and blocking findings.

## Notes
Issue source: GitHub #25 (open). The existing sanitizer already blocks secrets, redacts contact info/paths, and rewrites root-absolute links; this change should stay narrowly focused on excluded-file references and the privacy report.

## Acceptance Criteria
- [ ] Publishing a bundle where included HTML links to an excluded file no longer leaves a clickable dead link in the public output.
- [ ] The privacy report records rewritten/disabled excluded-file references with enough detail to explain what changed.
- [ ] Update the operator docs to mention the new dead-link sanitization behavior.
- [ ] The targeted tests pass.

## Log


### 2026-07-26 — Update operator-facing docs to describe link sanitization
**Done:** Documented that excluded-file references inside included HTML are disabled or removed, and that the privacy report records those link rewrites alongside exclusions and redactions.
**Rationale:** The operator-facing guidance now matches the sanitizer behavior implemented in the public Pages bundle.
**Findings:** The README and roadmap wording were kept aligned with the existing Pages sanitizer description and now call out rewritten links explicitly.
**Files:** docs/ai-operator-roadmap.md; README.md
**Commit:** not committed
### 2026-07-26 — Rewrite or disable links to excluded bundle files
**Done:** Added a public-bundle link sanitizer that disables hrefs to excluded files/directories and removes src references instead of leaving dead 404s.
**Rationale:** The sanitizer now prevents public Pages output from shipping clickable dead links while keeping included/external links intact.
**Findings:** The bundle needs a two-pass scan so link rewriting can see the final excluded set, including files rejected later in classification. The privacy report now records rewritten_links entries with target, action, scope, and count.
**Files:** tournament_scheduler/pipeline/pages_bundle.py; tests/test_pages_bundle.py
**Commit:** not committed
