# AGENT ALINE X v3.1

**Status:** Release Candidate — P7 Final QA | **Updated:** 2026-07-01
**Location:** `D:\AGENT_ALINE_X_\`

AGENT ALINE X is a fully local, private AI project agent for Windows. It runs
entirely on your machine via local Ollama models — no cloud, no internet
required after setup, no data leaves your PC.

---

## Current architecture

| Layer | Tech |
|---|---|
| Backend | FastAPI bridge (`backend_bridge.py`) |
| Frontend | React + Vite (`frontend/`) |
| Models | Local Ollama (dynamic discovery + fallback) |
| Memory | Project memory search (embedding + keyword fallback) |
| Safety | Command planner (safe / caution / blocked classification) |
| Status | Release status endpoint (`/api/release/status`) |

## Local URLs

- Backend: `http://127.0.0.1:8787`
- Frontend: `http://127.0.0.1:5173`

## Main features

- Multi-model router (routes chat prompts to code/audit/normal-chat models)
- Dynamic Ollama model discovery with automatic fallback
- Safe, validated workspace configuration (blocks drive roots, system folders)
- Performance metadata on every chat response (duration, route, fallback)
- Context trimming with per-mode character budgets (Quick/Balanced/Detailed)
- Explicit file context packing for chat (`selected_files`)
- Embedding-based project memory search with keyword fallback
- Production-first retrieval ranking (source files boosted, tests downranked
  unless the query is test-related)
- Command planner: every command is classified **safe** (auto-runs),
  **caution** (requires confirmation), or **blocked** (never runs)
- Read-only release status endpoint for QA visibility

## Required tools

- Python 3.11 (`py -3.11`)
- Node.js / npm (`npm.cmd`)
- Ollama (running locally)
- Windows PowerShell

---

## Start backend

```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m uvicorn backend_bridge:app --host 127.0.0.1 --port 8787 --reload
```

## Start frontend

```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd run dev
```

## Test backend

```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m pytest -q
```

## Build frontend

```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd run build
```

---

## Important smoke commands

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
Invoke-RestMethod http://127.0.0.1:8787/api/release/status
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/memory/reindex
Invoke-RestMethod "http://127.0.0.1:8787/api/memory/search?q=model%20router"
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" -Body '{"command":"py -3.11 -m pytest -q","dry_run":true}'
```

Full command reference: `RUN_COMMANDS.md`.

---

## Safety notes

- Commands are classified **safe / caution / blocked** before anything runs.
- **Caution** commands (e.g. `pip install`) require explicit confirmation.
- **Blocked** commands (e.g. `Remove-Item -Recurse -Force`, `git reset --hard`)
  never execute, regardless of confirmation.
- Only allowed workspace roots are ever read or written to.
- Secret-pattern files (`.env`, `*.pem`, credentials, tokens) are always blocked
  from listing/reading.
- No free-form terminal is exposed anywhere in the UI.
- Patch Mode is fixed OFF — no toggle exists.

## Release status

- **v3.1 — Release Candidate**
- Completed phases: P0, P1, P2, P3, P4, P5, P5.1, P5.2, P6, P6.1, P7
- Final manual QA required before production use — see `FINAL_QA_CHECKLIST.md`

---

## Project files

| File | Purpose |
|---|---|
| `README.md` | This file |
| `RUN_COMMANDS.md` | Full PowerShell command reference |
| `RELEASE_NOTES_v3.1.md` | Phase-by-phase release history (P0–P7) |
| `FINAL_QA_CHECKLIST.md` | Manual QA sign-off checklist |
| `release_info.json` | Machine-readable release metadata |
| `SAFETY_RULES.md` | Full safety rules |
| `backend_bridge.py` | FastAPI backend bridge |
| `agent_config.py` / `agent_tools.py` | Safety, workspace, and Ollama helpers |
| `project_memory.py` | Memory indexing/search engine |
| `test_safety.py` | Backend test suite |

---

*Project: AGENT ALINE X | v3.1 Release Candidate | Last updated: 2026-07-01*
