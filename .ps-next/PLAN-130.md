# Plan: Rename _load_json to _load_workbook_config in stage1_helpers

**Goal:** Rename stage1_helpers._load_json to _load_workbook_config and add an alias so all existing call sites continue to work without changes.
**Created:** 2026-06-19
**Intent:** The function name _load_json is a lie — it loads an Excel workbook, not JSON — and even the docstring acknowledges it; renaming it removes the confusion for future developers.
**Backlog-ref:** 130

## Tasks
- [x] Renamed _load_json to _load_workbook_config in stage1_helpers.py, updated the docstring to accurately describe loading an Excel workbook, and added the alias _load_json  _load_workbook_config for backward compatibility. — 2026-06-19
  - Files: tournament_scheduler/pipeline/stage1_helpers.py
  - Approach: Rename the function from `_load_json` to `_load_workbook_config`, update its docstring to accurately describe loading an Excel workbook, and add an alias `_load_json = _load_workbook_config` immediately after the definition to preserve backward compatibility.

- [ ] Update import statement in stage1_config.py to use new function name
  - Files: tournament_scheduler/pipeline/stage1_config.py
  - Approach: Change the import at line 48 from `from .stage1_helpers import _load_json, ...` to `from .stage1_helpers import _load_workbook_config, ...` and update all three call sites (lines 83, 150, 190) from `_load_json(...)` to `_load_workbook_config(...)`.

- [ ] Verify no other modules reference _load_json directly and run tests
  - Files: tournament_scheduler/pipeline/stage1_helpers.py, tournament_scheduler/pipeline/stage1_config.py
  - Approach: Run `rg '_load_json' tournament_scheduler/` to confirm no remaining direct references outside the alias line, then run `pytest` to verify all tests pass.

## Notes
Constraints: none
The alias `_load_json = _load_workbook_config` is added in stage1_helpers.py to protect any external call sites that may reference the old name without needing to be updated.

## Acceptance Criteria
- [ ] The function `_load_json` in tournament_scheduler/pipeline/stage1_helpers.py is replaced with `_load_workbook_config` and the old name is preserved as an alias.
- [ ] Code that calls `_load_json` continues to run without errors and produces the same output as before.
- [ ] Tests pass when importing and using the function under its new name.
- [ ] Importing `_load_workbook_config` from `tournament_scheduler/pipeline/stage1_config.py` works without error and the function runs correctly under its new name.
- [ ] The docstring in `_load_workbook_config` in stage1_helpers.py does not contain the word "json" and does contain a reference to loading an Excel workbook.

## Log
<!-- PS:next appends entries here after each task is executed -->
<!-- Entry format: ### YYYY-MM-DD — [task name] / **Done:** / **Rationale:** / **Findings:** / **Files:** / **Commit:** -->

### 2026-06-19 — Renamed _load_json to _load_workbook_config in stage1_helpers.py, updated the docstring to accurately describe loading an Excel workbook, and added the alias _load_json  _load_workbook_config for backward compatibility.
**Rationale:** Straightforward rename — alias preserves all existing imports in stage1_config.py without any changes to call sites.
**Findings:** All 537 unit tests pass; the alias correctly resolves to the same function object.
LESSONS: none
**Files:** stage1_helpers.py (+8/-3)
**Commit:** [pending — fill after commit]
