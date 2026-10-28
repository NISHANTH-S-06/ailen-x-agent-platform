# AGENT ALINE X — Web v3.3

## What's new in v2.8 — Quick Mode Fast Patch

* **Quick mode timeout improved for real context.** Quick mode timeout raised
  from 20 seconds to 30 seconds (`RESPONSE_LENGTHS` in `backend_bridge.py`).
  This fixes the rare timeout seen when real file-range context is loaded and the
  model needs slightly longer to process it. `num_predict` stays at 120 (short
  answer) — only the timeout budget was widened. Balanced/Detailed unchanged.

---

## What's new in v2.7 — Agent Intelligence + Real Context Upgrade

This pass focused on making the agent's *answers* better, not new UI surface area —
the Workspace, Audit, Commands, and Safety pages are unchanged.

* **Direct answers by default.** The agent's system prompt (`agent_config.py`)
  now answers like a helpful chat assistant — short, direct, conversational —
  instead of dumping the full report template on every message. The big
  `## Summary / Confirmed-Assumed-Not Checked / P0-P1-P2 / ...` report format
  is only used when you explicitly ask for a "full report", "daily report",
  or "release report".
* **One safe next step.** Every answer ends with a single `Next: ...` line —
  one concrete move, not a list of options.
* **Context source citation.** When you add a file range to chat context (see
  below), the agent is instructed to name the source — e.g. "(from
  backend_bridge.py lines 210-240)" — when it actually uses that content, so
  you can tell a grounded answer from a guess.
* **Compact error analyzer.** If the active chat context contains a failed
  command result (non-zero exit code) or build/test error, the agent answers
  in a fixed 4-line format: Root cause (likely) → File → Safe fix direction →
  Next test command — instead of a long essay.
* **"Not checked yet" stays strict.** Project status / build / test / risk /
  git questions without loaded context still get exactly: *"Not checked yet.
  Run Quick Audit first."* — enforced both in the frontend (instant, no
  network call) and the backend (`needs_verified_context` check), so it can't
  drift even if one side changes later.
* **Quick / Balanced / Detailed actually changes the answer.** These map to
  different `num_predict` (response length) and timeout budgets on the
  backend (`RESPONSE_LENGTHS` in `backend_bridge.py`) — Quick is short and
  fast, Detailed allows a longer, more thorough answer.
* **Backend cleanup.** Removed a dead/unreachable duplicate code path inside
  `api_chat` in `backend_bridge.py` left over from an earlier version (the
  greeting/no-context guards were duplicated; only the first, reachable copy
  was ever used — the dead copy is now gone, behavior is unchanged).

### Add Range to Chat Context

In the Workspace tab, after reading a file range (Read Range button), click
**"Add to Chat Context"**. That exact range — file path + start/end line
numbers + the numbered lines themselves — is added as a labelled chunk (shown
as "N context" in the Chat header). Every chat message after that includes
those chunks as grounded evidence sent to the model, so the agent can answer
questions about that real file content instead of guessing. Use the same
button again on a different range to add more (oldest chunks are dropped
automatically once the context budget is hit).

### Quick / Balanced / Detailed

Pick the response length next to the chat input (or in Settings). Quick gives
a short, fast answer (good for yes/no or one-line checks). Balanced is the
default — a short paragraph or a few bullets. Detailed allows a longer answer
with more depth for genuinely multi-part questions, while still avoiding the
full report template unless you ask for a report by name.

### "Not checked yet" safety rule

If you ask about project status, build, test, git, audit, or risk *without*
having added any file-range context or run any safe command first, the agent
will not guess — it replies "Not checked yet. Run Quick Audit first." and
stops. Run Quick Audit (or add relevant context) first, then ask again.

### Manual QA checklist for v2.7

- [ ] Chat "Hi" → friendly greeting, Fast badge, no network call needed.
- [ ] Chat "project status?" with zero context → "Not checked yet. Run Quick
      Audit first."
- [ ] Workspace → open `README_WEB_V2.md`, Read Range 1-40, click "Add to Chat
      Context" → context badge count increases.
