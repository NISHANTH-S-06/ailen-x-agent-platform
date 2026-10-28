# AGENT ALINE X — RUN COMMANDS

**Version:** v3.1 (P7 Final QA / Release Candidate) | **Updated:** 2026-07-01
All commands are safe PowerShell commands. Run in **Windows PowerShell**.

Current stack: **FastAPI backend bridge** (`backend_bridge.py`) + **React/Vite frontend**
(`frontend/`) + local **Ollama**. This replaces the earlier Open WebUI/Docker setup —
see `backup_before_p7_final_qa_release\RUN_COMMANDS.md` for the old Docker-based version.

Environment notes:
- Use Python via `py -3.11` (do not assume `python` alone resolves to 3.11).
- Use npm via `npm.cmd` (not bare `npm`) on this machine.
- Do not assume a `.venv` exists.
- Do not assume `requirements.txt` exists — use `requirements-bridge.txt`.

---

## DAILY STARTUP

### Step 1 — Check Ollama
```powershell
ollama list
```
Expected: `qwen2.5-coder:7b`, `agent-aline-x:latest` listed (or similar).

### Step 2 — Start backend bridge
```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m uvicorn backend_bridge:app --host 127.0.0.1 --port 8787 --reload
```

### Step 3 — Start frontend (separate terminal)
```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd run dev
```

### Step 4 — Open Browser
```powershell
Start-Process "http://127.0.0.1:5173"
```

Or use the combined launcher:
```powershell
cd D:\AGENT_ALINE_X_
.\RUN_WEB_V2.ps1
```

---

## BACKEND TESTS

```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m pytest -q
```
Expected: all tests pass (65+ as of P6.1/P7).

## BACKEND COMPILE CHECK

```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m py_compile backend_bridge.py agent_tools.py agent_config.py project_memory.py test_safety.py
```

## FRONTEND BUILD

```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd run build
```

---

## HEALTH / STATUS CHECKS

```powershell
# Backend + Ollama health
Invoke-RestMethod http://127.0.0.1:8787/api/health

# Final release / QA status snapshot (P7)
Invoke-RestMethod http://127.0.0.1:8787/api/release/status

# QA snapshot (P6)
Invoke-RestMethod http://127.0.0.1:8787/api/qa/snapshot
```

---

## MEMORY REINDEX / SEARCH SMOKE

```powershell
# Rebuild the project memory index (writes .agent_memory/index.json)
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/memory/reindex

# Search the memory index
Invoke-RestMethod "http://127.0.0.1:8787/api/memory/search?q=model%20router"
```

---

## COMMAND PLANNER SMOKE (P6)

```powershell
# Safe command — expect risk_level: safe, allowed: true
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" `
  -Body '{"command":"py -3.11 -m pytest -q","cwd":"D:\\AGENT_ALINE_X_","dry_run":true}'

# Caution command — expect risk_level: caution, requires_confirmation: true
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" `
  -Body '{"command":"py -3.11 -m pip install pytest","cwd":"D:\\AGENT_ALINE_X_","dry_run":true}'

# Blocked command — expect risk_level: blocked, allowed: false
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" `
  -Body '{"command":"Remove-Item -Recurse -Force D:\\AGENT_ALINE_X_\\*","cwd":"D:\\AGENT_ALINE_X_","dry_run":true}'
```

---

## MODEL CHECKS

```powershell
# Check Ollama version
ollama --version

# List all downloaded models
ollama list

# Pull primary model
ollama pull qwen2.5-coder:7b

# Pull fallback model
ollama pull llama3
```

---

## TROUBLESHOOTING

```powershell
# Backend not responding?
Invoke-RestMethod http://127.0.0.1:8787/api/health

# Ollama not responding?
ollama list
ollama serve   # Run manually if needed

# Port conflict on 8787 or 5173?
netstat -ano | findstr :8787
netstat -ano | findstr :5173
tasklist | findstr <PID>   # Replace <PID> with actual PID number
```

---

## LEGACY / ARCHIVED

The original Open WebUI + Docker workflow (`docker start open-webui`, port 3001) is
retired for this project. The Modelfile-based custom model creation step still applies
if `agent-aline-x` needs to be (re)built:

```powershell
# DO NOT RUN without user approval
ollama create agent-aline-x -f "D:\AGENT_ALINE_X_\Modelfile.agent-aline-x"
ollama list | findstr agent-aline-x
```

---

*Project: AGENT ALINE X | v3.1 P7 Final QA | Last updated: 2026-07-01*
