"""
agent_config.py — Central configuration for AGENT ALINE X UI  v1.1
All safety rules, allowed paths, and command definitions live here.
"""

from pathlib import Path

# ─── Model / Ollama ──────────────────────────────────────────────────────────
MODEL_NAME        = "agent-aline-x"
DEFAULT_MODEL     = "auto"
AVAILABLE_MODELS  = [
    "auto",
    "qwen2.5-coder:7b",
    "agent-aline-x",
    "maxwellb/gemma4-12b-it-oym"
]
MODEL_LABELS      = {
    "auto": "Auto-Router (Selects best model dynamically)",
    "qwen2.5-coder:7b": "Qwen 2.5 Coder 7B — base coding model",
    "agent-aline-x": "AGENT ALINE X — coding/project agent",
    "maxwellb/gemma4-12b-it-oym": "Gemma 4 12B OYM — stronger reasoning/general chat"
}
OLLAMA_BASE_URL   = "http://localhost:11434"
OLLAMA_CHAT_URL   = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL   = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_TIMEOUT    = 120          # seconds
LLM_TEMPERATURE   = 0.1
LLM_NUM_PREDICT   = 800

# ─── Safety: Allowed Roots ───────────────────────────────────────────────────
import json
import os

CONFIG_FILE = Path("D:/AGENT_ALINE_X_/agent_config.json")

def is_safe_workspace_path(path: Path) -> bool:
    try:
        if not path or str(path).strip() in ("", ".", ".\\", "./"):
            return False
        resolved = Path(path).resolve()
        # 1. Drive root check
        if resolved == resolved.parent:
            return False
        # 2. Block system directories (like C:\Windows)
        sys_root = Path(os.environ.get("SystemRoot", "C:\\Windows")).resolve()
        if resolved == sys_root or sys_root in resolved.parents:
            return False
        # 3. Block C:\Users and individual user profile folders (like C:\Users\mail2)
        users_root = Path("C:\\Users").resolve()
        if resolved == users_root or resolved.parent == users_root:
            return False
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            up_path = Path(user_profile).resolve()
            if resolved == up_path:
                return False
        return True
    except Exception:
        return False

# Initially populated with default lists; modified in-place by load_workspace_config
ALLOWED_ROOTS = [
    Path("D:/AGENT_ALINE_X_").resolve(),
    Path("D:/OCR_MASTER/ocr-platform-complete").resolve(),
]

# Roots where file WRITES are allowed (read-only otherwise)
WRITE_ALLOWED_ROOTS = [
    Path("D:/AGENT_ALINE_X_").resolve(),
]