- [ ] Chat → ask the agent to explain that context → answer references the
      file/lines and ends with a `Next:` line, stays short (not a giant report).
- [ ] Run Full Safe Audit → all 6 steps complete, health rating shown.
- [ ] Workspace path input → `C:\` → blocked with a clear message.
- [ ] Workspace path input → `.env` style path → blocked with a clear message.
- [ ] Ask explicitly "give me a full report" → agent switches to the full
      `## Summary / ...` report template.

## Project Structure

The verified, clean workspace root is structured as follows:

```
D:\AGENT_ALINE_X_
├── frontend/                            # React + TypeScript + Vite frontend
│   ├── src/                             # App components and logic
│   ├── package.json                     # Frontend dependencies
│   ├── vite.config.ts                   # Vite configuration
│   └── tailwind.config.ts               # Tailwind CSS configuration
├── _FINAL_BACKUP_BEFORE_PROFESSIONAL_CLEANUP/  # Complete master backup of active files
├── _ARCHIVE_OLD_ARTIFACTS/              # Archived duplicate folders & old backups
├── backend_bridge.py                    # Local FastAPI bridge service
├── requirements-bridge.txt              # Backend dependencies
├── RUN_WEB_V2.ps1                       # Unified launch script (Clean ASCII)
├── README_WEB_V2.md                     # This documentation file
├── agent_config.py                      # Central agent config (Safety list, models)
├── agent_tools.py                       # Core safe operations (Path validation, secret blocking)
├── agent_ui.py                          # Legacy Streamlit UI script
├── local_agent.py                       # Local terminal-based agent script
└── RUN_AGENT_UI.ps1                     # Legacy Streamlit launcher script
```

---

## How to Start

### Option A — One Command (Recommended)

Run the unified, ASCII-safe launcher script from the root folder:

```powershell
cd D:\AGENT_ALINE_X_
.\RUN_WEB_V2.ps1
```

This checks if the ports are already in use. If a port is free, it starts the service in a separate PowerShell window.

### Option B — Manual Start (Two Terminals)

**Terminal 1 — Backend Bridge:**
```powershell
cd D:\AGENT_ALINE_X_
python -m uvicorn backend_bridge:app --host 127.0.0.1 --port 8787
```

**Terminal 2 — Frontend App:**
```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd run dev
```

Open `http://localhost:5173` in a web browser.

---

## Web URLs

| Service | URL |
|---|---|
| Frontend UI | http://localhost:5173 |
| Backend Bridge | http://127.0.0.1:8787 |
| Bridge Health | http://127.0.0.1:8787/api/health |
| Models List | http://127.0.0.1:8787/api/models |

---

## API Endpoint List

The backend bridge exposes the following REST API endpoints (restricted to Local CORS):

### 1. GET `/api/health`
Checks FastAPI status and Ollama connectivity status.
- **Response**: `{"backend": "ok", "ollama": "ok"|"error", "active_model": "...", "patch_mode": "off"}`

### 2. GET `/api/models`
Lists all Ollama models configured and whether they are pulled.
- **Response**: `{"models": [...], "default_model": "...", "ollama_reachable": true|false, "status_detail": "..."}`

### 3. POST `/api/chat`
Sends user prompt to Ollama with optional file context.
- **Payload**: `{"message": "...", "model": "...", "context": [], "response_length": "Balanced", "temperature": 0.1}`
- **Response**: `{"response": "...", "model": "...", "duration_ms": 0}`

### 4. POST `/api/commands/run`
Runs a pre-approved safe command.
- **Payload**: `{"command_id": "..."}`
- **Response**: `{"command_id": "...", "label": "...", "ok": true|false, "exit_code": 0, "output": "...", "duration_ms": 0}`

### 5. POST `/api/files/list`
Lists files in an allowed root directory.
- **Payload**: `{"path": "D:\\AGENT_ALINE_X_"}`
- **Response**: `{"entries": [{"name": "...", "type": "DIR"|"FILE", "size": 123, "locked": false}], "error": null}`

