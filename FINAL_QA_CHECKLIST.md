# AGENT ALINE X — Final QA Checklist (v3.1 / P7)

Run these in order. All commands are safe (read-only or explicitly approved-safe).
Check items off only after seeing the actual output — never mark PASS without proof.

---

## 1. Backend compile
```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m py_compile backend_bridge.py agent_tools.py agent_config.py project_memory.py test_safety.py
```
- [ ] Exit code 0, no output (silence = success for `py_compile`)

## 2. Pytest (full suite)
```powershell
cd D:\AGENT_ALINE_X_
py -3.11 -m pytest -q
```
- [ ] All tests pass, no `--ignore` flags needed (pytest.ini handles backup exclusion)
- [ ] Count is ≥ 68 (65 pre-P7 + 3 new P7 tests)

## 3. Frontend build
```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd run build
```
- [ ] `tsc && vite build` completes with no TypeScript errors
- [ ] `dist/` output produced

## 4. Health endpoint
```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/health
```
- [ ] `backend: ok`
- [ ] `ollama: ok` (or `error` if Ollama isn't running — note this, don't fail QA for it)
- [ ] `patch_mode: off`

## 5. Memory reindex
```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/memory/reindex
```
- [ ] Returns `indexed_files` / `indexed_chunks` counts
- [ ] No error field, or a clear `retrieval_mode: keyword` fallback if Ollama embedding is offline

## 6. Memory search
```powershell
Invoke-RestMethod "http://127.0.0.1:8787/api/memory/search?q=model%20router"
```
- [ ] Returns `results` with at least one match for a known term (e.g. "model router")
- [ ] `backend_bridge.py` ranks at or near the top for implementation-style queries

## 7. Chat memory query (via UI or curl)
Ask: `Search project memory for model router and explain files involved`
- [ ] Response names the actual file(s) involved (e.g. `backend_bridge.py`)
- [ ] No hallucinated file names not present in the project

## 8. Command planner — safe / caution / blocked
```powershell
# Safe
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" `
  -Body '{"command":"py -3.11 -m pytest -q","dry_run":true}'

# Caution
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" `
  -Body '{"command":"py -3.11 -m pip install pytest","dry_run":true}'

# Blocked
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/commands/plan `
  -ContentType "application/json" `
  -Body '{"command":"Remove-Item -Recurse -Force D:\\AGENT_ALINE_X_\\*","dry_run":true}'
```
- [ ] Safe → `risk_level: safe`, `allowed: true`, `requires_confirmation: false`
- [ ] Caution → `risk_level: caution`, `allowed: true`, `requires_confirmation: true`
- [ ] Blocked → `risk_level: blocked`, `allowed: false` — and confirm the command never executes

## 9. Release status endpoint (P7)
```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/release/status
```
- [ ] `version: v3.1`
- [ ] `release_stage: P7 Final QA`
- [ ] `completed_phases` includes P0 through P6.1
- [ ] `command_planner_enabled: true`
- [ ] `patch_mode: off`
- [ ] Response returns in well under 1 second (no heavy calls)

---

## Sign-off

| Check | Result | Notes |
|---|---|---|
| Backend compile | | |
| Pytest | | |
| Frontend build | | |
| Health endpoint | | |
| Memory reindex | | |
| Memory search | | |
| Chat memory query | | |
| Command planner (safe/caution/blocked) | | |
| Release status endpoint | | |

**Overall verdict:** ______________________

*Do not mark "READY" or "production ready" without every row above showing actual
verified output, not assumption.*