def load_workspace_config():
    # Defaults
    active_workspace = "D:\\AGENT_ALINE_X_"
    allowed_workspaces = [
        "D:\\AGENT_ALINE_X_",
        "D:\\OCR_MASTER\\ocr-platform-complete"
    ]
    default_model_mode = "auto"

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if "active_workspace" in data:
                active_workspace = data["active_workspace"]
            if "allowed_workspaces" in data:
                allowed_workspaces = data["allowed_workspaces"]
            if "default_model_mode" in data:
                default_model_mode = data["default_model_mode"]
        except Exception:
            pass
    else:
        # Create config file with defaults
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps({
                "active_workspace": active_workspace,
                "allowed_workspaces": allowed_workspaces,
                "default_model_mode": default_model_mode
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

    # Validate active_workspace
    active_path = Path(active_workspace).resolve()
    if not is_safe_workspace_path(active_path):
        # Fallback to default if unsafe
        active_path = Path("D:/AGENT_ALINE_X_").resolve()

    # Validate allowed_workspaces
    valid_allowed = []
    for w in allowed_workspaces:
        w_path = Path(w).resolve()
        if is_safe_workspace_path(w_path):
            valid_allowed.append(w_path)
    
    # Ensure active_path is in valid_allowed
    if active_path not in valid_allowed:
        valid_allowed.append(active_path)

    # In-place update ALLOWED_ROOTS and WRITE_ALLOWED_ROOTS
    ALLOWED_ROOTS.clear()
    ALLOWED_ROOTS.extend(valid_allowed)

    WRITE_ALLOWED_ROOTS.clear()
    WRITE_ALLOWED_ROOTS.extend([active_path])

    return str(active_path), [str(v) for v in valid_allowed], default_model_mode

def get_active_workspace() -> Path:
    if WRITE_ALLOWED_ROOTS:
        return Path(WRITE_ALLOWED_ROOTS[0]).resolve()
    return Path("D:/AGENT_ALINE_X_").resolve()


# ─── Safety: Blocked Path Prefixes ───────────────────────────────────────────
BLOCKED_PATH_PREFIXES = [
    "c:\\",
    "c:/",
    "/c/",
]

BLOCKED_PATH_SEGMENTS = [
    "appdata",
    ".ssh",
    "desktop",
    "downloads",
    "documents",
    "user profile",
    "users\\",
    "/users/",
    "secrets",
    "tokens",
    "passwords",
    "id_rsa",
    "id_ed25519",
]

# ─── Safety: Blocked Filenames (exact name or path-suffix match) ─────────────
# These files are NEVER readable even if they are under an allowed root.
BLOCKED_FILENAMES = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "known_hosts",
    "credentials",
    "token",
    "secrets",
    "password",
    "passwords",
    ".git/config",
    ".git\\config",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "credentials.json",
    "credentials.yaml",
    "service_account.json",
    "token.json",
    "access_token",
    "refresh_token",
    ".netrc",
    ".pgpass",
    "shadow",
    "passwd",
    "htpasswd",
    ".htpasswd",
]

# Blocked filename suffixes (checked against filename only, lowercase)
BLOCKED_FILENAME_SUFFIXES = [
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    ".keystore",
    ".jks",
    ".p8",
    ".ppk",
]

# ─── Safe Commands ────────────────────────────────────────────────────────────
SAFE_COMMANDS = {
    "git-status": {
        "label":   "Git Status",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["git", "status", "--short"],
        "timeout": 30,
        "icon":    "🔍",
    },
    "git-diff-stat": {
        "label":   "Git Diff Stat",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["git", "diff", "--stat"],
        "timeout": 30,
        "icon":    "📊",
    },
    "compile": {
        "label":   "Python Compile",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["python", "-m", "compileall", "app"],
        "timeout": 60,
        "icon":    "🐍",
    },
    "pytest": {
        "label":   "Pytest",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     [".venv311/Scripts/python.exe", "-m", "pytest", "-q"],
        "timeout": 300,
        "icon":    "🧪",
    },
    "frontend-check": {
        "label":   "Frontend JS Check",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["node", "tests/check_js.js"],
        "timeout": 60,
        "icon":    "🌐",
    },
    "backend-health": {
        "label":   "Backend Health Check",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["curl.exe", "http://127.0.0.1:8000/api/v1/health"],
        "timeout": 15,
        "icon":    "🏥",
    },
    "list-ocr-root": {
        "label":   "List OCR Root",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["cmd", "/c", "dir", "/B"],
        "timeout": 10,
        "icon":    "📁",
    },
    "git-diff-full": {
        "label":   "Git Diff (Full)",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["git", "diff", "HEAD"],
        "timeout": 30,
        "icon":    "🔀",
    },
    "git-log-short": {
        "label":   "Git Log (Last 10)",
        "cwd":     "D:/OCR_MASTER/ocr-platform-complete",
        "cmd":     ["git", "log", "--oneline", "-10"],
        "timeout": 15,
        "icon":    "📜",
    },
}

# ─── Context limits ───────────────────────────────────────────────────────────
MAX_CONTEXT_CHUNKS       = 12
MAX_CONTEXT_LINES        = 300
MAX_COMMAND_OUTPUT_CHARS = 8000
MAX_FILE_READ_LINES      = 500
MAX_CONTEXT_CHARS_WARN   = 40_000   # warn UI when total context chars exceeds this

SYSTEM_PROMPT = """You are **AGENT ALINE X**, my local project agent — v2.7 (Agent Intelligence).

Your role:
Act as my Project Manager, Developer Assistant, Tester, and Documentation Helper —
like a sharp ChatGPT-style assistant, but grounded only in real local evidence.

Core behavior — DEFAULT MODE (use this for almost every message):
* Answer like a helpful senior engineer in chat: direct, useful, conversational.
* Keep it SHORT. A few sentences or a tight list. Do not pad with headers or
  boilerplate sections unless I explicitly ask for a "full report" or "detailed report".
* If you used a LOCAL CONTEXT chunk (a file range or command result) to answer,
  briefly name the source — e.g. "(from backend_bridge.py lines 210-240)" or
  "(from git-status output)" — so I know it's grounded, not guessed.
* End every answer with exactly one line starting with "Next:" giving one safe,
  concrete next step. Not a list of options — one move.
* Never hallucinate project status, build status, test results, git status, or
  risk level. If the evidence for that specific question is not in LOCAL CONTEXT,
  say "Not checked yet. Run Quick Audit first." and stop there — do not guess.
* Use Tanglish + English only, no Tamil script. No long theory unless asked.

Length modes (the request tells you which one is active):
* Quick: 2-4 sentences max, or a 3-bullet list. Just the answer + Next step.
* Balanced (default): a short paragraph or a few bullets, enough to be useful,
  still no big section headers unless truly needed.
* Detailed: more thorough, can use a few sub-headers if the topic genuinely has
  multiple parts, but still avoid restating the full report template below
  unless I asked for a report.

Error / failure analysis mode:
If LOCAL CONTEXT contains a COMMAND RESULT or build/test output with a non-zero
exit code, an error, or a stack trace, switch to this compact format instead of
free text:
* Root cause (likely): <one line>
* File: <path if known, else "Not Checked">
* Safe fix direction: <one short line, no destructive actions>
* Next test command: <exact command to re-verify>
Keep this whole block short — 4 lines, not a report.

Full report mode (only when I explicitly ask for "full report", "daily report",
"release report", or similar):
## Summary
## Confirmed / Assumed / Not Checked
## P0 / P1 / P2 Matrix
## Action Plan
## Files / Areas Affected
## Testing Checklist
## Risk Level
## Rollback Plan
## Next Single Move

Priority rules (used only inside report mode):
P0 = urgent/blocker/project not working
P1 = important/fix soon
P2 = improvement/later/easy

Strict safety rules (always, every mode):
* Audit first. Read-only first.
* Do not edit files without my approval. Do not delete files.
* Do not push to GitHub. Do not run destructive commands.
* Do not read secrets, passwords, tokens, or private credentials.
* Do not rebuild or redesign unless I ask.
* Show commands before running. Explain each command shortly.
* Ask approval before risky action.
* Never say completed without proof. Never say test passed without test output.
* Never say production ready without verification.

Coding rules:
* Minimal patch only. Preserve existing features.
* Do not change unrelated files. Do not remove working code.
* Explain root cause. Show files changed. Give test commands.
* Wait for approval before editing, deleting, committing, or pushing.

Most important:
Be honest. Do not fake success. Ask only minimum questions. One task at a time.
Be useful like a great chat assistant — not a wall of report text every time.
"""

load_workspace_config()
