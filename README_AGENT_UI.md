# AGENT ALINE X — Browser UI  v1.3

> **Professional local coding/project agent UI powered by Streamlit + Ollama**
> Updated: 2026-06-29

---

## 🚀 How to Run

### Option A — PowerShell Launcher (recommended)
```powershell
cd D:\AGENT_ALINE_X_
.\RUN_AGENT_UI.ps1
```

### Option B — Manual
```powershell
cd D:\AGENT_ALINE_X_
python -m pip install -r .\requirements-agent-ui.txt
streamlit run .\agent_ui.py
```

**Expected URL:** http://localhost:8501
Browser opens automatically. If not, navigate there manually.

---

## 📋 Files

| File | Purpose |
|------|---------|
| `agent_ui.py` | Main Streamlit UI — 6 tabs |
| `agent_config.py` | Central config: paths, commands, safety lists, system prompt |
| `agent_tools.py` | Core tools: path safety, file ops, subprocess, Ollama client |
| `requirements-agent-ui.txt` | Python deps (`streamlit>=1.35.0`) |
| `RUN_AGENT_UI.ps1` | One-click PowerShell launcher |
| `README_AGENT_UI.md` | This file |

---

## 🖥️ UI Tabs

| Tab | Purpose |
|-----|---------|
| 💬 Agent Chat | Chat with agent, context-grounded answers, quick prompts |
| ⚙️ Safe Commands | Pre-approved project checks with duration + exit code |
| 📂 File Explorer | List folders, read files, add to context. Secret files blocked. |
| 📋 Context | View/remove context chunks, size warnings |
| 🔎 Project Audit | One-click Quick / Test / Frontend audit workflows |
| 🛡️ Safety Panel | Live view of safety config, blocked paths, patch mode |

---

## 🛡️ Safety Rules

### ✅ Allowed Read Paths
- `D:\AGENT_ALINE_X_`
- `D:\OCR_MASTER\ocr-platform-complete`

### ✅ Allowed Write Path
- `D:\AGENT_ALINE_X_` only

### 🔒 Blocked Secret Files (v1.1 — NEW)
Even if a file exists under an allowed root, these are **never readable**:
- `.env`, `.env.local`, `.env.production`, `.env.development`
- `id_rsa`, `id_ed25519`, `id_ecdsa`, `id_dsa`
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`, `*.jks`
- `secrets.json`, `secrets.yaml`, `credentials.json`
- `token.json`, `service_account.json`, `.netrc`, `.pgpass`

In the file listing, blocked files show with a 🔒 indicator.

### 🚫 Blocked Paths
- `C:\` drive — entirely blocked
- `C:\Users\*` — all user profiles
- `*\Desktop\*`, `*\Downloads\*`, `*\Documents\*`, `*\AppData\*`
- `*.ssh\*`, `*\secrets\*`, `*\tokens\*`, `*\passwords\*`
- Any path not under allowed roots

### 🚫 Blocked Commands
- `git add`, `git commit`, `git push`, `git reset`, `git clean`
- `Remove-Item`, `rm`, `del`, `rmdir`, `format`
- `docker prune`, `docker rm`, `docker rmi`
- **No arbitrary command input** — UI has no free-form terminal

### 🔒 Patch Mode
- **OFF** — OCR project files are read-only
- Enable explicitly by editing `WRITE_ALLOWED_ROOTS` in `agent_config.py` (with approval)

---

## ⚙️ Allowed Safe Commands

| Key | Label | Command | Timeout |
|-----|-------|---------|---------|
| `git-status` | Git Status | `git status --short` | 30s |
| `git-diff-stat` | Git Diff Stat | `git diff --stat` | 30s |
| `git-diff-full` | Git Diff (Full) | `git diff HEAD` | 30s |
| `git-log-short` | Git Log (Last 10) | `git log --oneline -10` | 15s |
| `compile` | Python Compile | `python -m compileall app` | 60s |
| `pytest` | Pytest | `.venv311/Scripts/python.exe -m pytest -q` | 300s |
| `frontend-check` | Frontend JS Check | `node tests/check_js.js` | 60s |
| `backend-health` | Backend Health | `curl.exe http://127.0.0.1:8000/api/v1/health` | 15s |
| `list-ocr-root` | List OCR Root | `dir /B` | 10s |

All commands: `shell=False`, timeout enforced, stdout+stderr captured, output truncated at 8000 chars.
Results auto-added to agent context. Re-running replaces the previous result (no duplicate chunks).

---

## 🤖 Ollama & Models Integration

- **API:** `http://localhost:11434/api/chat`
- **Supported Models:**
  - `agent-aline-x` (Default fallback; custom base: `qwen2.5-coder:7b`)
  - `maxwellb/gemma4-12b-it-oym` (Stronger reasoning/general chat)
- **Active Model Selector:** Change the active model dynamically via the sidebar selector.
- **Performance Controls:** Customize temperature (default `0.1`) and token limits (`400` quick, `800` balanced, `1200` detailed) in the sidebar.
- **Model Testing:** Click the "Test Active Model" sidebar button to check latency/duration and verify responses without cluttering your project context chunks.