### 6. POST `/api/files/read-range`
Reads a line range from a file.
- **Payload**: `{"path": "...", "start": 1, "end": 80}`
- **Response**: `{"lines": [{"line": 1, "text": "..."}], "error": null, "path": "..."}`

### 7. POST `/api/audit/full`
Runs all 6 audit commands sequentially and computes a health rating.
- **Response**: `{"steps": [...], "pass": true|false, "duration_ms": 0, "health_rating": "Healthy"|"Needs Attention"|"Critical"}`

---

## Required Ollama Models

Pull these models to Ollama for full AI support:
- `qwen2.5-coder:7b` (Base coding model)
- `agent-aline-x` (Coding/project agent)
- `maxwellb/gemma4-12b-it-oym` (General reasoning)

Verify model availability with `/api/models` or `ollama list`.

---

## Safety Policy

- **No Writing/Patch Mode**: Patch Mode is hardcoded `OFF` (`PATCH_MODE = False`). No file edits are allowed via the web UI.
- **No Arbitrary Commands**: Only the 8 predefined command IDs are allowed (`git-status`, `git-diff-stat`, `git-diff-full`, `git-log-short`, `python-compile`, `pytest`, `frontend-build`, `backend-health`).
- **No Shell Execution**: Subprocess execution runs with `shell=False` and timeouts.
- **Secret Blocking**: Protected file patterns (`.env`, `id_rsa`, `known_hosts`, `credentials`, `token`, `password`) are blocked.
- **Root Whitelisting**: Access restricted to `D:\AGENT_ALINE_X_` and `D:\OCR_MASTER\ocr-platform-complete`. C:\ drive and user folders are blocked.
- **Secret Redaction**: Any line in command stdout/stderr containing `password`, `token`, `secret`, etc., is replaced with `[REDACTED LINE]`.

---

## Do Not Touch / Read-Only Areas

> [!WARNING]
> - Do not modify or write files to the OCR project directory: `D:\OCR_MASTER\ocr-platform-complete`. It is strictly read-only.
> - Do not write to any `C:\` drive directories.
> - Do not delete legacy config files (`agent_config.py`, `agent_tools.py`, `agent_ui.py`, etc.).
> - Do not perform destructive git operations (reset, clean, push).

---

## E2E Testing Checklist

### UI Sanity Checklist
- [ ] **Dashboard**: Default page, displays v3.3, theme looks clean, backend and Ollama badges display status, Patch Mode is OFF.
- [ ] **Chat**: Asking "Hi" or "Hello" returns an instant local greeting with the "Fast local answer" badge and duration.
- [ ] **Grounding Guard**: Project/build/test/git/risk status with no context returns "Not checked yet. Run Quick Audit first".
- [ ] **Response Modes**: Quick, Balanced, and Detailed chats return model answers with visible duration and the selected response length.
- [ ] **Workspace Explorer**: Able to load directory structure of `D:\AGENT_ALINE_X_`. Locked files (e.g. `.env`) are blocked from reading.
- [ ] **Range Reader**: Previewing `README_WEB_V2.md` from line 1 to 40 works and returns numbered lines.
- [ ] **Audit**: Running Full Safe Audit executes all steps and shows timeline and health rating.
- [ ] **Commands**: Predefined safe command cards run and show redacted logs. No free terminal text input exists.
- [ ] **Settings**: Test Active Model returns status and duration.
- [ ] **Safety Blocking**: `C:\` listing is blocked and `.env` range reads are blocked.

---

## Troubleshooting

- **Badge says "Bridge: offline (Mock Mode)"**: Backend bridge is not running on port 8787. Run `.\RUN_WEB_V2.ps1` or start manual uvicorn bridge.
- **Ollama badge is "Ollama: --"**: Ollama daemon is down or missing required models. Run `ollama serve`.
- **Port 8787 or 5173 in use**: Stop existing services manually. Launcher script skips starting services if ports are in use.

## Current Limitations

1. **Static Model List**: Available models list is hardcoded in config and requires manual addition to add new models.
2. **No File Patches**: Agent cannot modify files; write operations are disabled.
