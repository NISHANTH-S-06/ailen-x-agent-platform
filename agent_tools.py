"""
agent_tools.py — Core tools: path safety, file ops, subprocess runner, Ollama client.
v1.1 — Added secret file blocking, command duration, context deduplication support.
"""

import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from agent_config import (
    ALLOWED_ROOTS,
    BLOCKED_PATH_PREFIXES,
    BLOCKED_PATH_SEGMENTS,
    BLOCKED_FILENAMES,
    BLOCKED_FILENAME_SUFFIXES,
    OLLAMA_CHAT_URL,
    OLLAMA_TAGS_URL,
    OLLAMA_TIMEOUT,
    MODEL_NAME,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    LLM_TEMPERATURE,
    LLM_NUM_PREDICT,
    SAFE_COMMANDS,
    MAX_COMMAND_OUTPUT_CHARS,
    SYSTEM_PROMPT,
)


# ─── Path Safety ─────────────────────────────────────────────────────────────

def _is_relative_to(child: Path, parent: Path) -> bool:
    if hasattr(child, "is_relative_to"):
        return child.is_relative_to(parent)
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def is_allowed_path(path) -> bool:
    """Return True only if path is under one of the allowed roots."""
    try:
        resolved = Path(path).resolve()
        for root in ALLOWED_ROOTS:
            root_path = Path(root).resolve()
            if resolved == root_path or _is_relative_to(resolved, root_path):
                return True
    except Exception:
        return False
    return False


def has_blocked_segment(raw: str) -> bool:
    """Return True if the raw path string contains any blocked segment."""
    lower = raw.lower().replace("/", "\\")
    for prefix in BLOCKED_PATH_PREFIXES:
        if lower.startswith(prefix.lower().replace("/", "\\")):
            return True
    for seg in BLOCKED_PATH_SEGMENTS:
        if seg.lower().replace("/", "\\") in lower:
            return True
    return False


def is_blocked_filename(path: Path) -> bool:
    """
    Return True if the filename matches any blocked secret file pattern.
    Checks exact filename matches and suffix matches.
    Even if the file is under an allowed root, it cannot be read.
    """
    name_lower = path.name.lower()
    # Exact filename match
    for blocked in BLOCKED_FILENAMES:
        if name_lower == blocked.lower():
            return True
        # Also catch sub-path patterns like ".git/config"
        if str(path).lower().replace("\\", "/").endswith("/" + blocked.lower()):
            return True
    # Suffix match
    for suffix in BLOCKED_FILENAME_SUFFIXES:
        if name_lower.endswith(suffix.lower()):
            return True
    return False


def safe_resolve(raw: str) -> tuple[Optional[Path], Optional[str]]:
    """
    Resolve a raw path string safely.
    Returns (Path, None) on success or (None, error_message) on failure.
    """
    raw = raw.strip().strip('"').strip("'")

    if has_blocked_segment(raw):
        return None, f"🚫 BLOCKED: Path contains a blocked segment — '{raw}'"

    try:
        p = Path(raw)
        if not p.is_absolute():
            return None, f"🚫 BLOCKED: Only absolute paths are allowed — '{raw}'"
        p = p.resolve()
    except Exception as exc:
        return None, f"Error resolving path: {exc}"

    if not is_allowed_path(p):
        return None, (
            f"🚫 BLOCKED: '{p}' is outside allowed roots.\n"
            f"Allowed: {[str(r) for r in ALLOWED_ROOTS]}"
        )

    return p, None


# ─── File Operations ─────────────────────────────────────────────────────────

def list_directory(raw_path: str) -> tuple[Optional[list[dict]], Optional[str]]:
    """List directory contents safely. Returns (entries, error)."""
    path, err = safe_resolve(raw_path)
    if err:
        return None, err
    if not path.exists():
        return None, f"Path does not exist: {path}"
    if path.is_file():
        stat = path.stat()
        return [{"name": path.name, "type": "FILE", "size": stat.st_size, "path": str(path)}], None

    entries = []
    try:
        for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            is_secret = item.is_file() and is_blocked_filename(item)
            entry = {
                "name": item.name,
                "type": "DIR" if item.is_dir() else "FILE",
                "size": item.stat().st_size if item.is_file() else None,
                "path": str(item),
                "blocked": is_secret,
            }
            entries.append(entry)
    except PermissionError as exc:
        return None, f"Permission denied: {exc}"

    return entries, None


