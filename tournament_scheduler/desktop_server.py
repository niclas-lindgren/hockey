"""Local desktop backend for the RVV Miniputt app.

This module intentionally uses only the Python standard library so it can be
bundled as a small PyInstaller executable and launched by Electron/Tauri without
requiring users to install Python themselves.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import urlparse

APP_NAME = "RVV Miniputt"
SECRET_KEYS = ("BOOKUP_EMAIL", "BOOKUP_PASSWORD")
LLM_SECRET_KEYS = ("LLM_API_KEY",)

# Whitelist of rvv-miniputt commands that can be run via the generic endpoint.
ALLOWED_COMMANDS = frozenset({
    "status", "calendars", "verdict", "critic", "logs",
    "cancel", "replan", "adjust", "tournament", "auto-adjust",
    "scrape", "recovery-targets", "recovery-inject",
})

# Individual pipeline stages, runnable via their own module entrypoints.
STAGE_MODULES = {
    "stage1": "tournament_scheduler.pipeline.stage1_config",
    "stage2": "tournament_scheduler.pipeline.stage2_scraping",
    "stage3": "tournament_scheduler.pipeline.stage3_planning",
    "stage4": "tournament_scheduler.pipeline.stage4_export",
}

# Checkpoint file names for each stage.
STAGE_CHECKPOINT_FILES = {
    "stage1": "stage1_config.json",
    "stage2": "stage2_scraping.json",
    "stage3": "stage3_planning.json",
    "stage4": "stage4_export.json",
}

DEFAULT_PORT = 8765


def _app_dir() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        base = home / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_path() -> Path:
    return _app_dir() / "settings.json"


def _fallback_secrets_path() -> Path:
    return _app_dir() / "secrets.local.json"


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def _try_keyring():
    try:
        import keyring  # type: ignore

        return keyring
    except Exception:
        return None


def _get_secret(key: str) -> str:
    keyring = _try_keyring()
    if keyring is not None:
        try:
            return keyring.get_password(APP_NAME, key) or ""
        except Exception:
            pass
    return str(_load_json(_fallback_secrets_path(), {}).get(key, ""))


def _set_secret(key: str, value: str) -> None:
    keyring = _try_keyring()
    if keyring is not None:
        try:
            if value:
                keyring.set_password(APP_NAME, key, value)
            else:
                try:
                    keyring.delete_password(APP_NAME, key)
                except Exception:
                    pass
            return
        except Exception:
            pass

    secrets = _load_json(_fallback_secrets_path(), {})
    if value:
        secrets[key] = value
    else:
        secrets.pop(key, None)
    _write_json(_fallback_secrets_path(), secrets)


def _llm_status(settings: dict) -> dict[str, Any]:
    return {
        "label": "",
    }


def _redacted_settings() -> dict[str, Any]:
    settings = _load_json(_settings_path(), {})
    secrets = {
        key: {"configured": bool(_get_secret(key)), "value": ""}
        for key in SECRET_KEYS
    }
    return {
        "settings": settings,
        "secrets": secrets,
        "secrets_backend": "keyring" if _try_keyring() is not None else "local-file-fallback",
        "app_dir": str(_app_dir()),
        "llm": _llm_status(settings),
    }


@dataclass
class RunState:
    running: bool = False
    exit_code: int | None = None
    started_at: float | None = None
    finished_at: float | None = None
    command: list[str] = field(default_factory=list)
    input_path: str = ""
    export_dir: str = ""
    work_dir: str = ""
    run_type: str = "pipeline"  # "pipeline" or "command"
    log_lines: list[str] = field(default_factory=list)
    error: str = ""

    def append(self, line: str) -> None:
        self.log_lines.append(line.rstrip())
        if len(self.log_lines) > 1000:
            self.log_lines = self.log_lines[-1000:]


_STATE = RunState()
_STATE_LOCK = threading.Lock()


def _snapshot() -> dict[str, Any]:
    with _STATE_LOCK:
        return {
            "running": _STATE.running,
            "exit_code": _STATE.exit_code,
            "started_at": _STATE.started_at,
            "finished_at": _STATE.finished_at,
            "command": _STATE.command,
            "input_path": _STATE.input_path,
            "export_dir": _STATE.export_dir,
            "work_dir": _STATE.work_dir,
            "run_type": _STATE.run_type,
            "log_lines": _STATE.log_lines[-300:],
            "error": _STATE.error,
        }


def _cli_args(run_args: list[str]) -> list[str]:
    """Build argv for rvv-miniputt CLI (handles frozen vs normal mode)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "__rvv_cli__"] + run_args
    return [sys.executable, "-m", "tournament_scheduler.cli.rvv_cli"] + run_args


