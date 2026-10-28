import json
import urllib.request
import subprocess
from pathlib import Path

MODEL = "agent-aline-x"
OLLAMA_URL = "http://localhost:11434/api/chat"

ALLOWED_ROOTS = [
    Path("D:/AGENT_ALINE_X_").resolve(),
    Path("D:/OCR_MASTER/ocr-platform-complete").resolve(),
]

context_chunks = []


def is_allowed(path: Path) -> bool:
    path_str = str(path.resolve()).lower()
    return any(path_str.startswith(str(root).lower()) for root in ALLOWED_ROOTS)


def safe_path(raw: str) -> Path:
    p = Path(raw.strip().strip('"'))
    if not p.is_absolute():
        p = (Path.cwd() / p)
    p = p.resolve()

    if not is_allowed(p):
        raise PermissionError(f"Blocked path: {p}")

    return p


def ollama_chat(user_text: str) -> str:
    local_context = "\n\n--- LOCAL CONTEXT ---\n\n".join(context_chunks[-8:])

    system_text = """
You are AGENT ALINE X, Nishanth's safe local project agent.

STRICT GROUNDING RULES:
- Use ONLY the provided LOCAL CONTEXT.
- Do not give generic advice.
- Do not invent project status, test counts, files changed, git status, or risks.
- If exact evidence is not in LOCAL CONTEXT, write: Not Checked.
- When auditing a file, mention only risks visible in the provided file lines.
- If only partial file content is provided, say "partial file only checked".
- Never suggest commit, push, delete, Docker, or Open WebUI unless user explicitly asks.
- Give one safe next step only.
- Use Tanglish or English.

Required format:
1. Confirmed
2. Not Checked
3. Risk visible from context
4. Safe next step only
"""

    full_user_text = user_text
    if local_context:
        full_user_text = f"""
LOCAL CONTEXT:
{local_context}

USER QUESTION:
{user_text}
"""

    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": full_user_text},
        ],
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=300) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["message"]["content"]


def cmd_roots():
    print("\nAllowed folders:")
    for r in ALLOWED_ROOTS:
        print(f" - {r}")


def cmd_ls(arg: str):
    p = safe_path(arg or ".")
    if not p.exists():
        print(f"Not found: {p}")
        return

    if p.is_file():
        print(f"{p}  ({p.stat().st_size} bytes)")
        return

    for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        kind = "DIR " if item.is_dir() else "FILE"
        size = "" if item.is_dir() else f"{item.stat().st_size} bytes"
        print(f"{kind}  {item.name} {size}")


def cmd_read(arg: str):
    parts = arg.rsplit(" ", 1)
    file_arg = arg
    max_lines = 200

    if len(parts) == 2 and parts[1].isdigit():
        file_arg = parts[0]
        max_lines = int(parts[1])

    p = safe_path(file_arg)
    if not p.exists() or not p.is_file():
        print(f"File not found: {p}")
        return

    text = p.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    for i, line in enumerate(lines[:max_lines], start=1):
        print(f"{i:04d}: {line}")

    if len(lines) > max_lines:
        print(f"\n... truncated. Total lines: {len(lines)}")


def cmd_add(arg: str):
    parts = arg.rsplit(" ", 1)
    file_arg = arg
    max_lines = 300

    if len(parts) == 2 and parts[1].isdigit():
        file_arg = parts[0]
        max_lines = int(parts[1])

    p = safe_path(file_arg)
    if not p.exists() or not p.is_file():
        print(f"File not found: {p}")
        return

    text = p.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()[:max_lines]
    chunk = f"FILE: {p}\n" + "\n".join(lines)
    context_chunks.append(chunk)
    print(f"Added to context: {p} ({len(lines)} lines)")

def cmd_run(arg: str):
    commands = {
        "git-status": {
            "cwd": "D:/OCR_MASTER/ocr-platform-complete",
            "cmd": ["git", "status", "--short"],
        },
        "git-diff": {
            "cwd": "D:/OCR_MASTER/ocr-platform-complete",
            "cmd": ["git", "diff", "--stat"],
        },
        "compile": {
            "cwd": "D:/OCR_MASTER/ocr-platform-complete",
            "cmd": ["python", "-m", "compileall", "app"],
        },
        "pytest": {
            "cwd": "D:/OCR_MASTER/ocr-platform-complete",
            "cmd": [".venv311/Scripts/python.exe", "-m", "pytest", "-q"],
        },
        "frontend-check": {
            "cwd": "D:/OCR_MASTER/ocr-platform-complete",
            "cmd": ["node", "tests/check_js.js"],
        },
        "backend-health": {
            "cwd": "D:/OCR_MASTER/ocr-platform-complete",
            "cmd": ["curl.exe", "http://127.0.0.1:8000/api/v1/health"],
        },
    }

    key = arg.strip()
    if key not in commands:
        print("Blocked. Allowed commands:")
        for name in commands:
            print(f" - /run {name}")
        return

    spec = commands[key]
    print(f"Running safe command: {key}")
    print(f"CWD: {spec['cwd']}")
    print("CMD:", " ".join(spec["cmd"]))

    result = subprocess.run(
        spec["cmd"],
        cwd=spec["cwd"],
        text=True,
        capture_output=True,
        timeout=300,
        shell=False,
    )

    output = ""
    if result.stdout:
        output += "STDOUT:\n" + result.stdout
    if result.stderr:
        output += "\nSTDERR:\n" + result.stderr

    print(output[:8000])
    if len(output) > 8000:
        print("\n... output truncated ...")

    context_chunks.append(
        f"COMMAND RESULT: /run {key}\nExit code: {result.returncode}\n{output[:8000]}"
    )

def help_text():
    print("""
AGENT ALINE X Local File Agent

Commands:
  /roots                         Show allowed folders
  /ls <folder>                    List files
  /read <file> [lines]            Read file safely
  /add <file> [lines]             Add file content to agent context
  /clearctx                       Clear added context
  /ask <question>                 Ask agent using added context
  /exit                           Exit
  /run <safe-command>             Run safe project checks
Safety:
  Read-only mode.
  Allowed only:
    D:\\AGENT_ALINE_X_
    D:\\OCR_MASTER\\ocr-platform-complete
""")


def main():
    print("AGENT ALINE X local file agent ready.")
    help_text()

    while True:
        try:
            user = input("\nagent> ").strip()
            if not user:
                continue

            if user == "/exit":
                break
            elif user == "/help":
                help_text()
            elif user == "/roots":
                cmd_roots()
            elif user.startswith("/ls"):
                cmd_ls(user[3:].strip())
            elif user.startswith("/read"):
                cmd_read(user[5:].strip())
            elif user.startswith("/add"):
                cmd_add(user[4:].strip())
            elif user.startswith("/run"):
                cmd_run(user[4:].strip())
            elif user == "/clearctx":
                context_chunks.clear()
                print("Context cleared.")
            elif user.startswith("/ask"):
                q = user[4:].strip()
                print("\n" + ollama_chat(q))
            else:
                print("\n" + ollama_chat(user))

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