def read_file(raw_path: str, max_lines: int = 200) -> tuple[Optional[list[str]], Optional[str]]:
    """
    Read file lines safely. Returns (lines, error).
    v1.1: Blocks secret/credential files even if under an allowed root.
    """
    path, err = safe_resolve(raw_path)
    if err:
        return None, err

    # Block secret files — even inside allowed roots
    if is_blocked_filename(path):
        return None, (
            f"🔒 BLOCKED: '{path.name}' is a protected file and cannot be read.\n"
            "Secret, credential, and key files are always blocked for safety."
        )

    if not path.exists():
        return None, f"File does not exist: {path}"
    if not path.is_file():
        return None, f"Not a file: {path}"

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return None, f"Could not read file: {exc}"

    all_lines = text.splitlines()
    return all_lines[:max_lines], None


def read_file_range(raw_path: str, start_line: int, end_line: int) -> tuple[Optional[list[str]], Optional[str]]:
    """
    Read a specific line range from a file safely (1-indexed, inclusive).
    Reuses all safety guards from read_file. Returns (lines, error).
    """
    path, err = safe_resolve(raw_path)
    if err:
        return None, err

    if is_blocked_filename(path):
        return None, (
            f"🔒 BLOCKED: '{path.name}' is a protected file and cannot be read.\n"
            "Secret, credential, and key files are always blocked for safety."
        )

    if not path.exists():
        return None, f"File does not exist: {path}"
    if not path.is_file():
        return None, f"Not a file: {path}"

    if start_line < 1:
        return None, f"Start line must be ≥ 1, got {start_line}."
    if end_line < start_line:
        return None, f"End line ({end_line}) must be ≥ start line ({start_line})."

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return None, f"Could not read file: {exc}"

    all_lines = text.splitlines()
    total = len(all_lines)
    # Clamp to file bounds
    s = max(0, start_line - 1)         # convert to 0-indexed
    e = min(total, end_line)            # end_line is inclusive, slice is exclusive
    sliced = all_lines[s:e]
    # Return lines with their original 1-indexed line numbers as metadata
    return sliced, None


def make_context_chunk_from_file(raw_path: str, lines: list[str]) -> str:
    return f"FILE: {raw_path}\n" + "\n".join(
        f"{i+1:04d}: {line}" for i, line in enumerate(lines)
    )


# ─── Safe Command Runner ─────────────────────────────────────────────────────

