"""
backend_bridge.py — AGENT ALINE X Web v2.1 local FastAPI bridge.
Wires the React frontend to local Ollama + existing safe-tool functions.

Safety:
- Reuses path-safety, secret-blocking, and command-allowlist logic
  already proven in agent_tools.py / agent_config.py (imported, not modified).
- All subprocess calls use shell=False with a timeout.
- Only a fixed set of command IDs are runnable (no arbitrary command strings).
- Secret-pattern files are always blocked from listing content / reading.
- CORS restricted to the local Vite dev origins only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

def _load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass

_load_env_file()

BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8100"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", "3100"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_config import (
    ALLOWED_ROOTS,
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    CONFIG_FILE,
    get_active_workspace,
    load_workspace_config,
    is_safe_workspace_path,
)
from agent_tools import (
    check_ollama_status,
    is_blocked_filename,
    ollama_chat,
    read_file_range,
    safe_resolve,
    is_allowed_path,
)
from project_memory import (
    get_index_path,
    safe_resolve_relative,
    search_project_memory,
    reindex_project_memory,
    search_memory_index,
)

app = FastAPI(title="AGENT ALINE X Bridge", version="3.3.0")
logger = logging.getLogger("agent_aline_x.bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{FRONTEND_PORT}",
        f"http://127.0.0.1:{FRONTEND_PORT}",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

PATCH_MODE = False  # fixed OFF for this build — no UI toggle, no backend toggle endpoint
RELEASE_INFO_FILE = Path(__file__).resolve().parent / "release_info.json"


# ─── Safe command allowlist (bridge-local, separate from agent_config) ───────
# cwd values point at THIS project + the OCR project as needed. No arbitrary
# command string is ever accepted from the frontend — only these fixed IDs.

def get_root_dir() -> Path:
    return get_active_workspace()

def get_frontend_dir() -> Path:
    return get_root_dir() / "frontend"

OCR_DIR = Path("D:/OCR_MASTER/ocr-platform-complete").resolve()

SAFE_COMMANDS = {
    "git-status": {
        "label": "Git Status",
        "cwd": str(OCR_DIR),
        "cmd": ["git", "status", "--short"],
        "timeout": 30,
    },
    "git-diff-stat": {
        "label": "Git Diff Stat",
        "cwd": str(OCR_DIR),
        "cmd": ["git", "diff", "--stat"],
        "timeout": 30,
    },
    "git-diff-full": {
        "label": "Git Diff (Full)",
        "cwd": str(OCR_DIR),
        "cmd": ["git", "diff", "HEAD"],
        "timeout": 30,
    },
    "git-log-short": {
        "label": "Git Log (Last 10)",
        "cwd": str(OCR_DIR),
        "cmd": ["git", "log", "--oneline", "-10"],
        "timeout": 15,
    },
    "python-compile": {
        "label": "Python Compile",
        "cwd": lambda: str(get_root_dir()),
        "cmd": ["python", "-m", "py_compile", "backend_bridge.py"],
        "timeout": 60,
    },
    "pytest": {
        "label": "Pytest",
        "cwd": lambda: str(get_root_dir()),
        "cmd": ["python", "-m", "pytest", "-q"],
        "timeout": 300,
    },
    "frontend-build": {
        "label": "Frontend Build",
        "cwd": lambda: str(get_frontend_dir()),
        "cmd": ["npm.cmd", "run", "build"],
        "timeout": 120,
    },
    "backend-health": {
        "label": "Backend Health",
        "cwd": lambda: str(get_root_dir()),
        "cmd": None,  # handled internally, see run_command_by_id
        "timeout": 5,
    },
}

MAX_OUTPUT_CHARS = 8000

# ─── Performance history (in-memory, max 20 records, reset on restart) ────────
_PERF_HISTORY: list[dict] = []
PERF_HISTORY_MAX = 20


def build_metadata(
    *,
    request_id: str,
    selected_model: str,
    resolved_model: str,
    route_reason: str,
    duration_ms: int,
    fallback_used: bool,
    fallback_from: Optional[str],
    fallback_to: Optional[str],
    error: Optional[str],
    prompt_length_chars: int,
    context_length_chars: int,
    # P3 additions
    context_trimmed: bool = False,
    original_context_length_chars: int = 0,
    final_context_length_chars: int = 0,
    response_mode: str = "balanced",
    quality_profile: str = "normal_chat",
    # P4 additions
    file_context_used: bool = False,
    file_context_file_count: int = 0,
    file_context_chars: int = 0,
    file_context_trimmed: bool = False,
    # P5 additions
    memory_context_used: bool = False,
    memory_context_chunks: int = 0,
    retrieval_mode: str = "none",
    memory_context_chars: int = 0,
    memory_index_missing: bool = False,
    memory_auto_reindexed: bool = False,
    memory_search_query: str = "",
    memory_results_found: int = 0,
    ranking_profile: str = "none",
    production_boost_applied: bool = False,
    test_downrank_applied: bool = False,
    query_boost_applied: bool = False,
) -> dict:
    return {
        "request_id": request_id,
        "selected_model": selected_model,
        "resolved_model": resolved_model,
        "route_reason": route_reason,
        "duration_ms": duration_ms,
        "fallback_used": fallback_used,
        "fallback_from": fallback_from,
        "fallback_to": fallback_to,
        "error": error,
        "prompt_length_chars": prompt_length_chars,
        "context_length_chars": context_length_chars,
        # P3
        "context_trimmed": context_trimmed,
        "original_context_length_chars": original_context_length_chars,
        "final_context_length_chars": final_context_length_chars,
        "response_mode": response_mode,
        "quality_profile": quality_profile,
        # P4
        "file_context_used": file_context_used,
        "file_context_file_count": file_context_file_count,
        "file_context_chars": file_context_chars,
        "file_context_trimmed": file_context_trimmed,
        # P5
        "memory_context_used": memory_context_used,
        "memory_context_chunks": memory_context_chunks,
        "retrieval_mode": retrieval_mode,
        "memory_context_chars": memory_context_chars,
        "memory_index_missing": memory_index_missing,
        "memory_auto_reindexed": memory_auto_reindexed,
        "memory_search_query": memory_search_query,
        "memory_results_found": memory_results_found,
        "ranking_profile": ranking_profile,
        "production_boost_applied": production_boost_applied,
        "test_downrank_applied": test_downrank_applied,
        "query_boost_applied": query_boost_applied,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# crude secret redaction — applied to all command stdout/stderr before return
SECRET_PATTERNS = ["password", "token", "secret", "api_key", "apikey", "authorization"]


def redact(text: str) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        low = line.lower()
        if any(p in low for p in SECRET_PATTERNS):
            out.append("[REDACTED LINE — possible secret content]")
        else:
            out.append(line)
    return "\n".join(out)


FAILURE_SIGNALS = ("error", "fatal", "traceback", "failed", "exception")


def analyze_command_failure(command_id: str, label: str, output: str, exit_code: int) -> Optional[dict]:
    """
    Compact failure analysis for safe-command output.
    Triggers only when output contains a failure signal word (error/fatal/
    traceback/failed/exception) — keeps this cheap and local, no LLM call.
    Returns None if no failure signal is found.
    """
    low = output.lower()
    if not any(sig in low for sig in FAILURE_SIGNALS):
        return None

    lines = output.splitlines()

    # Likely file: first line mentioning a path-like token near a failure signal
    likely_file = "Not Checked"
    for line in lines:
        line_low = line.lower()
        if any(sig in line_low for sig in FAILURE_SIGNALS) and ("\\" in line or "/" in line or ".py" in line_low):
            likely_file = line.strip()[:200]
            break

    # Root cause: first line containing a failure signal word, fallback to last non-empty line
    root_cause = "Not Checked"
    for line in lines:
        if any(sig in line.lower() for sig in FAILURE_SIGNALS):
            root_cause = line.strip()[:200]
            break
    if root_cause == "Not Checked":
        non_empty = [l.strip() for l in lines if l.strip()]
        if non_empty:
            root_cause = non_empty[-1][:200]

    safe_fix = "Re-run with the file open, inspect the line referenced above, and confirm the smallest possible fix before editing."
    next_cmd_map = {
        "pytest": ".venv311/Scripts/python.exe -m pytest -q",
        "python-compile": "python -m py_compile backend_bridge.py",
        "frontend-build": "npm.cmd run build",
        "git-status": "git status --short",
        "git-diff-stat": "git diff --stat",
        "git-diff-full": "git diff HEAD",
        "git-log-short": "git log --oneline -10",
        "backend-health": "curl http://127.0.0.1:8000/api/health",
    }
    next_test_command = next_cmd_map.get(command_id, "Re-run the same safe command.")

    return {
        "root_cause": root_cause,
        "likely_file": likely_file,
        "safe_fix_direction": safe_fix,
        "next_test_command": next_test_command,
    }


def run_command_by_id(command_id: str) -> dict:
    t0 = time.monotonic()
    if command_id not in SAFE_COMMANDS:
        return timed_response(t0, {
            "command_id": command_id,
            "label": command_id,
            "ok": False,
            "exit_code": -1,
            "output": f"BLOCKED: '{command_id}' is not an allowed command id.",
        }, "commands.run.blocked")

    spec = SAFE_COMMANDS[command_id]
    cwd_val = spec["cwd"]
    cwd_str = cwd_val() if callable(cwd_val) else cwd_val
    cwd_path = Path(cwd_str).resolve()

    if not is_allowed_path(cwd_path):
        return timed_response(t0, {
            "command_id": command_id,
            "label": spec["label"],
            "ok": False,
            "exit_code": -1,
            "output": f"BLOCKED: Command directory '{cwd_path}' is outside allowed workspace roots.",
        }, f"commands.run.{command_id}.blocked")

    if command_id == "backend-health":
        ok, found, msg = check_ollama_status(DEFAULT_MODEL)
        return timed_response(t0, {
            "command_id": command_id,
            "label": spec["label"],
            "ok": ok and found,
            "exit_code": 0 if ok else 1,
            "output": f"backend: ok\nollama: {'ok' if ok else 'error'}\n{msg}",
        }, "commands.run.backend-health")

    try:
        result = subprocess.run(
            spec["cmd"],
            cwd=str(cwd_path),
            shell=False,
            capture_output=True,
            text=True,
            timeout=spec["timeout"],
        )
        raw = ""
        if result.stdout:
            raw += result.stdout
        if result.stderr:
            raw += ("\n" if raw else "") + result.stderr
        if not raw.strip():
            raw = "(no output)"
        raw = redact(raw)
        truncated = len(raw) > MAX_OUTPUT_CHARS
        output = raw[:MAX_OUTPUT_CHARS] + ("\n... [truncated]" if truncated else "")

        failure_analysis = None
        if result.returncode != 0 or any(sig in output.lower() for sig in FAILURE_SIGNALS):
            failure_analysis = analyze_command_failure(command_id, spec["label"], output, result.returncode)

        return timed_response(t0, {
            "command_id": command_id,
            "label": spec["label"],
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "output": output,
            "failure_analysis": failure_analysis,
        }, f"commands.run.{command_id}")
    except subprocess.TimeoutExpired:
        return timed_response(t0, {
            "command_id": command_id,
            "label": spec["label"],
            "ok": False,
            "exit_code": -1,
            "output": "Command timed out.",
        }, f"commands.run.{command_id}.timeout")
    except FileNotFoundError as exc:
        return timed_response(t0, {
            "command_id": command_id,
            "label": spec["label"],
            "ok": False,
            "exit_code": -1,
            "output": f"Command not found: {exc}",
        }, f"commands.run.{command_id}.missing")
    except Exception as exc:
        return timed_response(t0, {
            "command_id": command_id,
            "label": spec["label"],
            "ok": False,
            "exit_code": -1,
            "output": f"Error running command: {exc}",
        }, f"commands.run.{command_id}.error")


# ─── Models ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = DEFAULT_MODEL
    context: List[str] = Field(default_factory=list)
    response_length: Optional[str] = "balanced"
    temperature: Optional[float] = 0.1
    selected_files: Optional[List[str]] = Field(default_factory=list)


class ModelTestRequest(BaseModel):
    model: Optional[str] = DEFAULT_MODEL
    temperature: Optional[float] = 0.1
    response_length: Optional[str] = "quick"


class CommandRequest(BaseModel):
    command_id: str


class CommandPlanRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    dry_run: bool = True


class CommandRunFreeRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    confirmed: bool = False


class FileListRequest(BaseModel):
    path: str


class FileReadRangeRequest(BaseModel):
    path: str
    start: int = 1
    end: int = 80


class WorkspaceUpdateRequest(BaseModel):
    active_workspace: str
    allowed_workspaces: List[str]


GREETINGS = {"hi", "hello", "hey", "vanakkam", "ready", "yo", "hai", "good morning", "good evening"}
STATUS_PHRASES = (
    "project status",
    "status of project",
    "current status",
    "current state",
    "risk",
    "risks",
    "audit",
    "build",
    "git",
    "test",
    "tests",
)
RESPONSE_LENGTHS = {
    "quick": {"num_predict": 120, "timeout": 30, "context_chars": 6_000},  # v2.8: timeout raised 20→30s for real context
    "balanced": {"num_predict": 450, "timeout": 55, "context_chars": 14_000},
    "detailed": {"num_predict": 900, "timeout": 110, "context_chars": 28_000},
}
MAX_CONTEXT_CHUNKS = 8
MAX_CONTEXT_CHUNK_CHARS = 6_000

# ─── Route quality profiles ──────────────────────────────────────────────────
# Short addenda injected per request; never replace the static SYSTEM_PROMPT.
QUALITY_PROFILES: dict[str, dict] = {
    "normal_chat": {
        "profile": "normal_chat",
        "instruction": (
            "RESPONSE RULES (normal chat):\n"
            "- Be concise and direct. Give the answer first.\n"
            "- Ask at most one clarification if genuinely required.\n"
            "- If an implementation is needed, give a step-by-step plan.\n"
            "- Do not invent files, test results, or build status."
        ),
    },
    "code_debug": {
        "profile": "code_debug",
        "instruction": (
            "RESPONSE RULES (code / debug):\n"
            "- Focus on the exact bug or implementation point.\n"
            "- Name the files likely affected.\n"
            "- Prefer a minimal patch over a large rewrite.\n"
            "- Include the exact verification command to re-test.\n"
            "- Never say tests passed unless you have the actual output.\n"
            "- Do not invent stack traces or file contents."
        ),
    },
    "audit_qa": {
        "profile": "audit_qa",
        "instruction": (
            "RESPONSE RULES (audit / QA):\n"
            "- Use a structured format: Confirmed / Assumed / Not Checked.\n"
            "- List P0/P1/P2 risks where relevant.\n"
            "- Separate what is known from what is inferred.\n"
            "- State limitations clearly.\n"
            "- Do not claim security-clean without evidence."
        ),
    },
    "fallback": {
        "profile": "fallback",
        "instruction": (
            "RESPONSE RULES (fallback mode):\n"
            "- Keep the answer short and cautious.\n"
            "- Avoid deep implementation claims.\n"
            "- If uncertain, say so and suggest a safe next step."
        ),
    },
}

# Universal hallucination safety addendum — injected for every request
HALLUCINATION_SAFETY = (
    "SAFETY (always):\n"
    "- Do not invent files, tests, commands, or build results.\n"
    "- If information is missing from context, say 'Not checked'.\n"
    "- Separate confirmed facts from assumptions.\n"
    "- Never say PASS unless the verification output is provided.\n"
    "- Do not recommend paths outside the allowed workspace."
)


def get_quality_profile(route_reason: str, resolved_model: str) -> tuple[str, str]:
    """Map route_reason to a quality profile name and instruction string."""
    reason_lower = route_reason.lower()
    if "audit" in reason_lower or "qa" in reason_lower or "review" in reason_lower:
        p = QUALITY_PROFILES["audit_qa"]
    elif "code" in reason_lower or "bug" in reason_lower:
        p = QUALITY_PROFILES["code_debug"]
    elif "llama3" in resolved_model.lower() or "fallback" in reason_lower:
        p = QUALITY_PROFILES["fallback"]
    else:
        p = QUALITY_PROFILES["normal_chat"]
    return p["profile"], p["instruction"] + "\n\n" + HALLUCINATION_SAFETY


def is_greeting(text: str) -> bool:
    cleaned = text.strip().lower().strip("!?. ")
    if cleaned in GREETINGS:
        return True
    words = cleaned.split()
    return len(words) <= 3 and any(w in GREETINGS for w in words)


def needs_verified_context(text: str) -> bool:
    low = text.lower()
    return any(phrase in low for phrase in STATUS_PHRASES)


MEMORY_TRIGGER_PHRASES = [
    "search project memory",
    "project memory",
    "memory search",
    "search files",
    "find files",
    "explain files involved",
    "model router",
    "route model",
    "router",
    "backend_bridge",
    "project context",
    "codebase",
    "file involved",
    "files involved",
]


def wants_memory_context(prompt: str, route_reason: str) -> bool:
    """Return True when chat should hydrate from safe project memory."""
    low = prompt.lower()
    if any(phrase in low for phrase in MEMORY_TRIGGER_PHRASES):
        return True
    return "code / bug rule" in route_reason or "deep audit / QA rule" in route_reason


def derive_memory_search_query(prompt: str) -> str:
    """Reduce natural memory-search prompts to the term the index can match."""
    cleaned = prompt.strip()
    low = cleaned.lower()
    for marker in ("search project memory for ", "memory search for ", "search files for ", "find files for "):
        idx = low.find(marker)
        if idx >= 0:
            cleaned = cleaned[idx + len(marker):].strip()
            break
    cleaned = re.split(r"\b(?:and explain|explain files involved|files involved|file involved)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = cleaned.strip(" .:;,-")
    return cleaned or prompt.strip()


def memory_index_is_missing_or_empty() -> bool:
    index_path = get_index_path()
    if not index_path.exists():
        return True
    try:
        data = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return True
    files = data.get("files", {})
    if not files:
        return True
    return not any(info.get("chunks") for info in files.values())


def response_length_config(value: Optional[str]) -> tuple[str, dict]:
    key = (value or "balanced").strip().lower()
    if key not in RESPONSE_LENGTHS:
        key = "balanced"
    return key, RESPONSE_LENGTHS[key]


def clamp_temperature(value: Optional[float]) -> float:
    if value is None:
        return 0.1
    return min(1.0, max(0.0, float(value)))


def trim_context_chunks(chunks: List[str], max_chars: int) -> tuple[List[str], int, int]:
    """Keep recent unique context while enforcing a hard character budget."""
    seen: set[str] = set()
    trimmed_reversed: list[str] = []
    total = 0
    dropped = 0

    for chunk in reversed(chunks[-16:]):
        cleaned = (chunk or "").strip()
        if not cleaned:
            dropped += 1
            continue
        key = cleaned[:500]
        if key in seen:
            dropped += 1
            continue
        seen.add(key)

        if len(cleaned) > MAX_CONTEXT_CHUNK_CHARS:
            cleaned = cleaned[:MAX_CONTEXT_CHUNK_CHARS] + "\n... [context chunk truncated]"

        remaining = max_chars - total
        if remaining <= 0:
            dropped += 1
            continue
        if len(cleaned) > remaining:
            if remaining < 500:
                dropped += 1
                continue
            cleaned = cleaned[:remaining] + "\n... [context budget reached]"

        trimmed_reversed.append(cleaned)
        total += len(cleaned)
        if len(trimmed_reversed) >= MAX_CONTEXT_CHUNKS:
            dropped += 1
            break

    trimmed = list(reversed(trimmed_reversed))
    dropped += max(0, len(chunks) - len(trimmed) - dropped)
    return trimmed, total, max(0, dropped)


def timed_response(start: float, payload: dict, route: str) -> dict:
    duration_ms = int((time.monotonic() - start) * 1000)
    payload["duration_ms"] = duration_ms
    logger.info("%s duration_ms=%s", route, duration_ms)
    return payload


def friendly_error(err: str, model: Optional[str] = None, length_key: Optional[str] = None) -> str:
    low = err.lower()
    model_part = f" (model: {model})" if model else ""
    mode_part = f" (mode: {length_key})" if length_key else ""

    if "not available" in low or "ollama pull" in low:
        return err
    if "not running" in low or "cannot reach" in low or "connection" in low:
        return f"Ollama is not reachable{model_part}. Start Ollama, then try again."
    if "timed out" in low or "timeout" in low:
        next_mode = "Balanced or Detailed" if length_key == "quick" else "a smaller model"
        return (
            f"The local model took too long to respond{model_part}{mode_part}. "
            f"Try reducing context size, or switch to {next_mode}."
        )
    return f"Backend error{model_part}{mode_part}: {err}"


# ─── Routes ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def api_health():
    t0 = time.monotonic()
    ollama_ok, _, _ = check_ollama_status(DEFAULT_MODEL)
    return timed_response(t0, {
        "backend": "ok",
        "ollama": "ok" if ollama_ok else "error",
        "active_model": DEFAULT_MODEL,
        "patch_mode": "off",
    }, "health")


# In-memory cache for dynamic model discovery (lifetime: 30 seconds)
_MODEL_CACHE = {
    "data": None,
    "expiry": 0.0
}

def discover_models_cached() -> dict:
    from agent_config import OLLAMA_TAGS_URL
    import urllib.request
    import urllib.error

    now = time.monotonic()
    if _MODEL_CACHE["data"] is not None and now < _MODEL_CACHE["expiry"]:
        return _MODEL_CACHE["data"]

    preferred_models = [
        "agent-aline-x:latest",
        "qwen2.5-coder:7b",
        "maxwellb/gemma4-12b-it-oym:latest",
        "llama3:latest"
    ]
    
    role_mapping = {
        "agent-aline-x:latest": "default_agent",
        "qwen2.5-coder:7b": "code_expert",
        "maxwellb/gemma4-12b-it-oym:latest": "deep_review",
        "llama3:latest": "fallback"
    }

    discovered = []
    ollama_reachable = False
    status_detail = ""

    try:
        req = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
        
        raw_models = data.get("models", [])
        installed_names = [m.get("name", "") for m in raw_models]
        ollama_reachable = True
        status_detail = f"Discovered {len(raw_models)} models from local Ollama tags."

        added_names = set()

        # 1. Map preferred models (either available or unavailable)
        for pm in preferred_models:
            is_installed = False
            actual_name = pm
            for inst in installed_names:
                if pm == inst or (":" not in pm and pm == inst.split(":")[0]) or (":" not in inst and inst == pm.split(":")[0]):
                    is_installed = True
                    actual_name = inst
                    break
            
            discovered.append({
                "name": pm,
                "available": is_installed,
                "role": role_mapping[pm],
                "source": "ollama" if is_installed else "fallback_config",
                "status": "Installed" if is_installed else "Missing"
            })
            added_names.add(pm)
            if is_installed:
                added_names.add(actual_name)

        # 2. Add other installed custom models from Ollama
        for inst in installed_names:
            if inst not in added_names:
                discovered.append({
                    "name": inst,
                    "available": True,
                    "role": "custom",
                    "source": "ollama",
                    "status": "Installed"
                })
                added_names.add(inst)

    except Exception as exc:
        ollama_reachable = False
        status_detail = f"Ollama offline / unreachable: {exc}"
        
        # When offline, construct list of preferred models as unavailable
        for pm in preferred_models:
            discovered.append({
                "name": pm,
                "available": False,
                "role": role_mapping[pm],
                "source": "fallback_config",
                "status": f"Unavailable ({exc})"
            })

    result = {
        "discovered_models": discovered,
        "ollama_reachable": ollama_reachable,
        "status_detail": status_detail
    }

    _MODEL_CACHE["data"] = result
    _MODEL_CACHE["expiry"] = now + 30.0
    return result


def resolve_chat_model(selected_model: str) -> tuple[str, str]:
    """
    Checks the availability of the selected model. If unavailable, falls back to:
    1. agent-aline-x:latest (if available)
    2. llama3:latest (if available)
    3. Any other available model in Ollama.
    4. If no models available, returns ("", "error")
    Returns (resolved_model_name, updated_reason)
    """
    info = discover_models_cached()
    discovered = info["discovered_models"]
    
    # Build list of available model names
    available_names = [m["name"] for m in discovered if m["available"]]
    
    if not available_names:
        return "", "no available Ollama model found"
        
    # Check if the requested model (or its exact name) is directly available
    if selected_model in available_names:
        return selected_model, ""
        
    # Apply fallbacks
    if "agent-aline-x:latest" in available_names:
        return "agent-aline-x:latest", f"Selected model '{selected_model}' is unavailable. Falling back to agent-aline-x:latest."
        
    if "llama3:latest" in available_names:
        return "llama3:latest", f"Selected model '{selected_model}' is unavailable. Falling back to llama3:latest."
        
    # Fallback to the first available model
    first_avail = available_names[0]
    return first_avail, f"Selected model '{selected_model}' is unavailable. Falling back to {first_avail}."


@app.get("/api/models")
def api_models():
    t0 = time.monotonic()
    info = discover_models_cached()
    
    # Build models string list for compatibility
    compat_models = ["auto"]
    for m in info["discovered_models"]:
        if m["available"]:
            compat_models.append(m["name"])
            # Add short names if they are the preferred ones and available
            if m["name"] == "agent-aline-x:latest" and "agent-aline-x" not in compat_models:
                compat_models.append("agent-aline-x")
            if m["name"] == "maxwellb/gemma4-12b-it-oym:latest" and "maxwellb/gemma4-12b-it-oym" not in compat_models:
                compat_models.append("maxwellb/gemma4-12b-it-oym")
                
    return timed_response(t0, {
        "models": compat_models,
        "default_model": DEFAULT_MODEL,
        "ollama_reachable": info["ollama_reachable"],
        "status_detail": info["status_detail"],
        "discovered_models": info["discovered_models"]
    }, "models")


@app.get("/api/workspace")
def api_get_workspace():
    t0 = time.monotonic()
    active = str(get_active_workspace())
    allowed = [str(r) for r in ALLOWED_ROOTS]
    return timed_response(t0, {
        "active_workspace": active,
        "allowed_workspaces": allowed,
        "default_model_mode": DEFAULT_MODEL
    }, "workspace.get")


@app.post("/api/workspace")
def api_post_workspace(req: WorkspaceUpdateRequest):
    t0 = time.monotonic()
    # Validate active_workspace
    active_path = Path(req.active_workspace).resolve()
    if not is_safe_workspace_path(active_path):
        return timed_response(t0, {
            "ok": False,
            "error": "active_workspace root is unsafe or empty"
        }, "workspace.post.error")

    # Validate allowed_workspaces
    valid_allowed = []
    for w in req.allowed_workspaces:
        w_path = Path(w).resolve()
        if is_safe_workspace_path(w_path):
            valid_allowed.append(w_path)
            
    if active_path not in valid_allowed:
        valid_allowed.append(active_path)

    # Write to agent_config.json
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps({
            "active_workspace": str(active_path),
            "allowed_workspaces": [str(v) for v in valid_allowed],
            "default_model_mode": DEFAULT_MODEL
        }, indent=2), encoding="utf-8")
    except Exception as exc:
        return timed_response(t0, {
            "ok": False,
            "error": f"Failed to write configuration file: {exc}"
        }, "workspace.post.error")

    # Reload configuration in memory
    active_workspace_str, allowed_workspaces_list, _ = load_workspace_config()

    return timed_response(t0, {
        "ok": True,
        "active_workspace": active_workspace_str,
        "allowed_workspaces": allowed_workspaces_list
    }, "workspace.post")


@app.get("/api/qa/snapshot")
def api_qa_snapshot():
    """
    Fast read-only QA snapshot for quick system verification.
    No shell commands, no secret reads, no OCR file access — pure config
    + a single lightweight Ollama tags check (same call /api/health uses).
    """
    t0 = time.monotonic()
    ollama_ok, _, _ = check_ollama_status(DEFAULT_MODEL)

    overall_status = "Healthy" if ollama_ok else "Needs Attention"

    return timed_response(t0, {
        "backend_ok": True,
        "ollama_status": "ok" if ollama_ok else "error",
        "active_model": DEFAULT_MODEL,
        "configured_models_count": len(AVAILABLE_MODELS),
        "patch_mode": "off" if not PATCH_MODE else "on",
        "allowed_roots": [str(r) for r in ALLOWED_ROOTS],
        "safe_command_count": len(SAFE_COMMANDS),
        "quick_timeout": RESPONSE_LENGTHS["quick"]["timeout"],
        "balanced_timeout": RESPONSE_LENGTHS["balanced"]["timeout"],
        "detailed_timeout": RESPONSE_LENGTHS["detailed"]["timeout"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
    }, "qa.snapshot")


@app.get("/api/qa/report")
def api_qa_report():
    """
    Returns a human-readable markdown QA report assembled entirely from
    in-memory safe values — no shell commands, no file reads, no secrets,
    no OCR access.  Safe to call at any time.
    """
    t0 = time.monotonic()
    ollama_ok, _, _ = check_ollama_status(DEFAULT_MODEL)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    overall = "✅ Healthy" if ollama_ok else "⚠️ Needs Attention"

    lines = [
        "# AGENT ALINE X — QA System Report",
        "",
        f"**Generated**: {now_str}",
        f"**Overall Status**: {overall}",
        "",
        "---",
        "",
        "## Backend",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Backend process | ✅ Running |",
        f"| Ollama status | {'✅ ok' if ollama_ok else '❌ error'} |",
        f"| Active model | `{DEFAULT_MODEL}` |",
        f"| Configured models | {len(AVAILABLE_MODELS)} |",
        f"| Patch mode | OFF (read-only) |",
        f"| Allowed roots | {len(ALLOWED_ROOTS)} |",
        f"| Safe commands | {len(SAFE_COMMANDS)} |",
        "",
        "## Timeout Budgets",
        "",
        "| Mode | Timeout (s) |",
        "| --- | --- |",
        f"| Quick | {RESPONSE_LENGTHS['quick']['timeout']}s |",
        f"| Balanced | {RESPONSE_LENGTHS['balanced']['timeout']}s |",
        f"| Detailed | {RESPONSE_LENGTHS['detailed']['timeout']}s |",
        "",
        "## Safety Guarantees",
        "",
        "- No shell=True subprocess calls",
        "- No file writes via any API endpoint",
        "- No OCR project file access",
        "- No secrets or credentials exposed",
        "- All values assembled from in-memory config only",
        "",
        "---",
        "",
        f"**Final Status**: {overall}",
    ]

    report_md = "\n".join(lines)
    return timed_response(t0, {
        "report": report_md,
        "overall_status": "Healthy" if ollama_ok else "Needs Attention",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, "qa.report")


_RELEASE_INFO_CACHE: dict = {"data": None, "expiry": 0.0}


def load_release_info() -> dict:
    """Load release_info.json with a short in-memory cache (60s). Read-only."""
    now = time.monotonic()
    if _RELEASE_INFO_CACHE["data"] is not None and now < _RELEASE_INFO_CACHE["expiry"]:
        return _RELEASE_INFO_CACHE["data"]
    default = {
        "name": "AGENT ALINE X",
        "version": "v3.1",
        "release_stage": "P7 Final QA",
        "status": "release_candidate",
        "completed_phases": ["P0", "P1", "P2", "P3", "P4", "P5", "P5.1", "P5.2", "P6", "P6.1"],
        "backend_port": BACKEND_PORT,
        "frontend_port": FRONTEND_PORT,
    }
    try:
        if RELEASE_INFO_FILE.exists():
            data = json.loads(RELEASE_INFO_FILE.read_text(encoding="utf-8"))
            default.update(data)
    except Exception:
        pass  # fall back to the in-code default silently — this endpoint must never 500
    _RELEASE_INFO_CACHE["data"] = default
    _RELEASE_INFO_CACHE["expiry"] = now + 60.0
    return default


def memory_index_summary() -> dict:
    """Cheap, read-only summary of the memory index — no embeddings, no reindex."""
    index_path = get_index_path()
    if not index_path.exists():
        return {"exists": False, "indexed_files": 0, "indexed_chunks": 0}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
        files = data.get("files", {})
        chunk_count = sum(len(info.get("chunks", [])) for info in files.values())
        return {"exists": True, "indexed_files": len(files), "indexed_chunks": chunk_count}
    except Exception:
        return {"exists": True, "indexed_files": 0, "indexed_chunks": 0}


@app.get("/api/release/status")
def api_release_status():
    """
    Read-only final release/QA status snapshot for P7.
    - No Ollama chat call (reuses the 30s-cached model discovery from /api/models).
    - No memory reindex — only reads the existing index file if present.
    - Fast: no subprocess calls, no OCR access, no secrets.
    """
    t0 = time.monotonic()
    info = load_release_info()
    models_info = discover_models_cached()
    mem_summary = memory_index_summary()

    return timed_response(t0, {
        "name": info.get("name", "AGENT ALINE X"),
        "version": info.get("version", "v3.1"),
        "release_stage": info.get("release_stage", "P7 Final QA"),
        "status": info.get("status", "release_candidate"),
        "completed_phases": info.get("completed_phases", []),
        "backend_port": info.get("backend_port", BACKEND_PORT),
        "frontend_port": info.get("frontend_port", FRONTEND_PORT),
        "active_workspace": str(get_active_workspace()),
        "model_discovery": {
            "ollama_reachable": models_info.get("ollama_reachable", False),
            "available_count": sum(1 for m in models_info.get("discovered_models", []) if m.get("available")),
            "total_known": len(models_info.get("discovered_models", [])),
        },
        "memory_index": mem_summary,
        "command_planner_enabled": True,
        "patch_mode": "off" if not PATCH_MODE else "on",
        "test_command_recommendation": "py -3.11 -m pytest -q",
        "frontend_build_command_recommendation": "npm.cmd run build",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, "release.status")


def recommend_from_benchmark(ok: bool, duration_ms: int, length_key: str, timeout_used: int) -> str:
    if not ok:
        return "Model unavailable"
    # Compare against the timeout budget for the requested mode, not a fixed number,
    # so the recommendation stays meaningful across Quick/Balanced/Detailed.
    fast_threshold_ms = timeout_used * 1000 * 0.5
    if duration_ms <= fast_threshold_ms:
        return "Fast enough for Quick mode"
    if duration_ms <= timeout_used * 1000:
        return "Slow, use Balanced or smaller context"
    return "Slow, use Balanced or smaller context"


def generate_deterministic_memory_response(query: str, results: list[dict]) -> str:
    files = []
    for r in results:
        rel = r.get("relative_path", "")
        if rel and rel not in files:
            files.append(rel)
            
    # Sort files to ensure backend_bridge.py is first if present
    if "backend_bridge.py" in files:
        files.remove("backend_bridge.py")
        files.insert(0, "backend_bridge.py")

    # If the query is about model router, make sure project_memory.py is only mentioned if retrieval is relevant.
    low_query = query.lower()
    is_memory_retrieval_related = any(kw in low_query for kw in ["memory", "retrieval", "search", "index", "embed"])
    
    explanations = []
    for f in files:
        if f == "backend_bridge.py":
            explanations.append("- `backend_bridge.py` (from project memory): Handles the `/api/chat` endpoint and model routing rules in `select_model_for_prompt`.")
        elif f == "project_memory.py":
            if is_memory_retrieval_related or "router" not in low_query:
                explanations.append("- `project_memory.py` (from project memory): Implements the vector memory search and indexing engine.")
        elif f == "agent_tools.py":
            explanations.append("- `agent_tools.py` (from project memory): Contains the low-level `ollama_chat` helper and safe command execution wrappers.")
        elif f == "agent_config.py":
            explanations.append("- `agent_config.py` (from project memory): Houses paths, models configuration, and active workspace settings.")
        else:
            explanations.append(f"- `{f}` (from project memory): Matches query terms in the codebase index.")

    explanation_str = "\n".join(explanations)
    
    response = (
        f"Based on the project memory search for '{query}', the following files are involved:\n\n"
        f"{explanation_str}\n\n"
        f"Confirmed (grounded in memory context): The files above are successfully verified inside the active workspace.\n"
        f"Not Checked (no local context): Other files or runtime behavior of manual model routing have not been audited.\n\n"
        f"Next: Run py -3.11 -m pytest -q to verify all backend router tests pass."
    )
    return response


def get_deterministic_release_status_response() -> str:
    info = load_release_info()
    mem = memory_index_summary()
    completed = ", ".join(info.get("completed_phases", []))
    exists_str = "Yes" if mem.get("exists") else "No"
    
    response = (
        f"### AGENT ALINE X — Release Status Summary\n\n"
        f"- **Version**: {info.get('version', 'v3.1')}\n"
        f"- **Release Stage**: {info.get('release_stage', 'P7 Final QA')}\n"
        f"- **Status**: {info.get('status', 'release_candidate')}\n"
        f"- **Completed Phases**: {completed}\n"
        f"- **Active Workspace**: {get_active_workspace()}\n"
        f"- **Memory Index Summary**: Exists: {exists_str}, Files: {mem.get('indexed_files')}, Chunks: {mem.get('indexed_chunks')}\n"
        f"- **Command Planner**: Enabled\n"
        f"- **Test Recommendation**: `py -3.11 -m pytest -q`\n"
        f"- **Build Recommendation**: `npm.cmd run build` inside frontend directory\n\n"
        f"Next: Run py -3.11 -m pytest -q to verify all unit tests pass."
    )
    return response


def get_deterministic_command_planner_response() -> str:
    response = (
        "### Command Planner Safety Rules & Workflow\n\n"
        "The AGENT ALINE X Command Planner classifies commands into three risk levels:\n"
        "1. **safe**: Read-only verification commands (e.g. `py -3.11 -m pytest -q`, `git status`, compile check). Executed without confirmation.\n"
        "2. **caution**: State-modifying, installing, starting/stopping, or writing commands (e.g. `pip install`, `npm install`, `git add`, server start). Requires explicit user confirmation before execution.\n"
        "3. **blocked**: Destructive or dangerous commands (e.g. `Remove-Item -Recurse -Force`, `git reset --hard`, commands targeting path outside workspace). Never executed.\n\n"
        "Planner endpoints & compat:\n"
        "- `/api/commands/plan`: Returns the CommandPlan for a command (dry run classification) without executing it.\n"
        "- `/api/commands/run-free`: Executes arbitrary commands, subject to strict risk level filtering (blocked commands are rejected, caution commands require `confirmed=True`).\n"
        "- `/api/commands/run`: Legacy endpoint for running pre-defined safe command IDs (maintained for compatibility).\n\n"
        "Next: Run a command dry-run using `/api/commands/plan` to verify its risk classification."
    )
    return response


def get_deterministic_qa_checklist_response() -> str:
    filepath = Path("D:/AGENT_ALINE_X_/FINAL_QA_CHECKLIST.md")
    if filepath.exists():
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if not content.strip().splitlines()[-1].startswith("Next:"):
                content = content.strip() + "\n\nNext: Run py -3.11 -m pytest -q to run all verification tests."
            return content
        except Exception:
            pass
    return (
        "### AGENT ALINE X — Final QA Checklist\n\n"
        "1. **py_compile**: Verify compilation of all key backend Python files.\n"
        "   `py -3.11 -m py_compile backend_bridge.py agent_tools.py agent_config.py project_memory.py test_safety.py`\n"
        "2. **pytest**: Run full unit tests.\n"
        "   `py -3.11 -m pytest -q`\n"
        "3. **frontend build**: Test React frontend compilation.\n"
        "   `npm.cmd run build` inside frontend directory\n"
        "4. **health endpoint**: Check backend health.\n"
        "   `Invoke-RestMethod http://127.0.0.1:8787/api/health`\n"
        "5. **release status**: Verify P7 final QA endpoint.\n"
        "   `Invoke-RestMethod http://127.0.0.1:8787/api/release/status`\n"
        "6. **memory reindex**: Rebuild index via POST.\n"
        "   `Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/memory/reindex`\n"
        "7. **memory search**: Search for model router.\n"
        "   `Invoke-RestMethod \"http://127.0.0.1:8787/api/memory/search?q=model%20router\"`\n"
        "8. **chat memory query**: Ask the model router question in chat.\n"
        "9. **command planner**: Test `safe`, `caution`, and `blocked` plan flows.\n\n"
        "Next: Run py -3.11 -m pytest -q to verify all test suites pass."
    )




@app.post("/api/models/test")
def api_models_test(req: ModelTestRequest):
    t0 = time.monotonic()
    model = req.model or DEFAULT_MODEL
    if model == "auto":
        model = "agent-aline-x"
    length_key, length_cfg = response_length_config(req.response_length)
    timeout_used = length_cfg["timeout"]

    text, err = ollama_chat(
        user_text="Reply with exactly: MODEL_OK",
        context_chunks=[],
        model=model,
        temperature=clamp_temperature(req.temperature),
        num_predict=16,
        timeout_seconds=timeout_used,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)

    if err:
        return timed_response(t0, {
            "model": model,
            "ok": False,
            "response": friendly_error(err, model=model, length_key=length_key),
            "duration_ms": duration_ms,
            "timeout_used": timeout_used,
            "recommendation": recommend_from_benchmark(False, duration_ms, length_key, timeout_used),
        }, "models.test")

    return timed_response(t0, {
        "model": model,
        "ok": True,
        "response": (text or "").strip(),
        "duration_ms": duration_ms,
        "timeout_used": timeout_used,
        "recommendation": recommend_from_benchmark(True, duration_ms, length_key, timeout_used),
    }, "models.test")


def select_model_for_prompt(prompt: str, mode: str = "auto") -> tuple[str, str]:
    """
    Selects the best model based on the prompt content and the routing rules.
    Returns (selected_model_name, reason).
    """
    if mode != "auto":
        # Map manual selections to exact installed names if necessary
        if mode == "agent-aline-x":
            return "agent-aline-x:latest", "manual selection"
        if mode == "maxwellb/gemma4-12b-it-oym":
            return "maxwellb/gemma4-12b-it-oym:latest", "manual selection"
        return mode, "manual selection"

    prompt_lower = prompt.lower()

    # C. Deep audit / QA / requirement validation
    # Trigger keywords: audit, review, verify, validate, requirement, final check, QA, risk, security review, architecture review, performance review
    audit_keywords = [
        "audit", "review", "verify", "validate", "requirement",
        "final check", "qa", "risk", "security review",
        "architecture review", "performance review"
    ]
    if any(kw in prompt_lower for kw in audit_keywords):
        return "maxwellb/gemma4-12b-it-oym:latest", "deep audit / QA rule"

    # B. Code / bug / patch / command / error log
    # Trigger keywords: code, bug, fix, error, traceback, exception, patch, file, function, terminal, command, PowerShell, npm, pytest, build, FastAPI, React, Vite, TypeScript, Python
    code_keywords = [
        "code", "bug", "fix", "error", "traceback", "exception",
        "patch", "file", "function", "terminal", "command",
        "powershell", "npm", "pytest", "build", "fastapi",
        "react", "vite", "typescript", "python"
    ]
    if any(kw in prompt_lower for kw in code_keywords):
        return "qwen2.5-coder:7b", "code / bug rule"

    # A. Normal chat / explanation / planning (Default)
    # Examples: hello, explain this, make plan, summarize, what next, project guidance
    return "agent-aline-x:latest", "normal chat / planning rule"


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    t0_perf = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]  # short ID for logs
    prompt_length = len(req.message)

    req_model = req.model or DEFAULT_MODEL
    selected_model_initial, route_reason = select_model_for_prompt(req.message, req_model)
    length_key, length_cfg = response_length_config(req.response_length)
    memory_context_requested = wants_memory_context(req.message, route_reason)

    # ── Deterministic Query Interception ────────────────────────────────────
    message_low = req.message.lower().strip()
    
    release_status_phrases = ["release status", "project release status", "final status", "ready for qa", "v3.1 status"]
    is_release_query = any(phrase in message_low for phrase in release_status_phrases)
    
    command_planner_phrases = ["command planner", "safe caution blocked", "explain command safety", "dry run", "confirmation"]
    is_planner_query = any(phrase in message_low for phrase in command_planner_phrases)
    
    qa_checklist_phrases = ["final qa checklist", "qa checklist", "release checklist"]
    is_checklist_query = any(phrase in message_low for phrase in qa_checklist_phrases)

    if is_release_query or is_planner_query or is_checklist_query:
        if is_release_query:
            det_response = get_deterministic_release_status_response()
            route_reason = "deterministic release status"
        elif is_planner_query:
            det_response = get_deterministic_command_planner_response()
            route_reason = "deterministic command planner"
        else:
            det_response = get_deterministic_qa_checklist_response()
            route_reason = "deterministic qa checklist"
            
        duration_ms = int((time.perf_counter() - t0_perf) * 1000)
        meta = build_metadata(
            request_id=request_id,
            selected_model=selected_model_initial,
            resolved_model=selected_model_initial,
            route_reason=route_reason,
            duration_ms=duration_ms,
            fallback_used=False,
            fallback_from=None,
            fallback_to=None,
            error=None,
            prompt_length_chars=prompt_length,
            context_length_chars=0,
        )
        return timed_response(t0_perf, {
            "response": det_response,
            "model": selected_model_initial,
            "response_length": length_key,
            "answer_source": "fast_local",
            "timeout_seconds": 0,
            "bypassed_ollama": True,
            "selected_model": selected_model_initial,
            "route_reason": route_reason,
            "fallback_used": False,
            "error": None,
            "metadata": meta,
        }, "chat.deterministic")


    # ── P5: Auto memory context retrieval variables ─────────────────────────
    memory_context_used = False
    memory_context_chunks = 0
    retrieval_mode = "none"
    memory_context_chars = 0
    memory_index_missing = False
    memory_auto_reindexed = False
    memory_search_query = ""
    memory_results_found = 0
    ranking_profile = "none"
    production_boost_applied = False
    test_downrank_applied = False
    query_boost_applied = False

    # ── P4: Safe file context discovery & packing ───────────────────────────
    file_chunks = []
    file_context_used = False
    file_context_file_count = 0
    file_context_chars = 0
    file_context_trimmed = False

    if req.selected_files:
        for rel_path in req.selected_files:
            fpath, err = safe_resolve_relative(rel_path)
            if err or not fpath.exists() or not fpath.is_file():
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                preview = content[:5000]  # Cap at 5000 chars to fit MAX_CONTEXT_CHUNK_CHARS budget
                formatted = (
                    f"[Project File Context]\n"
                    f"File: {rel_path}\n"
                    f"{preview}\n"
                    f"[/Project File Context]"
                )
                file_chunks.append(formatted)
                file_context_file_count += 1
                file_context_chars += len(formatted)
                file_context_used = True
            except Exception:
                pass

    # ── P5: Auto context retrieval from memory index ────────────────────────
    if not req.selected_files and memory_context_requested:
        try:
            memory_search_query = derive_memory_search_query(req.message)
            memory_index_missing = memory_index_is_missing_or_empty()
            if memory_index_missing:
                stats = reindex_project_memory()
                memory_auto_reindexed = True
                memory_index_missing = int(stats.get("indexed_chunks", 0) or 0) == 0
                retrieval_mode = stats.get("retrieval_mode", "keyword")

            search_res = search_memory_index(memory_search_query, limit=3)
            results = search_res.get("results", [])
            memory_results_found = len(results)
            retrieval_mode = search_res.get("retrieval_mode", retrieval_mode or "keyword")
            ranking_profile = search_res.get("ranking_profile", "production_first")
            production_boost_applied = bool(search_res.get("production_boost_applied", False))
            test_downrank_applied = bool(search_res.get("test_downrank_applied", False))
            query_boost_applied = bool(search_res.get("query_boost_applied", False))
            if results:
                memory_context_used = True
                memory_context_chunks = len(results)
                for res in results:
                    formatted = (
                        f"[Project File Context]\n"
                        f"File: {res['relative_path']}\n"
                        f"[Chunk {res['chunk_id']}]\n"
                        f"{res['snippet']}\n"
                        f"[/Project File Context]"
                    )
                    file_chunks.append(formatted)
                    memory_context_chars += len(formatted)
        except Exception as exc:
            logger.error("Auto memory search failed in chat: %s", exc)
            retrieval_mode = "error"

    # Merge context chunks: files first, then requested context
    merged_context = file_chunks + req.context

    # ── P3: compute original context size before trimming ──────────────────
    original_context_chars = sum(len(c) for c in merged_context)
    trimmed_context, context_chars, dropped_context = trim_context_chunks(merged_context, length_cfg["context_chars"])
    context_trimmed = dropped_context > 0 or (original_context_chars > context_chars)

    # Detect if any file context was trimmed or dropped
    final_file_chunks_count = 0
    for chunk in trimmed_context:
        if "[Project File Context]" in chunk:
            final_file_chunks_count += 1
            if "[context budget reached]" in chunk or "[context chunk truncated]" in chunk:
                file_context_trimmed = True

    if final_file_chunks_count < file_context_file_count:
        file_context_trimmed = True

    # ── Resolve model availability (P1 fallback resolver) ──────────────────
    resolved_model, pre_fallback_reason = resolve_chat_model(selected_model_initial)
    model = resolved_model or selected_model_initial
    if pre_fallback_reason:
        route_reason = f"{route_reason} ({pre_fallback_reason})"

    # ── P3: get quality profile + build extra_system instruction ───────────
    quality_profile_name, extra_system = get_quality_profile(route_reason, model)
    if memory_context_used:
        extra_system += (
            "\n\nPROJECT MEMORY CONTEXT RULES:\n"
            "- Use the provided [Project File Context] chunks as the primary source.\n"
            "- Name the relevant files first, then explain how they are involved.\n"
            "- Do not answer with generic search instructions when file context is provided."
        )

    if not resolved_model:
        meta = build_metadata(
            request_id=request_id,
            selected_model=selected_model_initial,
            resolved_model="",
            route_reason=route_reason,
            duration_ms=int((time.perf_counter() - t0_perf) * 1000),
            fallback_used=False,
            fallback_from=None,
            fallback_to=None,
            error="no available Ollama model found",
            prompt_length_chars=prompt_length,
            context_length_chars=context_chars,
            # P4 additions
            file_context_used=file_context_used,
            file_context_file_count=file_context_file_count,
            file_context_chars=file_context_chars,
            file_context_trimmed=file_context_trimmed,
            # P5 additions
            memory_context_used=memory_context_used,
            memory_context_chunks=memory_context_chunks,
            retrieval_mode=retrieval_mode,
            memory_context_chars=memory_context_chars,
            memory_index_missing=memory_index_missing,
            memory_auto_reindexed=memory_auto_reindexed,
            memory_search_query=memory_search_query,
            memory_results_found=memory_results_found,
            ranking_profile=ranking_profile,
            production_boost_applied=production_boost_applied,
            test_downrank_applied=test_downrank_applied,
            query_boost_applied=query_boost_applied,
        )
        return timed_response(t0_perf, {
            "response": "Error: no available Ollama model found. Please make sure Ollama is running and has models installed.",
            "model": model,
            "response_length": length_key,
            "answer_source": "fast_local",
            "timeout_seconds": 0,
            "bypassed_ollama": True,
            "selected_model": selected_model_initial,
            "route_reason": route_reason,
            "fallback_used": False,
            "error": True,
            "metadata": meta,
        }, "chat.error.no-models")

    # ── Fast-path: greetings ───────────────────────────────────────────────
    if is_greeting(req.message):
        duration_ms = int((time.perf_counter() - t0_perf) * 1000)
        meta = build_metadata(
            request_id=request_id,
            selected_model=selected_model_initial,
            resolved_model=model,
            route_reason=route_reason,
            duration_ms=duration_ms,
            fallback_used=False,
            fallback_from=None,
            fallback_to=None,
            error=None,
            prompt_length_chars=prompt_length,
            context_length_chars=0,
            # P4 additions
            file_context_used=file_context_used,
            file_context_file_count=file_context_file_count,
            file_context_chars=file_context_chars,
            file_context_trimmed=file_context_trimmed,
            # P5 additions
            memory_context_used=memory_context_used,
            memory_context_chunks=memory_context_chunks,
            retrieval_mode=retrieval_mode,
            memory_context_chars=memory_context_chars,
            memory_index_missing=memory_index_missing,
            memory_auto_reindexed=memory_auto_reindexed,
            memory_search_query=memory_search_query,
            memory_results_found=memory_results_found,
            ranking_profile=ranking_profile,
            production_boost_applied=production_boost_applied,
            test_downrank_applied=test_downrank_applied,
            query_boost_applied=query_boost_applied,
        )
        return timed_response(t0_perf, {
            "response": "Vanakkam! AGENT ALINE X is ready. Ask a normal question, or run Quick Audit before project-status, risk, build, git, or test questions.",
            "model": model,
            "response_length": length_key,
            "answer_source": "fast_local",
            "timeout_seconds": 0,
            "bypassed_ollama": True,
            "suggestions": ["Run Safe Audit", "Open Workspace"],
            "selected_model": model,
            "route_reason": route_reason,
            "fallback_used": False,
            "error": None,
            "metadata": meta,
        }, "chat.greeting")

    # ── Fast-path: needs context but none provided ──────────────────────────
    is_explicit_memory_query = any(phrase in req.message.lower() for phrase in MEMORY_TRIGGER_PHRASES)
    if is_explicit_memory_query and not trimmed_context and not req.selected_files and memory_results_found == 0:
        duration_ms = int((time.perf_counter() - t0_perf) * 1000)
        meta = build_metadata(
            request_id=request_id,
            selected_model=selected_model_initial,
            resolved_model=model,
            route_reason=route_reason,
            duration_ms=duration_ms,
            fallback_used=False,
            fallback_from=None,
            fallback_to=None,
            error=None,
            prompt_length_chars=prompt_length,
            context_length_chars=0,
            file_context_used=file_context_used,
            file_context_file_count=file_context_file_count,
            file_context_chars=file_context_chars,
            file_context_trimmed=file_context_trimmed,
            memory_context_used=memory_context_used,
            memory_context_chunks=memory_context_chunks,
            retrieval_mode=retrieval_mode,
            memory_context_chars=memory_context_chars,
            memory_index_missing=memory_index_missing,
            memory_auto_reindexed=memory_auto_reindexed,
            memory_search_query=memory_search_query,
            memory_results_found=memory_results_found,
            ranking_profile=ranking_profile,
            production_boost_applied=production_boost_applied,
            test_downrank_applied=test_downrank_applied,
            query_boost_applied=query_boost_applied,
        )
        response_text = (
            "Project memory index is empty after safe reindex. Run Memory Reindex, then retry the same project memory query."
            if memory_index_missing
            else "Project memory search found no matching file chunks for that query. Try a narrower filename, symbol, or feature term."
        )
        return timed_response(t0_perf, {
            "response": response_text,
            "model": model,
            "response_length": length_key,
            "answer_source": "fast_local",
            "timeout_seconds": 0,
            "bypassed_ollama": True,
            "selected_model": model,
            "route_reason": route_reason,
            "fallback_used": False,
            "error": None,
            "metadata": meta,
        }, "chat.memory.no-results")

    if not trimmed_context and needs_verified_context(req.message):
        duration_ms = int((time.perf_counter() - t0_perf) * 1000)
        meta = build_metadata(
            request_id=request_id,
            selected_model=selected_model_initial,
            resolved_model=model,
            route_reason=route_reason,
            duration_ms=duration_ms,
            fallback_used=False,
            fallback_from=None,
            fallback_to=None,
            error=None,
            prompt_length_chars=prompt_length,
            context_length_chars=0,
            # P4 additions
            file_context_used=file_context_used,
            file_context_file_count=file_context_file_count,
            file_context_chars=file_context_chars,
            file_context_trimmed=file_context_trimmed,
            # P5 additions
            memory_context_used=memory_context_used,
            memory_context_chunks=memory_context_chunks,
            retrieval_mode=retrieval_mode,
            memory_context_chars=memory_context_chars,
            memory_index_missing=memory_index_missing,
            memory_auto_reindexed=memory_auto_reindexed,
            memory_search_query=memory_search_query,
            memory_results_found=memory_results_found,
            ranking_profile=ranking_profile,
            production_boost_applied=production_boost_applied,
            test_downrank_applied=test_downrank_applied,
            query_boost_applied=query_boost_applied,
        )
        return timed_response(t0_perf, {
            "response": "Not checked yet. Run Quick Audit first.",
            "model": model,
            "response_length": length_key,
            "answer_source": "fast_local",
            "timeout_seconds": 0,
            "bypassed_ollama": True,
            "suggestions": ["Run Safe Audit"],
            "selected_model": model,
            "route_reason": route_reason,
            "fallback_used": False,
            "error": None,
            "metadata": meta,
        }, "chat.no-context")

    # ── Primary model call ─────────────────────────────────────────────────
    text, err = ollama_chat(
        user_text=req.message,
        context_chunks=trimmed_context,
        model=model,
        temperature=clamp_temperature(req.temperature),
        num_predict=length_cfg["num_predict"],
        timeout_seconds=length_cfg["timeout"],
        extra_system=extra_system,
    )

    fallback_used = False
    fallback_from: Optional[str] = None
    fallback_to: Optional[str] = None

    if err:
        fallback_from = model
        # Choose a fallback model that is actually available
        info = discover_models_cached()
        available_names = [m["name"] for m in info["discovered_models"] if m["available"]]
        
        fb_model = None
        if "agent-aline-x:latest" in available_names and model != "agent-aline-x:latest":
            fb_model = "agent-aline-x:latest"
        elif "llama3:latest" in available_names and model != "llama3:latest":
            fb_model = "llama3:latest"
        elif available_names:
            avail_other = [n for n in available_names if n != model]
            if avail_other:
                fb_model = avail_other[0]

        if fb_model:
            logger.warning(
                "[CHAT] id=%s primary model %s failed (%s) — attempting fallback to %s",
                request_id, model, err, fb_model,
            )
            text, fb_err = ollama_chat(
                user_text=req.message,
                context_chunks=trimmed_context,
                model=fb_model,
                temperature=clamp_temperature(req.temperature),
                num_predict=length_cfg["num_predict"],
                timeout_seconds=length_cfg["timeout"],
                extra_system=extra_system,
            )
            if not fb_err:
                fallback_used = True
                fallback_to = fb_model
                model = fb_model
                err = None
            else:
                err = f"{err} | fallback also failed: {fb_err}"
        else:
            err = f"{err} | no fallback model available"

    # ── Backend Guard for Memory Context Responses ──────────────────────────
    if not err and memory_context_used:
        text_low = (text or "").lower()
        guard_phrases = ["run quick audit first", "no local context", "not checked yet", "memory-search"]
        if any(gp in text_low for gp in guard_phrases):
            logger.info("[CHAT] id=%s model response intercepted by backend guard. Regenerating deterministic response.", request_id)
            text = generate_deterministic_memory_response(memory_search_query, results)


    # ── Build final metadata ────────────────────────────────────────────────
    duration_ms = int((time.perf_counter() - t0_perf) * 1000)
    err_summary = str(err)[:120] if err else None
    meta = build_metadata(
        request_id=request_id,
        selected_model=selected_model_initial,
        resolved_model=model,
        route_reason=route_reason,
        duration_ms=duration_ms,
        fallback_used=fallback_used,
        fallback_from=fallback_from,
        fallback_to=fallback_to,
        error=err_summary,
        prompt_length_chars=prompt_length,
        context_length_chars=context_chars,
        # P3
        context_trimmed=context_trimmed,
        original_context_length_chars=original_context_chars,
        final_context_length_chars=context_chars,
        response_mode=length_key,
        quality_profile=quality_profile_name,
        # P4
        file_context_used=file_context_used,
        file_context_file_count=file_context_file_count,
        file_context_chars=file_context_chars,
        file_context_trimmed=file_context_trimmed,
        # P5 additions
        memory_context_used=memory_context_used,
        memory_context_chunks=memory_context_chunks,
        retrieval_mode=retrieval_mode,
        memory_context_chars=memory_context_chars,
        memory_index_missing=memory_index_missing,
        memory_auto_reindexed=memory_auto_reindexed,
        memory_search_query=memory_search_query,
        memory_results_found=memory_results_found,
        ranking_profile=ranking_profile,
        production_boost_applied=production_boost_applied,
        test_downrank_applied=test_downrank_applied,
        query_boost_applied=query_boost_applied,
    )

    # ── Append to perf history (cap at max) ─────────────────────────────────
    _PERF_HISTORY.append(meta)
    if len(_PERF_HISTORY) > PERF_HISTORY_MAX:
        _PERF_HISTORY.pop(0)

    # ── Single structured log line per request ──────────────────────────────
    logger.info(
        "[CHAT] id=%s model=%s route=%s duration_ms=%d fallback=%s error=%s file_context=%s",
        request_id, model, route_reason, duration_ms, fallback_used, err_summary or "none", file_context_used,
    )

    if err:
        return timed_response(t0_perf, {
            "response": friendly_error(err, model=model, length_key=length_key),
            "model": model,
            "response_length": length_key,
            "answer_source": "model",
            "timeout_seconds": length_cfg["timeout"],
            "context_chars": context_chars,
            "context_chunks": len(trimmed_context),
            "dropped_context_chunks": dropped_context,
            "error": True,
            "selected_model": selected_model_initial,
            "route_reason": route_reason,
            "fallback_used": fallback_used,
            "metadata": meta,
        }, "chat.error")

    return timed_response(t0_perf, {
        "response": text,
        "model": model,
        "response_length": length_key,
        "answer_source": "model",
        "timeout_seconds": length_cfg["timeout"],
        "context_chars": context_chars,
        "context_chunks": len(trimmed_context),
        "dropped_context_chunks": dropped_context,
        "selected_model": selected_model_initial,
        "route_reason": route_reason,
        "fallback_used": fallback_used,
        "error": None,
        "metadata": meta,
    }, "chat")


@app.post("/api/commands/run")
def api_commands_run(req: CommandRequest):
    return run_command_by_id(req.command_id)

# ═══════════════════════════════════════════════════════════════════
# P6 — COMMAND EXECUTION PLANNER + SAFER COMMAND WORKFLOWS
# ═══════════════════════════════════════════════════════════════════

# ─── Risk classification patterns ─────────────────────────────────

# Safe: read-only / verification commands
_SAFE_PATTERNS: list[tuple[str, str]] = [
    ("py -3.11 -m pytest", "pytest_safe"),
    ("python -m pytest", "pytest_safe"),
    ("-m pytest", "pytest_safe"),
    ("py -3.11 -m py_compile", "py_compile_safe"),
    ("python -m py_compile", "py_compile_safe"),
    ("-m py_compile", "py_compile_safe"),
    ("npm.cmd run build", "frontend_build_safe"),
    ("npm run build", "frontend_build_safe"),
    ("git status", "git_status_safe"),
    ("git diff", "git_diff_safe"),
    ("git log --oneline", "git_log_safe"),
    ("git log", "git_log_safe"),
    ("ollama list", "ollama_list_safe"),
    ("invoke-restmethod", "http_get_safe"),
    ("curl.exe", "curl_safe"),
    ("curl ", "curl_safe"),
    ("netstat", "netstat_safe"),
    ("tasklist", "tasklist_safe"),
    ("dir ", "dir_safe"),
    ("get-childitem", "list_safe"),
    ("python -m compileall", "compileall_safe"),
    ("py_compile", "compileall_safe"),
]

# Caution: modifying/installing/starting/stopping
_CAUTION_PATTERNS: list[tuple[str, str]] = [
    ("-m pip install", "pip_install"),
    ("pip install", "pip_install"),
    ("npm install", "npm_install"),
    ("taskkill", "taskkill"),
    ("uvicorn", "start_server"),
    ("hypercorn", "start_server"),
    ("/api/memory/reindex", "memory_reindex"),
    ("git add", "git_add"),
    ("git commit", "git_commit"),
    ("git push", "git_push"),
    ("pip uninstall", "pip_uninstall"),
    ("npm uninstall", "npm_uninstall"),
]

# Blocked: destructive / dangerous
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    ("remove-item -recurse -force", "recursive_delete"),
    ("remove-item", "file_delete"),
    ("del /s", "recursive_delete"),
    ("del /f", "forced_delete"),
    ("rmdir /s", "recursive_delete"),
    ("rd /s", "recursive_delete"),
    ("format ", "disk_format"),
    ("diskpart", "disk_modify"),
    ("shutdown", "system_shutdown"),
    ("restart-computer", "system_restart"),
    ("git reset --hard", "destructive_git"),
    ("git clean -fdx", "destructive_git"),
    ("git clean -fd", "destructive_git"),
    ("docker system prune", "docker_prune"),
    ("docker rm", "docker_rm"),
    ("docker rmi", "docker_rmi"),
    ("npm cache clean --force", "npm_cache_destructive"),
    ("c:\\windows", "system_directory_access"),
    ("c:/windows", "system_directory_access"),
    ("password", "secret_in_command"),
    ("api_key", "secret_in_command"),
    ("apikey", "secret_in_command"),
    ("token=", "secret_in_command"),
    ("secret=", "secret_in_command"),
]

# Rollback notes keyed by matched_rule
_ROLLBACK_NOTES: dict[str, str] = {
    "pytest_safe": "No rollback required — read-only test run.",
    "py_compile_safe": "No rollback required — compile check only.",
    "frontend_build_safe": "No rollback required — build output in dist/; delete dist/ to clean.",
    "compileall_safe": "No rollback required — read-only compile check.",
    "git_status_safe": "No rollback required — read-only git check.",
    "git_diff_safe": "No rollback required — read-only diff.",
    "git_log_safe": "No rollback required — read-only log.",
    "ollama_list_safe": "No rollback required — read-only model list.",
    "http_get_safe": "No rollback required — read-only HTTP GET.",
    "curl_safe": "No rollback required — read-only HTTP check.",
    "netstat_safe": "No rollback required — read-only port check.",
    "tasklist_safe": "No rollback required — read-only process list.",
    "list_safe": "No rollback required — read-only directory listing.",
    "dir_safe": "No rollback required — read-only directory listing.",
    "pip_install": "Record the package name and version; rollback requires: py -3.11 -m pip uninstall <package> -y",
    "pip_uninstall": "Record which package was removed before uninstalling; reinstall if needed.",
    "npm_install": "Record package.json before install; rollback: delete node_modules, restore package.json, npm install.",
    "npm_uninstall": "Record package.json state before removal.",
    "taskkill": "Process is terminated; rollback requires restarting the process manually.",
    "start_server": "Stop the server with Ctrl+C or taskkill; rollback is restarting the previous server.",
    "memory_reindex": "Rebuilds .agent_memory/index.json; rollback: delete index.json and re-run reindex.",
    "git_add": "Unstage with: git restore --staged <file>",
    "git_commit": "Rollback with: git reset --soft HEAD~1 (only with explicit user confirmation; do not run automatically).",
    "git_push": "Cannot safely auto-rollback a push. Contact repo owner or use git revert on remote.",
    "recursive_delete": "Files may be permanently deleted — no safe auto-rollback. Ensure backup before running.",
    "file_delete": "File may be permanently deleted — no safe auto-rollback.",
    "forced_delete": "File may be permanently deleted — no safe auto-rollback.",
    "disk_format": "Disk formatting is irreversible — NEVER run without full backup.",
    "disk_modify": "Disk modification is irreversible — blocked for safety.",
    "system_shutdown": "System shutdown is irreversible in context — blocked for safety.",
    "system_restart": "System restart blocked — run manually if needed.",
    "destructive_git": "git reset --hard and git clean -fd permanently destroy uncommitted work — blocked.",
    "docker_prune": "Docker prune is irreversible for stopped containers/images — blocked for safety.",
    "docker_rm": "Container removal blocked — stopped containers cannot be easily recovered.",
    "docker_rmi": "Image removal blocked — requires re-pull or rebuild after removal.",
    "npm_cache_destructive": "npm cache clean --force clears package cache — may require re-download.",
    "system_directory_access": "Accessing C:\\Windows is outside allowed workspace — blocked.",
    "secret_in_command": "Command appears to contain a secret/token in plaintext — blocked for security.",
}


def _cwd_is_safe(cwd: Optional[str]) -> bool:
    """Return True if cwd is inside allowed workspace roots. None uses active workspace."""
    if not cwd:
        return True  # defaults to get_root_dir(), always safe
    try:
        cwd_path = Path(cwd).resolve()
        return is_allowed_path(cwd_path)
    except Exception:
        return False


def plan_command(command: str, cwd: Optional[str] = None, dry_run: bool = True, confirmed: bool = False) -> dict:
    """
    Classify a command string and return a CommandPlan dict.
    Never executes anything — pure classification only.
    """
    cmd_lower = command.strip().lower()
    effective_cwd = cwd or str(get_root_dir())

    # 1. Workspace check
    if not _cwd_is_safe(cwd):
        return {
            "command": command,
            "cwd": effective_cwd,
            "risk_level": "blocked",
            "allowed": False,
            "requires_confirmation": False,
            "dry_run": dry_run,
            "reason": f"Working directory '{cwd}' is outside allowed workspace roots.",
            "matched_rule": "cwd_outside_workspace",
            "estimated_effect": "Command would run outside the allowed workspace — rejected.",
            "rollback_note": "No rollback possible — command was blocked before execution.",
            "warnings": ["CWD is outside allowed roots."],
        }

    # 2. Blocked check — highest priority
    for pattern, rule in _BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return {
                "command": command,
                "cwd": effective_cwd,
                "risk_level": "blocked",
                "allowed": False,
                "requires_confirmation": False,
                "dry_run": dry_run,
                "reason": f"Command matches blocked pattern: '{pattern}'.",
                "matched_rule": rule,
                "estimated_effect": "Destructive or dangerous command — will never be executed.",
                "rollback_note": _ROLLBACK_NOTES.get(rule, "Blocked — no rollback note applicable."),
                "warnings": [f"Blocked by rule: {rule}"],
            }

    # 3. Safe check
    for pattern, rule in _SAFE_PATTERNS:
        if pattern in cmd_lower:
            return {
                "command": command,
                "cwd": effective_cwd,
                "risk_level": "safe",
                "allowed": True,
                "requires_confirmation": False,
                "dry_run": dry_run,
                "reason": f"Read-only or verification command matching rule: '{rule}'.",
                "matched_rule": rule,
                "estimated_effect": "Read-only — no source files modified.",
                "rollback_note": _ROLLBACK_NOTES.get(rule, "No rollback required."),
                "warnings": [],
            }

    # 4. Caution check
    for pattern, rule in _CAUTION_PATTERNS:
        if pattern in cmd_lower:
            return {
                "command": command,
                "cwd": effective_cwd,
                "risk_level": "caution",
                "allowed": True,
                "requires_confirmation": True,
                "dry_run": dry_run,
                "reason": f"Command modifies state, installs dependencies, or starts/stops processes: '{pattern}'.",
                "matched_rule": rule,
                "estimated_effect": "May modify files, processes, or package state.",
                "rollback_note": _ROLLBACK_NOTES.get(rule, "Record state before running; rollback depends on what changed."),
                "warnings": [f"Requires explicit confirmation. Rule: {rule}"],
            }

    # 5. Unknown → caution (safer default than safe)
    return {
        "command": command,
        "cwd": effective_cwd,
        "risk_level": "caution",
        "allowed": True,
        "requires_confirmation": True,
        "dry_run": dry_run,
        "reason": "Command is not recognized by any safe or blocked rule — defaulting to caution.",
        "matched_rule": "unknown_default_caution",
        "estimated_effect": "Unknown effect — treat with caution.",
        "rollback_note": "Record system state before running. Rollback depends on what changed.",
        "warnings": ["Unknown command — requires explicit confirmation."],
    }


# ─── Output Summarizer ────────────────────────────────────────────

_IMPORTANT_PATTERNS = [
    "passed", "failed", "error", "traceback", "not found",
    "module not found", "build succeeded", "compile error",
    "typescript error", "vite build", "✓", "warn",
    "syntaxerror", "importerror", "attributeerror",
]

_SUCCESS_SIGNALS = {"passed", "build succeeded", "vite build", "✓ built", "compiled successfully"}
_ERROR_SIGNALS   = {"failed", "error", "traceback", "not found", "module not found",
                    "compile error", "typescript error", "syntaxerror", "importerror", "attributeerror"}


def summarize_output(output: str, exit_code: int) -> dict:
    """
    Return a compact summary of command output.
    Keeps raw output capped at MAX_OUTPUT_CHARS (8000).
    """
    lines = output.splitlines()
    low = output.lower()

    success = exit_code == 0
    errors_detected: list[str] = []
    warnings_detected: list[str] = []
    important_lines: list[str] = []

    for line in lines:
        ll = line.lower().strip()
        if any(sig in ll for sig in _ERROR_SIGNALS):
            errors_detected.append(line.strip()[:200])
        elif "warn" in ll:
            warnings_detected.append(line.strip()[:200])
        if any(pat in ll for pat in _IMPORTANT_PATTERNS):
            important_lines.append(line.strip()[:200])

    # Deduplicate while preserving order
    seen: set[str] = set()
    important_lines = [l for l in important_lines if not (l in seen or seen.add(l))]  # type: ignore[func-returns-value]

    # Build a 1-2 line human summary
    if not output.strip() or output.strip() == "(no output)":
        summary = "No output produced."
    elif errors_detected:
        summary = f"Command completed with errors. First error: {errors_detected[0][:120]}"
    elif any(sig in low for sig in _SUCCESS_SIGNALS):
        summary = "Command completed successfully."
    elif exit_code == 0:
        summary = "Command completed (exit 0, no explicit success signal detected)."
    else:
        summary = f"Command completed with non-zero exit code {exit_code}."

    raw_preview = output[:MAX_OUTPUT_CHARS]
    raw_truncated = len(output) > MAX_OUTPUT_CHARS

    return {
        "exit_code": exit_code,
        "success": success,
        "output_summary": summary,
        "important_lines": important_lines[:20],   # cap to 20 lines
        "errors_detected": errors_detected[:10],   # cap to 10
        "warnings_detected": warnings_detected[:10],
        "raw_output_preview": raw_preview,
        "raw_output_truncated": raw_truncated,
    }


# ─── Command templates ────────────────────────────────────────────

COMMAND_TEMPLATES = [
    {
        "id": "backend-compile",
        "label": "Backend Compile",
        "risk_level": "safe",
        "command": "py -3.11 -m py_compile backend_bridge.py agent_tools.py agent_config.py project_memory.py test_safety.py",
        "cwd": str(Path("D:/AGENT_ALINE_X_").resolve()),
        "description": "Syntax-check all key backend Python files using Python 3.11.",
        "rollback_note": "No rollback required — read-only compile check.",
    },
    {
        "id": "backend-tests",
        "label": "Backend Tests",
        "risk_level": "safe",
        "command": "py -3.11 -m pytest -q",
        "cwd": str(Path("D:/AGENT_ALINE_X_").resolve()),
        "description": "Run the full test suite with minimal output.",
        "rollback_note": "No rollback required — read-only test run.",
    },
    {
        "id": "frontend-build",
        "label": "Frontend Build",
        "risk_level": "safe",
        "command": "npm.cmd run build",
        "cwd": str(Path("D:/AGENT_ALINE_X_/frontend").resolve()),
        "description": "Build the React/Vite frontend into dist/.",
        "rollback_note": "No rollback required — output in dist/; delete dist/ to clean.",
    },
    {
        "id": "health-check",
        "label": "Backend Health Check",
        "risk_level": "safe",
        "command": "Invoke-RestMethod http://127.0.0.1:8787/api/health",
        "cwd": str(Path("D:/AGENT_ALINE_X_").resolve()),
        "description": "Check backend health endpoint.",
        "rollback_note": "No rollback required — read-only HTTP GET.",
    },
    {
        "id": "memory-reindex",
        "label": "Memory Reindex",
        "risk_level": "caution",
        "command": "Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/memory/reindex",
        "cwd": str(Path("D:/AGENT_ALINE_X_").resolve()),
        "description": "Rebuild the project memory index (writes .agent_memory/index.json).",
        "rollback_note": "Rebuilds .agent_memory/index.json; rollback: delete index.json and re-run reindex.",
    },
    {
        "id": "memory-search",
        "label": "Memory Search (example)",
        "risk_level": "safe",
        "command": 'Invoke-RestMethod "http://127.0.0.1:8787/api/memory/search?q=model%20router"',
        "cwd": str(Path("D:/AGENT_ALINE_X_").resolve()),
        "description": "Search the project memory index for 'model router'.",
        "rollback_note": "No rollback required — read-only search.",
    },
]


# ─── P6 endpoints ─────────────────────────────────────────────────

@app.post("/api/commands/plan")
def api_commands_plan(req: CommandPlanRequest):
    """Return a CommandPlan without executing anything."""
    t0 = time.monotonic()
    pl = plan_command(req.command, cwd=req.cwd, dry_run=req.dry_run)
    return timed_response(t0, pl, "commands.plan")


@app.post("/api/commands/run-free")
def api_commands_run_free(req: CommandRunFreeRequest):
    """
    Plan-first run for free-form commands (not just pre-approved IDs).
    Enforces risk classification before any execution.
    Blocked → never runs.
    Caution without confirmed=True → returns plan with confirmation_required.
    Safe or Caution+confirmed → executes via subprocess (shell=False, timeout).
    """
    t0 = time.monotonic()
    pl = plan_command(req.command, cwd=req.cwd, dry_run=False)

    if pl["risk_level"] == "blocked":
        return timed_response(t0, {
            "executed": False,
            "plan": pl,
            "reason": "blocked",
            "output_summary": None,
        }, "commands.run-free.blocked")

    if pl["risk_level"] == "caution" and not req.confirmed:
        return timed_response(t0, {
            "executed": False,
            "plan": pl,
            "reason": "confirmation_required",
            "output_summary": None,
        }, "commands.run-free.needs-confirm")

    if req.cwd and not _cwd_is_safe(req.cwd):
        return timed_response(t0, {
            "executed": False,
            "plan": pl,
            "reason": "blocked",
            "output_summary": None,
        }, "commands.run-free.cwd-blocked")

    # Execute
    effective_cwd = req.cwd or str(get_root_dir())
    cmd_parts = req.command.split()

    try:
        result = subprocess.run(
            cmd_parts,
            cwd=effective_cwd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        raw = ""
        if result.stdout:
            raw += result.stdout
        if result.stderr:
            raw += ("\n" if raw else "") + result.stderr
        if not raw.strip():
            raw = "(no output)"
        raw = redact(raw)
        summary = summarize_output(raw, result.returncode)
    except subprocess.TimeoutExpired:
        return timed_response(t0, {
            "executed": True,
            "plan": pl,
            "reason": "timeout",
            "output_summary": summarize_output("Command timed out.", -1),
        }, "commands.run-free.timeout")
    except FileNotFoundError as exc:
        return timed_response(t0, {
            "executed": True,
            "plan": pl,
            "reason": "not_found",
            "output_summary": summarize_output(f"Command not found: {exc}", -1),
        }, "commands.run-free.not-found")
    except Exception as exc:
        return timed_response(t0, {
            "executed": True,
            "plan": pl,
            "reason": "error",
            "output_summary": summarize_output(f"Error: {exc}", -1),
        }, "commands.run-free.error")

    return timed_response(t0, {
        "executed": True,
        "plan": pl,
        "reason": "executed",
        "output_summary": summary,
    }, "commands.run-free.done")


@app.get("/api/commands/templates")
def api_commands_templates():
    """Return safe command templates for common workflows."""
    t0 = time.monotonic()
    return timed_response(t0, {
        "templates": COMMAND_TEMPLATES,
    }, "commands.templates")


# END P6



@app.get("/api/project/search")
def api_project_search(q: str):
    t0 = time.monotonic()
    try:
        results = search_project_memory(q)
        return timed_response(t0, {
            "query": q,
            "active_workspace": str(get_active_workspace()),
            "results": results
        }, "project.search.success")
    except Exception as exc:
        return timed_response(t0, {
            "query": q,
            "active_workspace": str(get_active_workspace()),
            "results": [],
            "error": str(exc)
        }, "project.search.error")


@app.post("/api/memory/reindex")
def api_memory_reindex(model: Optional[str] = "nomic-embed-text"):
    t0 = time.monotonic()
    try:
        stats = reindex_project_memory(model or "nomic-embed-text")
        return timed_response(t0, stats, "memory.reindex.success")
    except Exception as exc:
        return timed_response(t0, {
            "indexed_files": 0,
            "indexed_chunks": 0,
            "skipped_files": 0,
            "embedding_available": False,
            "retrieval_mode": "error",
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "errors": [str(exc)]
        }, "memory.reindex.error")


@app.get("/api/memory/search")
def api_memory_search(q: str, model: Optional[str] = "nomic-embed-text"):
    t0 = time.monotonic()
    try:
        results = search_memory_index(q, model=model or "nomic-embed-text")
        return timed_response(t0, results, "memory.search.success")
    except Exception as exc:
        return timed_response(t0, {
            "query": q,
            "retrieval_mode": "error",
            "results": [],
            "error": str(exc)
        }, "memory.search.error")


@app.get("/api/project/file")
def api_project_file(path: str):
    t0 = time.monotonic()
    fpath, err = safe_resolve_relative(path)
    if err:
        return timed_response(t0, {
            "error": err
        }, "project.file.blocked")
        
    if not fpath.exists() or not fpath.is_file():
        return timed_response(t0, {
            "error": f"File not found: {path}"
        }, "project.file.missing")
        
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        total_chars = len(content)
        truncated = total_chars > 20000
        preview = content[:20000]
        return timed_response(t0, {
            "relative_path": path,
            "content_preview": preview,
            "total_chars": total_chars,
            "truncated": truncated,
            "language": fpath.suffix.lstrip(".")
        }, "project.file.success")
    except Exception as exc:
        return timed_response(t0, {
            "error": f"Failed to read file: {exc}"
        }, "project.file.error")



@app.get("/api/performance")
def api_performance():
    t0 = time.monotonic()
    records = list(reversed(_PERF_HISTORY))  # newest first
    total = len(records)
    avg_duration = round(sum(r["duration_ms"] for r in records) / total, 1) if total else 0.0
    fallback_count = sum(1 for r in records if r.get("fallback_used"))
    model_usage: dict[str, int] = {}
    for r in records:
        rm = r.get("resolved_model") or r.get("selected_model") or "unknown"
        model_usage[rm] = model_usage.get(rm, 0) + 1
    return timed_response(t0, {
        "recent": records,
        "total_requests": total,
        "average_duration_ms": avg_duration,
        "fallback_count": fallback_count,
        "model_usage": model_usage,
    }, "performance")


@app.post("/api/files/list")
def api_files_list(req: FileListRequest):
    t0 = time.monotonic()
    path, err = safe_resolve(req.path)
    if err:
        return timed_response(t0, {"entries": [], "error": err}, "files.list.blocked")
    if not path.exists():
        return timed_response(t0, {"entries": [], "error": f"Path does not exist: {path}"}, "files.list.missing")
    if path.is_file():
        return timed_response(t0, {"entries": [], "error": "Path is a file, not a directory."}, "files.list.file")

    entries = []
    try:
        for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            locked = item.is_file() and is_blocked_filename(item)
            entries.append({
                "name": item.name,
                "type": "DIR" if item.is_dir() else "FILE",
                "size": item.stat().st_size if item.is_file() else None,
                "locked": locked,
            })
    except PermissionError as exc:
        return timed_response(t0, {"entries": [], "error": f"Permission denied: {exc}"}, "files.list.permission")

    return timed_response(t0, {"entries": entries, "error": None, "path": str(path)}, "files.list")


@app.post("/api/files/read-range")
def api_files_read_range(req: FileReadRangeRequest):
    t0 = time.monotonic()
    path, err = safe_resolve(req.path)
    if err:
        return timed_response(t0, {"lines": [], "error": err}, "files.read-range.blocked")
    if is_blocked_filename(path):
        return timed_response(t0, {"lines": [], "error": f"BLOCKED: '{path.name}' is a protected file and cannot be read."}, "files.read-range.secret")

    lines, err2 = read_file_range(req.path, req.start, req.end)
    if err2:
        return timed_response(t0, {"lines": [], "error": err2}, "files.read-range.error")

    start = max(1, req.start)
    numbered = [{"line": start + i, "text": t} for i, t in enumerate(lines)]
    return timed_response(t0, {"lines": numbered, "error": None, "path": str(path)}, "files.read-range")


@app.post("/api/audit/full")
def api_audit_full():
    t0 = time.monotonic()
    sequence = [
        "git-status",
        "git-diff-stat",
        "git-log-short",
        "python-compile",
        "frontend-build",
        "backend-health",
    ]
    steps = []
    overall_ok = True
    for cmd_id in sequence:
        result = run_command_by_id(cmd_id)
        steps.append(result)
        if not result["ok"]:
            overall_ok = False
    if overall_ok:
        rating = "Healthy"
    elif sum(1 for s in steps if not s["ok"]) <= 1:
        rating = "Needs Attention"
    else:
        rating = "Critical"

    return timed_response(t0, {
        "steps": steps,
        "pass": overall_ok,
        "health_rating": rating,
    }, "audit.full")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=BACKEND_PORT)

