# Plan: GitHub issue #35 locked Python dependencies
**Goal:** Implement GitHub issue #35 so CI and documented operator installs use a committed, exact Python dependency lock instead of broad runtime constraints.
**Created:** 2026-07-30
**Intent:** Make installs reproducible for CI, release validation, and routine RVV Miniputt operation while keeping `pyproject.toml` as the direct dependency declaration.

## Tasks
- [x] Add locked Python dependency workflow artifacts
  - Files: requirements.lock, requirements.txt, scripts/refresh-python-lock.sh
  - Approach: Use pip-tools as the documented lock workflow; keep `requirements.txt` as broad direct-runtime declarations for maintainers, add a hash-checked `requirements.lock` generated from `pyproject.toml` with the `test` extra, and add a refresh script that fails if pip-tools is unavailable.
- [x] Install and validate from the lock in operator/CI paths
  - Files: scripts/install.sh, scripts/package-desktop-backend.sh, scripts/package-desktop-backend.ps1, .github/workflows/ci.yml, Makefile, scripts/check
  - Approach: Install `requirements.lock` with `--require-hashes`, install the project editable with `--no-deps`, update CI cache keys and install steps, make desktop packaging install locked runtime before locked desktop tools, and add a `scripts/check dependency-lock` phase that detects stale lock output.
- [ ] Document and test the deterministic dependency workflow
  - Files: README.md, docs/ci.md, tests/test_dependency_lock_workflow.py
  - Approach: Document operator installs, lock refresh commands, platform/desktop optional handling, and CI expectations; add static tests proving CI/install/check use `requirements.lock`, refresh command exists, and docs mention the locked workflow.

## Notes
Selected GitHub issue #35 because higher-numbered open GitHub issues #46, #45, and #39 already appear completed in `.ps-next/HISTORY.md` on 2026-07-30. The lock should not make Make or CI duplicate verification logic; it should preserve existing CLI/test behavior while changing dependency resolution to the committed lock.

## Acceptance Criteria
- [ ] `requirements.lock` contains exact resolved versions and hashes.
- [ ] `grep -R "requirements.lock" .github/workflows/ci.yml scripts/install.sh scripts/package-desktop-backend.sh scripts/package-desktop-backend.ps1 docs/ci.md README.md` shows CI, install, packaging, and docs use the locked dependency set.
- [ ] `scripts/check dependency-lock` passes.
- [ ] `python3 -m pytest --no-cov -v tests/test_dependency_lock_workflow.py` passes.
- [ ] `python3 -m pytest --no-cov -q tests/test_dependency_lock_workflow.py tests/test_makefile_operator_interface.py` passes.

## Log


### 2026-07-30 — Install and validate from the lock in operator/CI paths
**Done:** Updated operator install, desktop packaging, CI jobs, Makefile, and scripts/check so supported install/check paths consume requirements.lock with hash checking and install the local project without dependency resolution.
**Rationale:** Installing the committed lock first makes CI/operator dependency resolution deterministic; editable installs with --no-deps preserve local source wiring without letting pip re-resolve broad pyproject constraints.
**Findings:** Expanded the lock refresh from only the test extra to all pyproject extras so desktop packaging tools (keyring/PyInstaller) are locked too; scripts/check dependency-lock uses a temporary pinned pip-tools environment and compares pre/post lock content instead of requiring a clean git tree.
**Files:** .github/workflows/ci.yml, Makefile, requirements.lock, scripts/check, scripts/install.sh, scripts/package-desktop-backend.ps1, scripts/package-desktop-backend.sh, scripts/refresh-python-lock.sh, .ps-next/PLAN.md
**Commit:** not committed
### 2026-07-30 — Add locked Python dependency workflow artifacts
**Done:** Added a committed hash-checked Python dependency lock generated from pyproject.toml with the test extra, plus a refresh script for pip-tools and a requirements.txt note that locked installs should use requirements.lock.
**Rationale:** pip-tools keeps pyproject.toml as the direct dependency source while producing a deterministic pip-compatible lock file with hashes for CI/operator installs.
**Findings:** pip-tools 7.6.0 currently fails with pip 26.2 internals, so the documented temporary refresh environment should keep pip below 26 until pip-tools catches up.
**Files:** requirements.lock (new), scripts/refresh-python-lock.sh (new), requirements.txt, .ps-next/PLAN.md
**Commit:** not committed
<!-- pi-next appends entries here after each task -->