### Grounding & Chat Behavior

- **Greetings work without context:** Sending greetings like `Hi`, `Hello`, `Hey`, `Vanakkam`, `ready ah`, etc. returns a friendly greeting and guide without requiring command/file context.
- **Project queries require context:** For project-related queries (status, compile, git, tests, audit, risk), the agent enforces strict grounding. If context is empty, the agent outputs `“Not Checked — run Quick Audit or Safe Commands first.”`
- **Context limit:** The last 8 context chunks are sent per LLM call.

---

## 🔐 v1.1 Security Fixes

| Fix | Description |
|-----|-------------|
| XSS protection | All chat messages HTML-escaped via `html.escape()` before rendering |
| Secret file blocking | `.env`, keys, certs blocked in `read_file()` even under allowed roots |
| Filename blocking | `is_blocked_filename()` checks exact name + suffix patterns |
| File listing indicator | Blocked files shown as 🔒 in directory listing |
| Context deduplication | Re-running same command replaces old chunk (no spam) |
| File deduplication | Re-reading same file replaces old chunk |
| Context size warning | Warning shown when context exceeds 40,000 chars |
| MAX_CONTEXT_CHUNKS | Enforced: oldest chunk auto-dropped when limit exceeded |
| Model missing warning | Clear error if `agent-aline-x` model not found in Ollama |

---

## 📅 Daily Workflow

1. Open PowerShell → `cd D:\AGENT_ALINE_X_` → `.\RUN_AGENT_UI.ps1`
2. Browser opens at http://localhost:8501
3. Check **🟢 Ollama** and **🟢 model** badges at top
4. Go to **⚙️ Safe Commands** → click **Git Status** and **Python Compile**
5. Go to **📂 File Explorer** → read a key file if needed
6. Go to **💬 Agent Chat** → ask your question
7. Use **🔎 Project Audit** for one-click audit sequences
8. Use **📋 Context** tab to remove stale chunks between tasks

> **Load → Ask → Act.** Agent can only answer based on what you load.

---

## 🔧 Troubleshooting

### Ollama Offline badge
```powershell
ollama serve
```
Then click **🔄 Refresh Status** in the UI.

### Model not found (missing status)
```powershell
ollama list

# If agent-aline-x is missing:
ollama create agent-aline-x -f D:\AGENT_ALINE_X_\Modelfile.agent-aline-x

# If maxwellb/gemma4-12b-it-oym is missing:
ollama pull maxwellb/gemma4-12b-it-oym

# Verify model manually:
ollama run maxwellb/gemma4-12b-it-oym "Hi"
```

### Streamlit not installed
```powershell
python -m pip install streamlit
```

### Syntax error after editing
```powershell
python -m py_compile D:\AGENT_ALINE_X_\agent_config.py
python -m py_compile D:\AGENT_ALINE_X_\agent_tools.py
python -m py_compile D:\AGENT_ALINE_X_\agent_ui.py
```

### Port 8501 in use
```powershell
Get-Process -Name python | Stop-Process -Force
# Or:
streamlit run .\agent_ui.py --server.port 8502
```

### Pytest uses wrong Python
Ensure venv exists at `D:\OCR_MASTER\ocr-platform-complete\.venv311\`

---

## ✅ v1.1 Validation Checklist

Run after deployment:

| Check | How | Expected |
|-------|-----|----------|
| UI loads | Open http://localhost:8501 | Hero header visible |
| Ollama badge | Check header | 🟢 Ollama Online |
| Model badge | Check header | 🟢 agent-aline-x |
| Blocked path | File Explorer → enter `C:\Windows` | 🚫 BLOCKED error |
| Allowed path | File Explorer → enter `D:\OCR_MASTER\ocr-platform-complete` | Lists files |
| Secret file block | Read file → enter path to any `.env` file | 🔒 BLOCKED error |
| Secret file listing | List folder containing `.env` | Shows 🔒 indicator |
| Git Status | Safe Commands tab | Output in results panel |
| Context dedup | Click Git Status twice | Only 1 chunk in Context tab |
| Context warning | Add many file chunks | Warning when large |
| Empty context warning | Clear context → go to Chat | ℹ️ info banner shown |
| Quick Audit | Project Audit tab | 3-step progress, agent summary |
| XSS check | Chat: type `<script>alert(1)</script>` | Renders as escaped text, no alert |

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-06-24 | Initial release: 6-tab UI, safe commands, file explorer, context, audit, safety panel |
| v1.1 | 2026-06-29 | XSS fix, secret file blocking, cmd dedup, context size warning, model missing alert, MAX_CONTEXT_CHUNKS enforcement, duration display |
| v1.2 | 2026-06-29 | Git Diff Viewer, File Range Reader, Test Failure Analyzer, Export Audit Report, Full Safe Audit |
| v1.3 | 2026-06-29 | Multi-model support (agent-aline-x + gemma4-12b-it-oym), model selector sidebar, greeting fallback, temperature/num_predict controls, Test Active Model button |

---

*Project: AGENT ALINE X | v1.3 | 2026-06-29*