def _module_args(module: str, module_args: list[str]) -> list[str]:
    """Build argv to run a Python module directly (for individual stages)."""
    if getattr(sys, "frozen", False):
        # For frozen builds, stage modules are not available. Fall back to
        # running the full pipeline CLI via rvv_cli.
        return _cli_args([module.replace("tournament_scheduler.pipeline.", "").replace("_", "") + "/"] + module_args)
    return [sys.executable, "-m", module] + module_args


def _run_process(args: list[str], env: dict[str, str]) -> int:
    """Run a subprocess, streaming stdout into _STATE log.

    Returns the exit code. Does NOT set _STATE.running or _STATE.exit_code,
    so the caller should manage those.
    """
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        with _STATE_LOCK:
            _STATE.append(line)
    return process.wait()


def _run_cli(args: list[str], env: dict[str, str]) -> int:
    return _run_process(args, env)


def _secret_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in SECRET_KEYS:
        value = _get_secret(key)
        if value:
            env[key] = value
    return env


# ── LLM client ─────────────────────────────────────────────────────


def _llm_config() -> dict[str, Any]:
    """Load LLM configuration from settings + secrets."""
    settings = _load_json(_settings_path(), {})
    llm = settings.get("llm", {})
    api_key = _get_secret("LLM_API_KEY")
    return {
        "enabled": bool(llm.get("enabled", False)),
        "provider": llm.get("provider", "openai"),
        "endpoint": llm.get("endpoint", "https://api.openai.com/v1"),
        "model": llm.get("model", "gpt-4o"),
        "api_key": api_key,
    }


def _llm_completion(
    messages: list[dict[str, str]],
    llm: dict[str, Any] | None = None,
    timeout: int = 60,
) -> str | None:
    """Call an OpenAI-compatible chat API and return the response text.

    Returns None if LLM is not configured, on error, or on timeout.
    """
    if llm is None:
        llm = _llm_config()
    if not llm.get("enabled") or not llm.get("endpoint"):
        return None

    url = llm["endpoint"].rstrip("/") + "/chat/completions"
    api_key = llm.get("api_key", "")
    model = llm.get("model", "gpt-4o")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body_dict: dict[str, Any] = {
        "messages": messages,
        "temperature": 0,
        "max_tokens": 2000,
    }
    if model:
        body_dict["model"] = model
    body = json.dumps(body_dict).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:500]
        with _STATE_LOCK:
            _STATE.append(f"⚠ LLM-feil: HTTP {exc.code} — {body_text}")
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
        if "timed out" in reason.lower() or isinstance(exc, TimeoutError):
            with _STATE_LOCK:
                _STATE.append(f"⚠ LLM tok for lang tid ({timeout}s). Prøv en raskere modell eller øk tidsrommet.")
        else:
            with _STATE_LOCK:
                _STATE.append(f"⚠ LLM-feil: kunne ikke nå {url} — {reason}")
        return None
    except json.JSONDecodeError as exc:
        with _STATE_LOCK:
            _STATE.append(f"⚠ LLM-feil: ugyldig JSON-svar — {exc}")
        return None
    except Exception as exc:
        with _STATE_LOCK:
            _STATE.append(f"⚠ LLM-feil: {exc}")
        return None