def run_safe_command(key: str) -> dict:
    """
    Run a pre-approved safe command by key.
    Returns a dict with: key, label, cwd, cmd_str, exit_code, output, truncated.
    """
    if key not in SAFE_COMMANDS:
        return {
            "key": key,
            "label": key,
            "cwd": "",
            "cmd_str": "",
            "exit_code": -1,
            "output": f"🚫 BLOCKED: '{key}' is not in the allowed command list.",
            "truncated": False,
            "error": True,
            "duration_ms": 0,
        }

    spec = SAFE_COMMANDS[key]
    cwd_path = Path(spec["cwd"])
    if not is_allowed_path(cwd_path):
        return {
            "key": key,
            "label": spec["label"],
            "cwd": spec["cwd"],
            "cmd_str": "",
            "exit_code": -1,
            "output": f"🚫 BLOCKED: Command directory '{cwd_path}' is outside allowed workspace roots.",
            "truncated": False,
            "error": True,
            "duration_ms": 0,
        }

    cmd_str = " ".join(spec["cmd"])
    t_start = time.monotonic()

    try:
        result = subprocess.run(
            spec["cmd"],
            cwd=spec["cwd"],
            text=True,
            capture_output=True,
            timeout=spec.get("timeout", 60),
            shell=False,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        return {
            "key": key,
            "label": spec["label"],
            "cwd": spec["cwd"],
            "cmd_str": cmd_str,
            "exit_code": -1,
            "output": "⏰ Command timed out.",
            "truncated": False,
            "error": True,
            "duration_ms": duration_ms,
        }
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        return {
            "key": key,
            "label": spec["label"],
            "cwd": spec["cwd"],
            "cmd_str": cmd_str,
            "exit_code": -1,
            "output": f"⚠️ Command not found: {exc}",
            "truncated": False,
            "error": True,
            "duration_ms": duration_ms,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        return {
            "key": key,
            "label": spec["label"],
            "cwd": spec["cwd"],
            "cmd_str": cmd_str,
            "exit_code": -1,
            "output": f"Error running command: {exc}",
            "truncated": False,
            "error": True,
            "duration_ms": duration_ms,
        }

    duration_ms = int((time.monotonic() - t_start) * 1000)

    raw_output = ""
    if result.stdout:
        raw_output += "STDOUT:\n" + result.stdout
    if result.stderr:
        raw_output += "\nSTDERR:\n" + result.stderr
    if not raw_output.strip():
        raw_output = "(No output)"

    truncated = len(raw_output) > MAX_COMMAND_OUTPUT_CHARS
    output = raw_output[:MAX_COMMAND_OUTPUT_CHARS]
    if truncated:
        output += "\n\n... [output truncated] ..."

    return {
        "key": key,
        "label": spec["label"],
        "cwd": spec["cwd"],
        "cmd_str": cmd_str,
        "exit_code": result.returncode,
        "output": output,
        "truncated": truncated,
        "error": False,
        "duration_ms": duration_ms,
    }


def make_context_chunk_from_command(result: dict) -> str:
    duration_str = f"{result.get('duration_ms', 0)}ms"
    return (
        f"COMMAND RESULT: {result['label']} ({result['key']})\n"
        f"CWD: {result['cwd']}\n"
        f"CMD: {result['cmd_str']}\n"
        f"Exit code: {result['exit_code']}\n"
        f"Duration: {duration_str}\n"
        f"{result['output']}"
    )


# ─── Ollama Client ────────────────────────────────────────────────────────────

def check_ollama_status(model: Optional[str] = None) -> tuple[bool, bool, str]:
    """
    Check Ollama availability and model presence.
    Returns (ollama_running: bool, model_found: bool, message: str).
    """
    try:
        req = urllib.request.Request(OLLAMA_TAGS_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
        models = [m.get("name", "") for m in data.get("models", [])]
        
        target_model = model if model else DEFAULT_MODEL
        if target_model == "auto":
            target_model = "agent-aline-x"
        # Check if target_model is present (allowing a match with or without tag)
        found = any(target_model in m for m in models)
        
        # Verify both models if possible to construct the message
        status_parts = []
        for am in AVAILABLE_MODELS:
            am_found = any(am in m for m in models)
            status_parts.append(f"{am}: {'🟢' if am_found else '🔴'}")
        
        msg = f"Models status: {', '.join(status_parts)}"
        return True, found, msg
    except urllib.error.URLError as exc:
        return False, False, f"Cannot reach Ollama: {exc.reason}"
    except Exception as exc:
        return False, False, f"Error: {exc}"


def ollama_chat(
    user_text: str,
    context_chunks: list[str],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    num_predict: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
    extra_system: str = "",
) -> tuple[Optional[str], Optional[str]]:
    """
    Send a chat request to Ollama with the system prompt and local context.
    extra_system is appended to the static SYSTEM_PROMPT for route-specific
    quality instructions and hallucination safety addendum.
    Returns (response_text, error_message).
    """
    target_model = model if model else DEFAULT_MODEL
    if target_model == "auto":
        target_model = "agent-aline-x"


    # Verify if selected model is available in Ollama
    is_running, found, msg = check_ollama_status(target_model)
    if not is_running:
        return None, f"Ollama is not running. {msg}"
    if not found:
        return None, (
            f"Selected model '{target_model}' is not available in Ollama. "
            f"Run: ollama pull {target_model}, or choose an installed model in Settings."
        )

    recent_chunks = []
    total_context_chars = 0
    for chunk in context_chunks[-8:]:
        cleaned = (chunk or "").strip()
        if not cleaned:
            continue
        if len(cleaned) > 6000:
            cleaned = cleaned[:6000] + "\n... [context chunk truncated]"
        if total_context_chars + len(cleaned) > 30000:
            remaining = 30000 - total_context_chars
            if remaining > 500:
                recent_chunks.append(cleaned[:remaining] + "\n... [context budget reached]")
            break
        recent_chunks.append(cleaned)
        total_context_chars += len(cleaned)
    local_context = "\n\n--- CONTEXT CHUNK ---\n\n".join(recent_chunks)

    if local_context:
        full_user = (
            f"LOCAL CONTEXT:\n{local_context}\n\n"
            f"USER QUESTION:\n{user_text}"
        )
    else:
        full_user = (
            f"[No local context loaded. Answer with 'Not Checked' where evidence is missing.]\n\n"
            f"USER QUESTION:\n{user_text}"
        )

    # Use custom or default temperature & num_predict
    temp = temperature if temperature is not None else LLM_TEMPERATURE
    predict = num_predict if num_predict is not None else LLM_NUM_PREDICT
    timeout = timeout_seconds if timeout_seconds is not None else OLLAMA_TIMEOUT

    # Build final system content: static base + per-route addendum
    system_content = SYSTEM_PROMPT
    if extra_system:
        system_content = SYSTEM_PROMPT + "\n\n" + extra_system

    payload = {
        "model": target_model,
        "stream": False,
        "options": {
            "temperature": temp,
            "num_predict": predict,
        },
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": full_user},
        ],
    }

    try:
        req = urllib.request.Request(
            OLLAMA_CHAT_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data["message"]["content"], None
    except TimeoutError:
        return None, f"Ollama request timed out after {timeout} seconds."
    except urllib.error.URLError as exc:
        return None, f"Ollama connection error: {exc.reason}"
    except Exception as exc:
        return None, f"Error calling Ollama: {exc}"
