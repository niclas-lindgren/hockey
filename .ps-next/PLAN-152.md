# Plan: Harness-driven semantic config validation after Stage 1
**Goal:** After Stage 1 runs, the harness reads .pipeline/stage1_config.json plus input.xlsx (via load_effective_config) and uses its own LLM reasoning to flag semantic issues such as more tournaments than available weekends.
**Created:** 2026-06-18
**Intent:** Move semantic config checks out of pipeline code and into the harness skill so organizers get plain-language warnings before Stage 2 runs, without adding Python validation logic.
**Backlog-ref:** 152

## Tasks
- [x] Expanded the Stage 1 block in SKILL.md to instruct the harness to run checkpoint_printer and load_effective_config after Stage 1, documenting all fields relevant to semantic checks. — 2026-06-18
  - Files: .agents/skills/rvv/SKILL.md
  - Approach: Expand the existing "Stage 1 — Config" block in the "Claude Code: stage-by-stage orchestration" section to instruct the harness to run `python3 -m tournament_scheduler.cli.checkpoint_printer stage1` and then run `python3 -c "from tournament_scheduler.pipeline.stage1_config import load_effective_config; import json, pprint; pprint.pprint(load_effective_config('.pipeline'))"` to obtain the merged config (teams, start_date, end_date, age_groups, parallel_games, target_tournament_count) before performing semantic checks.

- [x] Added '## Semantic validation (Stage 1)' section to SKILL.md with a 5-step checklist: count available weekends, count teams per age group, estimate teams per tournament, compute required tournaments, and flag overcommitment. — 2026-06-18
  - Files: .agents/skills/rvv/SKILL.md
  - Approach: Add a new "## Semantic validation (Stage 1)" section in SKILL.md with a step-by-step reasoning checklist: count available weekends between start_date and end_date, compute required tournaments per age group from target_tournament_count × number-of-teams ÷ teams-per-tournament, and instruct the harness to flag when required tournaments exceed available weekends per age group.

- [x] Added two more reasoning steps to the semantic validation section: parallel_games feasibility (flag if parallel_games > distinct clubs per age group) and minimum team count (flag if fewer than 2 teams in an age group). — 2026-06-18
  - Files: .agents/skills/rvv/SKILL.md
  - Approach: Within the same "## Semantic validation (Stage 1)" section, add a check that parallel_games for each age group is ≤ the number of distinct clubs in that age group, and that each age group has at least 2 teams — both expressed as explicit reasoning steps the LLM should perform before advancing to Stage 2.

- [ ] Add harness check for age groups with zero teams
  - Files: .agents/skills/rvv/SKILL.md
  - Approach: Add a reasoning step in the semantic-validation section that lists the age groups from the effective config and verifies each one has at least one team in the `teams` array; flag any age group declared in `age_groups` but absent from team records as a semantic error.

- [ ] Add harness escalation path for semantic failures — block Stage 2 advance
  - Files: .agents/skills/rvv/SKILL.md
  - Approach: Document that when any semantic check fails the harness should print a Norwegian-language summary of each issue (e.g. "Aldergruppe JU10: 24 turneringer kreves men bare 18 helger tilgjengelig") and stop before running Stage 2, instructing the user to update input.xlsx and re-run Stage 1.

## Notes
No pipeline Python code changes needed. All logic lives in the SKILL.md instructions that guide the harness (Claude/Codex/OpenCode) after it invokes the Stage 1 CLI. The fields start_date, end_date, age_groups, parallel_games are not present in .pipeline/stage1_config.json — they must be read from input.xlsx via load_effective_config() before semantic reasoning can happen.

## Acceptance Criteria
- [ ] The SKILL.md "Claude Code: stage-by-stage orchestration" section contains explicit instructions to call load_effective_config after Stage 1 and read start_date, end_date, age_groups, and parallel_games from the merged result.
- [ ] The SKILL.md has a dedicated semantic-validation section that lists at least three observable checks the harness must run (weekend count, parallel_games feasibility, zero-team age groups).
- [ ] The SKILL.md instructs the harness to print a Norwegian-language error summary and not advance to Stage 2 when any semantic check fails.
- [ ] When a harness following the updated SKILL.md instructions processes a Stage 1 checkpoint where target_tournament_count exceeds available weekends, it reports the discrepancy before proceeding.
- [ ] Running `grep -c "Semantic validation" .agents/skills/rvv/SKILL.md` returns a non-zero count, confirming the new section is present in the skill file.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-18 — Expanded the Stage 1 block in SKILL.md to instruct the harness to run checkpoint_printer and load_effective_config after Stage 1, documenting all fields relevant to semantic checks.
**Rationale:** Straightforward doc addition — the load_effective_config call was already the recommended approach per the plan notes.
**Findings:** SKILL.md Stage 1 block now shows both checkpoint_printer and load_effective_config commands with field descriptions.
LESSONS: none
**Files:** .agents/skills/rvv/SKILL.md (+24/-1)
**Commit:** d4161c4 (hockey)

### 2026-06-18 — Added '## Semantic validation (Stage 1)' section to SKILL.md with a 5-step checklist: count available weekends, count teams per age group, estimate teams per tournament, compute required tournaments, and flag overcommitment.
**Rationale:** none
**Findings:** New section positioned between Stage 1 and Stage 2 orchestration blocks in SKILL.md.
LESSONS: none
**Files:** .agents/skills/rvv/SKILL.md (+12/-0)
**Commit:** 79d7ade (hockey)

### 2026-06-18 — Added two more reasoning steps to the semantic validation section: parallel_games feasibility (flag if parallel_games > distinct clubs per age group) and minimum team count (flag if fewer than 2 teams in an age group).
**Rationale:** none
**Findings:** Both checks appended to the existing semantic validation section as named sub-checks.
LESSONS: none
**Files:** .agents/skills/rvv/SKILL.md (+12/-0)
**Commit:** [pending — fill after commit]
