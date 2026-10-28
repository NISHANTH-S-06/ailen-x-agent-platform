# AGENT ALINE X — PORT STANDARDIZATION

**Project Name:** AGENT ALINE X  
**Version:** v3.3 Port Standardization  

This document defines the standardized port configuration for running AGENT ALINE X simultaneously alongside OCR, MCP, and AUTO QA platforms without port conflicts.

---

## 1. Port Assignments

| Component | Port | Host | Protocol | Description |
| --- | --- | --- | --- | --- |
| **Backend Bridge** | `8100` | `127.0.0.1` | HTTP / REST | FastAPI bridge server (`backend_bridge.py`) |
| **Frontend UI** | `3100` | `127.0.0.1` | HTTP | React / Vite web interface |
| **Ollama LLM Engine** | `11434` | `127.0.0.1` | HTTP | Local Ollama model server |
| **OCR Master Platform** | `8000` | `127.0.0.1` | HTTP | External OCR service |
| **MCP Server** | `8001` | `127.0.0.1` | HTTP | External Model Context Protocol server |
| **AUTO QA Testing** | `8200` | `127.0.0.1` | HTTP | External Automated QA suite |

---

## 2. Environment Variables

The project uses `.env` located at the root directory (`D:\AGENT_ALINE_X_\.env`) to avoid hardcoded ports:

```env
BACKEND_PORT=8100
FRONTEND_PORT=3100
```

- **Backend**: Python FastAPI auto-loads `.env` and defaults to `BACKEND_PORT=8100`.
- **Frontend**: Vite (`vite.config.ts`) and `apiClient.ts` dynamically evaluate `FRONTEND_PORT` and `BACKEND_PORT`.

---

## 3. Operations & Control Scripts

All control scripts auto-detect `.env` port settings.

### Start Services
Starts both backend (8100) and frontend (3100) in minimized processes:
```powershell
.\start.ps1
```

### Stop Services
Terminates processes listening on configured backend and frontend ports:
```powershell
.\stop.ps1
```

### Restart Services
Gracefully stops existing processes and launches fresh instances:
```powershell
.\restart.ps1
```

### Health Check
Queries `/api/health` and verifies HTTP 200 OK:
```powershell
.\health_check.ps1
```

---

## 4. Verification & Health Endpoint

- **Endpoint:** `GET http://127.0.0.1:8100/api/health`
- **Expected Status:** `HTTP 200 OK`
- **Response Format:**
```json
{
  "backend": "ok",
  "ollama": "ok",
  "active_model": "agent-aline-x:latest",
  "patch_mode": "off",
  "duration_ms": 15
}
```
