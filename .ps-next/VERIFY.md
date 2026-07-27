# Verification Report

STATUS: PASS

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| `rvv-miniputt scrape-llm --club Jar` prints an explicit browser-enabled warning and mentions the terminal-only recovery commands. | PASS | Covered by `tests/test_rvv_cli_portability.py::test_scrape_llm_cli_prints_browser_tool_guidance_for_browser_only_source` (`browser-verktøy`, `browser_worker`, `recovery-targets`, `recovery-inject`). |
| `rvv-miniputt scrape-llm --club Holmen` prints a deterministic `scrape` recommendation instead of browser-tool guidance. | PASS | Covered by `tests/test_rvv_cli_portability.py::test_scrape_llm_cli_points_holmen_to_deterministic_scrape` (`deterministisk skraper`, `rvv-miniputt scrape --club "Holmen"`, no `browser-worker`). |
| The docs and skill notes update to show `recovery-targets` and `recovery-inject` as the fallback for plain terminal sessions. | PASS | Updated `.claude/commands/rvv-miniputt/scrape-llm.md`, `.claude/commands/rvv-miniputt/run.md`, and `.agents/skills/rvv/SKILL.md`; verified by `tests/test_rvv_skill_boundary.py` and `tests/test_source_health.py`. |