def _llm_validate_teams(
    teams: list[dict[str, Any]],
    known_clubs: list[str],
    llm: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ask the LLM to validate team club names against the registry.

    Returns a list of issues (same shape as _validate_teams_against_registry)
    or an empty list if LLM is not available.
    """
    if llm is None:
        llm = _llm_config()
    if not llm.get("enabled"):
        return []

    # Only send teams with potentially problematic club names
    known_set = set(known_clubs)
    questionable = [t for t in teams if t.get("club", "") not in known_set]
    if not questionable:
        return []

    prompt = (
        "Du er en norsk hockey-planleggingsassistent. "
        "Du får en liste med lag fra en ishockeyklubb, der klubbnavnet "
        "(feltet 'club') ikke finnes i klubbregisteret. "
        f"Gyldige klubber: {', '.join(sorted(known_clubs))}.\n\n"
        "For hvert lag, avgjør:\n"
        "1. Hvilken klubb i registeret laget sannsynligvis tilhører.\n"
        "2. Om laget er et kombinasjonslag (spillere fra flere klubber).\n"
        "3. Hva som bør gjøres: bruk en eksisterende klubb, eller be brukeren rette.\n\n"
        "Svar med JSON: {"
        '"issues": [{"club": "<original club name>", '
        '"suggested_club": "<best match or ''>", '
        '"is_combined_team": true/false, '
        '"explanation_nb": "<kort forklaring på norsk>"}]}\n\n'
        "Lag:\n"
    )
    for t in questionable:
        prompt += f"- club={t.get('club', '?')}, label={t.get('label', '?')}, age={t.get('age_group', '?')}\n"

    response = _llm_completion([
        {"role": "system", "content": "Du svarer kun med gyldig JSON, ingen annen tekst."},
        {"role": "user", "content": prompt},
    ], llm=llm)

    if not response:
        return []

    try:
        result = json.loads(response)
        return result.get("issues", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _llm_assess_verdict(
    verdict_data: dict[str, Any],
    llm: dict[str, Any] | None = None,
) -> str | None:
    """Ask the LLM to produce a short Norwegian assessment of the plan verdict."""
    if llm is None:
        llm = _llm_config()
    if not llm.get("enabled"):
        return None

    tone = verdict_data.get("tone_label", verdict_data.get("tone", "?"))
    pairwise = verdict_data.get("pairwise_matchup_score", "?")
    diversity = verdict_data.get("diversity_score", "?")
    month_balance = verdict_data.get("month_balance_score", "?")
    gate = verdict_data.get("fairness_gate_status", "?")
    gate_score = verdict_data.get("fairness_gate_score", "?")

    prompt = (
        "Du er en norsk hockey-planleggingsassistent. Vurder denne sesongplanen:\n\n"
        f"Tone: {tone}\n"
        f"Parvis-matchup-score: {pairwise}\n"
        f"Diversitetsscore: {diversity}\n"
        f"Månedsbalanse: {month_balance}\n"
        f"Fairness-gate: {gate} (score: {gate_score})\n\n"
        "Gi en kort vurdering på norsk (2-3 setninger). Er planen god nok til å eksportere? "
        "Hvis ikke, hva bør justeres?"
    )

    return _llm_completion([
        {"role": "system", "content": "Du er en hjelpsom norsk ishockey-assistent. Svar konsist på norsk."},
        {"role": "user", "content": prompt},
    ], llm=llm)


def _resolve_paths(payload: dict[str, Any]) -> tuple[str, str, str]:
    settings = _load_json(_settings_path(), {})
    inp = str(payload.get("input_path") or settings.get("input_path", "input.xlsx"))
    exp = str(payload.get("export_dir") or settings.get("export_dir", "export"))
    wd = str(payload.get("work_dir") or settings.get("work_dir", str(_app_dir() / "pipeline-cache")))
    return inp, exp, wd


def _load_checkpoint(stage: str, work_dir: str) -> dict[str, Any] | None:
    """Read a stage checkpoint from disk."""
    fname = STAGE_CHECKPOINT_FILES.get(stage)
    if not fname:
        return None
    path = Path(work_dir) / fname
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _validate_teams_against_registry(checkpoint: dict[str, Any]) -> list[dict[str, Any]]:
    """Check that all team club names exist in the club registry.

    Returns a list of issues: each has "club" (the invalid name),
    "suggestions" (closest matches), and "team" (the full team dict).
    """
    from tournament_scheduler.club_registry import CLUB_REGISTRY

    known = set(CLUB_REGISTRY.keys())
    issues: list[dict[str, Any]] = []

    # Stage 1 checkpoint stores teams under data.teams
    data = checkpoint.get("data", checkpoint)
    teams = data.get("teams", [])
    if not teams:
        return issues

    # Build alias candidates for each team club
    for t in teams:
        club = t.get("club", "")
        if not club:
            continue
        if club in known:
            continue

        # Suggest the closest known club
        suggestions_str = club
        # If the name contains a slash like "Jar/Jutul", split and offer each part
        if "/" in club:
            parts = [p.strip() for p in club.split("/") if p.strip()]
            valid_parts = [p for p in parts if p in known]
            if valid_parts:
                suggestions_str = f" eller ".join(valid_parts)

        issues.append({
            "club": club,
            "suggestions": suggestions_str,
            "team": t,
        })

    return issues


def _count_checkpoint_issues(checkpoint: dict[str, Any] | None) -> int:
    """Count reported issues/warnings in a Stage 3 checkpoint."""
    if not checkpoint:
        return 0
    plan = checkpoint.get("plan", {})
    rules = plan.get("rules_report", []) if isinstance(plan, dict) else []
    return len(rules)


def _checkpoint_summary(stage: str, work_dir: str) -> dict[str, Any]:
    """Produce a human-readable summary of a checkpoint for the frontend."""
    cp = _load_checkpoint(stage, work_dir)
    if cp is None:
        return {"exists": False}

    result: dict[str, Any] = {"exists": True}

    if stage == "stage1":
        teams = cp.get("teams", [])
        result["team_count"] = len(teams)
        result["age_groups"] = list({t.get("age_group", "?") for t in teams})
        result["start_date"] = cp.get("start_date", "")
        result["end_date"] = cp.get("end_date", "")

    elif stage == "stage2":
        sources = cp.get("sources", [])
        blocked = cp.get("blocked", [])
        result["source_count"] = len(sources)
        result["blocked"] = blocked
        result["total_events"] = sum(s.get("event_count", 0) for s in sources)
        result["has_zero_event_sources"] = any(s.get("event_count", 0) == 0 for s in sources)

    elif stage == "stage3":
        plan = cp.get("plan", {})
        if isinstance(plan, dict):
            tournaments = plan.get("tournaments", [])
            result["tournament_count"] = len(tournaments)
            result["rules_issues"] = _count_checkpoint_issues(cp)
            result["pairwise_score"] = plan.get("pairwise_matchup_score", "")
            result["diversity_score"] = plan.get("diversity_score", "")
            result["fairness_gate"] = plan.get("fairness_gate", {})
        else:
            result["tournament_count"] = 0

    elif stage == "stage4":
        files = cp.get("output_files", {})
        result["files"] = list(files.values()) if isinstance(files, dict) else []
        result["errors"] = cp.get("errors", [])

    return result


def _run_stage(stage: str, extra_args: list[str], env: dict[str, str],
               work_dir: str, input_path: str, export_dir: str) -> int:
    """Run a single pipeline stage as a subprocess and return exit code."""
    module = STAGE_MODULES.get(stage)
    if not module:
        return 1

    module_args: list[str] = ["--work-dir", work_dir]
    if stage == "stage1":
        module_args.extend(["--input", input_path])
    elif stage == "stage4":
        module_args.extend(["--export-dir", export_dir])

    module_args.extend(extra_args)

    with _STATE_LOCK:
        _STATE.append(f"")
        _STATE.append(f"─── {stage.upper()} ─────────────────────────────────")
        _STATE.append(f"Kjører: python3 -m {module}")
        _STATE.append(f"")

    if getattr(sys, "frozen", False):
        return 1  # Stages not available individually in frozen build

    args = _module_args(module, module_args)
    return _run_process(args, env)


def _run_verdict(work_dir: str, env: dict[str, str]) -> dict[str, Any]:
    """Run the verdict command and return structured result."""
    result = subprocess.run(
        _cli_args(["verdict", "--work-dir", work_dir]),
        capture_output=True, text=True, env=env, timeout=30,
    )
    out: dict[str, Any] = {"exit_code": result.returncode}
    for line in result.stdout.split("\n"):
        line = line.strip()
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _run_smart(payload: dict[str, Any]) -> None:
    """Full Pi-style pipeline orchestration: stage-by-stage with inspection.

    - Stage 1: config validation
    - Stage 2: deterministic scraping
    - Stage 3: planning with verdict check
    - Auto-adjust loop: up to 3 iterations if verdict is 'rough'
    - Stage 4: export + open
    """
    input_path, export_dir, work_dir = _resolve_paths(payload)
    env = _secret_env()
    max_adjust = int(payload.get("max_adjust_iterations", 3))
    plan_iterations = int(payload.get("plan_iterations", 3))
    allow_missing = bool(payload.get("allow_missing_sources", False))

    with _STATE_LOCK:
        _STATE.running = True
        _STATE.exit_code = None
        _STATE.started_at = time.time()
        _STATE.finished_at = None
        _STATE.run_type = "pipeline"
        _STATE.input_path = input_path
        _STATE.export_dir = export_dir
        _STATE.work_dir = work_dir
        _STATE.log_lines = []
        _STATE.error = ""
        _STATE.append("🏒 RVV Miniputt — Smart kjøring")
        _STATE.append(f"Styres: steg-for-steg med inspeksjon og auto-justering")
        _STATE.append(f"")
        _STATE.append(f"Inndata: {input_path}")
        _STATE.append(f"Arbeidsmappe: {work_dir}")
        _STATE.append(f"Eksport: {export_dir}")
        _STATE.append(f"Plan-iterasjoner: {plan_iterations}")
        _STATE.append(f"Maks justeringer: {max_adjust}")
        _STATE.append(f"")

    try:
        # ── Stage 1: Config ────────────────────────────────────────
        rc1 = _run_stage("stage1", [], env, work_dir, input_path, export_dir)
        cp1 = _checkpoint_summary("stage1", work_dir)
        with _STATE_LOCK:
            _STATE.append(f"")
            if cp1.get("exists"):
                _STATE.append(f"✓ Stage 1: {cp1.get('team_count', '?')} lag, "
                              f"{len(cp1.get('age_groups', []))} aldersgrupper")
            else:
                _STATE.append(f"⚠ Stage 1: ingen checkpoint funnet")
        if rc1 != 0:
            with _STATE_LOCK:
                _STATE.append(f"❌ Stage 1 feilet — avbryter")
            raise RuntimeError("Stage 1 feilet")

        # ── Semantic validation: check teams against club registry ────
        raw_cp1 = _load_checkpoint("stage1", work_dir)
        if raw_cp1:
            club_issues = _validate_teams_against_registry(raw_cp1)
            if club_issues:
                from tournament_scheduler.club_registry import CLUB_REGISTRY as _CR
                llm_cfg = _llm_config()
                llm_issues: list[dict[str, Any]] = []

                # Try LLM-assisted resolution first
                if llm_cfg["enabled"]:
                    with _STATE_LOCK:
                        _STATE.append(f"")
                        _STATE.append(f"🔍 Spør LLM om hjelp med ukjente klubbnavn...")
                    data = raw_cp1.get("data", raw_cp1)
                    teams = data.get("teams", [])
                    llm_issues = _llm_validate_teams(
                        teams, sorted(_CR.keys()), llm=llm_cfg
                    )

                has_llm_fix = False
                for li in llm_issues:
                    suggested = li.get("suggested_club", "")
                    if suggested and suggested in _CR:
                        has_llm_fix = True

                if has_llm_fix:
                    # Apply LLM suggestions
                    data = raw_cp1.get("data", raw_cp1)
                    teams_list = data.get("teams", [])
                    fix_map: dict[str, str] = {}
                    for li in llm_issues:
                        orig = li.get("club", "")
                        suggested = li.get("suggested_club", "")
                        if orig and suggested and suggested in _CR:
                            fix_map[orig] = suggested

                    applied = 0
                    for t in teams_list:
                        club = t.get("club", "")
                        if club in fix_map:
                            t["club"] = fix_map[club]
                            applied += 1

                    if applied:
                        checkpoint_path = Path(work_dir) / STAGE_CHECKPOINT_FILES["stage1"]
                        checkpoint_path.write_text(
                            json.dumps(raw_cp1, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        with _STATE_LOCK:
                            _STATE.append(f"")
                            _STATE.append(f"🤖 LLM rettet {applied} klubbnavn:")
                            for orig, fixed in fix_map.items():
                                _STATE.append(f"  • {orig} → {fixed}")
                            _STATE.append(f"")
                            _STATE.append(f"✓ Fortsetter med rettede klubbnavn")
                else:
                    # No LLM or LLM couldn't help — show diagnostic to user
                    with _STATE_LOCK:
                        _STATE.append(f"")
                        _STATE.append(f"⚠ Ukjente klubbnavn funnet — stopper og venter på deg:")
                        _STATE.append(f"")
                        for issue in club_issues:
                            team = issue["team"]
                            club = issue["club"]
                            label = team.get("label", "?")
                            age = team.get("age_group", "?")
                            _STATE.append(f"  Laget '{label}' ({age}) har klubb='{club}'")

                            if "/" in club:
                                parts = [p.strip() for p in club.split("/") if p.strip()]
                                valid = [p for p in parts if p in _CR]
                                _STATE.append(f"  Dette ser ut som et kombinasjonslag med spillere fra "
                                              f"{' og '.join(parts)}.")
                                _STATE.append(f"  Modellen støtter ikke kombinasjonslag — hvert lag må "
                                              f"tilhøre én klubb.")
                                if valid:
                                    _STATE.append(f"  Hvis laget hovedsakelig hører til {valid[0]}, "
                                                  f"endrer du klubb til '{valid[0]}' i input.xlsx.")
                                _STATE.append(f"  Hvis laget må splittes: opprett to rader i input.xlsx "
                                              f"(én for Jar, én for Jutul).")
                            else:
                                _STATE.append(f"  Ukjent klubb. Gyldige klubber: {', '.join(sorted(_CR.keys()))}")
                            _STATE.append(f"")

                        if llm_cfg["enabled"]:
                            _STATE.append(f"🤖 LLM ble spurt, men kunne ikke foreslå en rettelse.")
                            for li in llm_issues:
                                expl = li.get("explanation_nb", "")
                                if expl:
                                    _STATE.append(f"  {expl}")

                        _STATE.append(f"✋ Åpne input.xlsx, rett Klubb-kolonnen for lagene over, "
                                      f"lagre, og kjør Smart kjør på nytt.")

                    raise RuntimeError(
                        f"{len(club_issues)} ukjent(e) klubbnavn i input.xlsx — "
                        f"kan ikke fortsette før de er rettet"
                    )

        # Re-read checkpoint summary after potential LLM fixes
        cp1 = _checkpoint_summary("stage1", work_dir)

        # ── Stage 2: Scraping ──────────────────────────────────────
        s2_args = ["--non-strict"]
        if allow_missing:
            s2_args.append("--allow-missing-sources")
        rc2 = _run_stage("stage2", s2_args, env, work_dir, input_path, export_dir)
        cp2 = _checkpoint_summary("stage2", work_dir)
        with _STATE_LOCK:
            _STATE.append(f"")
            if cp2.get("exists"):
                _STATE.append(f"✓ Stage 2: {cp2.get('source_count', '?')} kilder, "
                              f"{cp2.get('total_events', '?')} hendelser")
                blocked = cp2.get("blocked", [])
                if blocked:
                    _STATE.append(f"⚠ Blokkerte kilder ({len(blocked)}): "
                                  f"{', '.join(blocked)}")
                    _STATE.append(f"  Disse kalenderne er ikke tilgjengelige for planlegging.")
            else:
                _STATE.append(f"⚠ Stage 2: ingen checkpoint funnet")
        if rc2 != 0:
            with _STATE_LOCK:
                _STATE.append(f"❌ Stage 2 feilet — avbryter")
            raise RuntimeError("Stage 2 feilet")

        # ── Stage 3: Planning ──────────────────────────────────────
        with _STATE_LOCK:
            _STATE.append(f"")
            _STATE.append(f"Kjører planlegger {plan_iterations} gang(er) og velger beste resultat...")
        s3_args = ["--iterations", str(plan_iterations)]
        rc3 = _run_stage("stage3", s3_args, env, work_dir, input_path, export_dir)
        if rc3 != 0:
            with _STATE_LOCK:
                _STATE.append(f"❌ Stage 3 feilet — avbryter")
            raise RuntimeError("Stage 3 feilet")

        # ── Verdict + auto-adjust loop ─────────────────────────────
        for adj_i in range(max_adjust + 1):
            verdict = _run_verdict(work_dir, env)
            tone = verdict.get("tone", "unknown")
            tone_label = verdict.get("tone_label", tone.upper())
            gate_status = verdict.get("fairness_gate_status", "pass")

            with _STATE_LOCK:
                _STATE.append(f"")
                _STATE.append(f"─── VURDERING (iterasjon {adj_i + 1}) ────────────")
                _STATE.append(f"Tone: {tone_label}  |  Fairness: {gate_status}")
                _STATE.append(f"Matchup: {verdict.get('pairwise_matchup_score', '?')}  |  "
                              f"Diversity: {verdict.get('diversity_score', '?')}")
                _STATE.append(f"")

            # LLM assessment (if configured)
            llm_assessment = _llm_assess_verdict(verdict)
            if llm_assessment:
                with _STATE_LOCK:
                    for line in llm_assessment.strip().split("\n"):
                        _STATE.append(f"  💬 {line.strip()}")
                    _STATE.append(f"")

            # If tone is strong or mixed — good enough, move to export
            if tone == "strong" or gate_status == "pass":
                with _STATE_LOCK:
                    _STATE.append(f"✓ Godkjent — går videre til eksport")
                break

            # If tone is rough and we have iterations left, auto-adjust
            if tone == "rough" and adj_i < max_adjust:
                with _STATE_LOCK:
                    _STATE.append(f"⚠ Rå — forbedringsrunde {adj_i + 1}/{max_adjust}...")
                adj_args = ["auto-adjust", "--work-dir", work_dir,
                            "--export-dir", export_dir,
                            "--max-iterations", "1",
                            "--no-timestamped-export"]
                adj_rc = _run_process(_cli_args(adj_args), env)
                if adj_rc != 0:
                    with _STATE_LOCK:
                        _STATE.append(f"  Auto-justering feilet (exit code {adj_rc})")
                        break
                else:
                    with _STATE_LOCK:
                        _STATE.append(f"  ✓ Justeringer brukt — re-evaluerer...")
                # Do NOT re-run Stage 3. Auto-adjust already wrote the fixed
                # plan checkpoint and re-exported. The next loop iteration
                # re-checks the verdict on the adjusted plan.
            else:
                # Either strong (already handled) or out of iterations
                break

        # ── Stage 4: Export ────────────────────────────────────────
        rc4 = _run_stage("stage4", ["--no-timestamped-export"], env, work_dir, input_path, export_dir)
        cp4 = _checkpoint_summary("stage4", work_dir)
        with _STATE_LOCK:
            _STATE.append(f"")
            if cp4.get("exists"):
                files = cp4.get("files", [])
                _STATE.append(f"✓ Stage 4: {len(files)} fil(er) eksportert")
                for f in files[:5]:
                    _STATE.append(f"  → {f}")
                if len(files) > 5:
                    _STATE.append(f"  ...og {len(files) - 5} til")
            else:
                _STATE.append(f"⚠ Stage 4: ingen checkpoint funnet")

        with _STATE_LOCK:
            _STATE.append(f"")
            _STATE.append(f"✅ Smart kjøring fullført")
            _STATE.exit_code = 0

    except Exception as exc:
        with _STATE_LOCK:
            _STATE.exit_code = 1
            _STATE.error = str(exc)
            _STATE.append(f"FEIL: {exc}")
    finally:
        with _STATE_LOCK:
            _STATE.running = False
            _STATE.finished_at = time.time()


class Handler(BaseHTTPRequestHandler):
    server_version = "RVVMiniputtDesktop/0.1"

    def _send(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        parts = path.rstrip("/").split("/")

        if path == "/health":
            self._send(200, {"ok": True, "app_dir": str(_app_dir())})
        elif path == "/settings":
            self._send(200, _redacted_settings())
        elif path == "/run/status":
            self._send(200, _snapshot())
        elif path == "/commands":
            self._send(200, {"commands": sorted(ALLOWED_COMMANDS)})
        elif path == "/stage/status":
            settings = _load_json(_settings_path(), {})
            wd = settings.get("work_dir", str(_app_dir() / "pipeline-cache"))
            stages: list[dict[str, Any]] = []
            for stage in ["stage1", "stage2", "stage3", "stage4"]:
                cp = _checkpoint_summary(stage, wd)
                cp["name"] = stage
                stages.append(cp)
            self._send(200, {"stages": stages, "work_dir": wd})
        elif len(parts) == 3 and parts[1] == "checkpoint":
            stage = parts[2]
            if stage in STAGE_CHECKPOINT_FILES:
                settings = _load_json(_settings_path(), {})
                wd = settings.get("work_dir", str(_app_dir() / "pipeline-cache"))
                cp = _load_checkpoint(stage, wd)
                if cp is not None:
                    self._send(200, cp)
                else:
                    self._send(404, {"error": f"Ingen checkpoint funnet for {stage}"})
            else:
                self._send(400, {"error": f"Ukjent stage: {stage}"})
        elif path == "/llm/status":
            cfg = _llm_config()
            self._send(200, {
                "enabled": cfg["enabled"],
                "provider": cfg["provider"],
                "model": cfg["model"],
                "endpoint": cfg["endpoint"],
                "key_configured": bool(cfg["api_key"]),
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._body()
            if path == "/settings":
                all_settings = dict(payload.get("settings") or {})
                # Save regular settings (llm config lives under settings["llm"])
                _write_json(_settings_path(), all_settings)
                for key, value in dict(payload.get("secrets") or {}).items():
                    if key in SECRET_KEYS or key in LLM_SECRET_KEYS:
                        _set_secret(key, str(value or ""))
                self._send(200, _redacted_settings())
            elif path == "/run":
                with _STATE_LOCK:
                    if _STATE.running:
                        self._send(409, {"error": "En kjøring pågår allerede."})
                        return
                threading.Thread(target=_run_pipeline, args=(payload,), daemon=True).start()
                self._send(202, {"started": True})
            elif path == "/open":
                target = str(payload.get("path") or "")
                if not target:
                    self._send(400, {"error": "Mangler sti."})
                    return
                webbrowser.open(Path(target).expanduser().resolve().as_uri())
                self._send(200, {"opened": target})
            elif path == "/run/command":
                self._handle_run_command(payload)
            elif path == "/run/command/result":
                self._handle_run_command_result(payload)
            elif path == "/run/smart":
                with _STATE_LOCK:
                    if _STATE.running:
                        self._send(409, {"error": "En kjøring pågår allerede."})
                        return
                threading.Thread(target=_run_smart, args=(payload,), daemon=True).start()
                self._send(202, {"started": True, "mode": "smart"})
            elif path == "/llm/test":
                self._handle_llm_test(payload)
            elif path == "/llm/validate-teams":
                self._send(200, self._handle_llm_validate_teams(payload))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:
            self._send(500, {"error": str(exc)})

    # ------------------------------------------------------------------
    # Generic command dispatch
    # ------------------------------------------------------------------

    def _validate_command(self, payload: dict[str, Any]) -> str | None:
        cmd = str(payload.get("command", "")).strip()
        if not cmd or cmd not in ALLOWED_COMMANDS:
            return None
        return cmd

    def _command_args(self, cmd: str, payload: dict[str, Any]) -> list[str]:
        """Build argument list, injecting --work-dir from stored settings."""
        args = payload.get("args", [])
        extra = payload.get("extra", {})

        work_dir_cmds = frozenset({
            "status", "verdict", "critic", "calendars", "cancel",
            "replan", "adjust", "tournament", "auto-adjust",
            "scrape", "recovery-targets", "recovery-inject",
            "logs",
        })

        result: list[str] = [cmd]

        # Auto-inject --work-dir from settings if applicable
        if cmd in work_dir_cmds and "--work-dir" not in args:
            settings = _load_json(_settings_path(), {})
            wd = extra.get("work_dir") or settings.get(
                "work_dir",
                str(_app_dir() / "pipeline-cache"),
            )
            result.extend(["--work-dir", wd])

        result.extend(args)
        return result

    def _handle_run_command(self, payload: dict[str, Any]) -> None:
        cmd = self._validate_command(payload)
        if cmd is None:
            self._send(400, {
                "error": f"Ukjent kommando. Tillatte: {', '.join(sorted(ALLOWED_COMMANDS))}"
            })
            return

        with _STATE_LOCK:
            if _STATE.running:
                self._send(409, {
                    "error": "En kjøring pågår allerede. Vent til den er ferdig."
                })
                return

        cmd_args = self._command_args(cmd, payload)
        threading.Thread(
            target=_run_generic_command, args=(cmd_args,), daemon=True
        ).start()
        self._send(202, {"started": True, "command": cmd})

    def _handle_run_command_result(self, payload: dict[str, Any]) -> None:
        cmd = self._validate_command(payload)
        if cmd is None:
            self._send(400, {
                "error": f"Ukjent kommando. Tillatte: {', '.join(sorted(ALLOWED_COMMANDS))}"
            })
            return

        cmd_args = self._command_args(cmd, payload)

        env = os.environ.copy()
        for key in SECRET_KEYS:
            value = _get_secret(key)
            if value:
                env[key] = value

        try:
            result = subprocess.run(
                _cli_args(cmd_args),
                capture_output=True,
                text=True,
                env=env,
                timeout=30.0,
            )
            self._send(200, {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": cmd,
            })
        except subprocess.TimeoutExpired:
            self._send(408, {
                "error": f"Kommandoen '{cmd}' tok for lang tid. Bruk /run/command for asynkron kjøring."
            })
        except Exception as exc:
            self._send(500, {"error": str(exc)})

    # ------------------------------------------------------------------
    # LLM handlers
    # ------------------------------------------------------------------

    def _handle_llm_test(self, payload: dict[str, Any]) -> None:
        """Test the LLM connection with a short prompt."""
        cfg = _llm_config()
        if not cfg["enabled"] or not cfg["endpoint"]:
            self._send(400, {"error": "LLM er ikke konfigurert. Åpne Innstillinger og sett opp tilkobling."})
            return

        with _STATE_LOCK:
            _STATE.append(f"")
            _STATE.append(f"🧪 Tester KI-tilkobling: {cfg['endpoint']}")
            _STATE.append(f"   Modell: {cfg['model'] or '(standard/LM Studio lastet modell)'}")
            _STATE.append(f"   Nøkkel: {'•' * 8 if cfg['api_key'] else 'ingen'}")

        response = _llm_completion([
            {"role": "user", "content": "Svar med 'OK'."},
        ], llm=cfg, timeout=60)

        if response:
            with _STATE_LOCK:
                _STATE.append(f"✅ Tilkobling OK: {response[:100]}")
            self._send(200, {"ok": True, "response": response[:200]})
        else:
            # Grab the last error line from the log
            with _STATE_LOCK:
                error_lines = [l for l in _STATE.log_lines[-20:] if "⚠ LLM" in l]
                detail = error_lines[-1] if error_lines else "Ukjent feil"
            self._send(502, {"error": f"Kunne ikke nå LLM. {detail}"})

    def _handle_llm_validate_teams(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate team club names using the LLM."""
        from tournament_scheduler.club_registry import CLUB_REGISTRY

        teams = payload.get("teams", [])
        if not teams:
            return {"issues": []}

        cfg = _llm_config()
        if not cfg["enabled"]:
            return {"issues": []}

        known = sorted(CLUB_REGISTRY.keys())
        issues = _llm_validate_teams(teams, known, llm=cfg)
        return {"issues": issues}

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep packaged app output clean; run logs are exposed through /run/status.
        return


def _run_generic_command(cmd_args: list[str]) -> None:
    """Run an arbitrary rvv-miniputt command, streaming output into _STATE.

    cmd_args is the argument list after the module/cli name, e.g.
    ["verdict", "--work-dir", ".pipeline"]
    """
    run_args = _cli_args(cmd_args)

    env = os.environ.copy()
    for key in SECRET_KEYS:
        value = _get_secret(key)
        if value:
            env[key] = value

    with _STATE_LOCK:
        _STATE.running = True
        _STATE.exit_code = None
        _STATE.started_at = time.time()
        _STATE.finished_at = None
        _STATE.command = run_args
        _STATE.input_path = ""
        _STATE.export_dir = ""
        _STATE.work_dir = ""
        _STATE.log_lines = []
        _STATE.error = ""
        _STATE.run_type = "command"
        _STATE.append(f"🏒 rvv-miniputt {' '.join(cmd_args)}")
        _STATE.append(f"Python: {sys.executable}")
        _STATE.append("")

    try:
        exit_code = _run_cli(run_args, env)
        with _STATE_LOCK:
            _STATE.exit_code = exit_code
    except Exception as exc:
        with _STATE_LOCK:
            _STATE.exit_code = 1
            _STATE.error = str(exc)
            _STATE.append(f"FEIL: {exc}")
    finally:
        with _STATE_LOCK:
            _STATE.running = False
            _STATE.finished_at = time.time()


def _rvv_cli_main(argv: list[str]) -> int:
    from tournament_scheduler.cli.rvv_cli import main as cli_main

    return int(cli_main(argv) or 0)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "__rvv_cli__":
        return _rvv_cli_main(argv[1:])

    parser = argparse.ArgumentParser(description="RVV Miniputt local desktop backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"RVV Miniputt desktop backend listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
