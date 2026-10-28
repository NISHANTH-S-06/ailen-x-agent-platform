# RUN_AGENT_UI.ps1
# ─────────────────────────────────────────────────────────────────────────────
# AGENT ALINE X  |  Streamlit UI Launcher
# ─────────────────────────────────────────────────────────────────────────────
# Usage:
#   Open PowerShell in D:\AGENT_ALINE_X_
#   .\RUN_AGENT_UI.ps1
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AGENT ALINE X  |  Local Safe Project Agent UI" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Verify Python ──────────────────────────────────────────────────
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    Write-Host "      Found: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Python not found. Install Python 3.9+ and retry." -ForegroundColor Red
    exit 1
}

# ── Step 2: Install / verify requirements ─────────────────────────────────
Write-Host "[2/4] Installing requirements (streamlit)..." -ForegroundColor Yellow
python -m pip install -r .\requirements-agent-ui.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ERROR: pip install failed." -ForegroundColor Red
    exit 1
}
Write-Host "      Requirements OK." -ForegroundColor Green

# ── Step 3: Syntax check ──────────────────────────────────────────────────
Write-Host "[3/4] Syntax checking agent_ui.py..." -ForegroundColor Yellow
python -m py_compile .\agent_ui.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ERROR: Syntax error in agent_ui.py" -ForegroundColor Red
    exit 1
}
python -m py_compile .\agent_tools.py
python -m py_compile .\agent_config.py
Write-Host "      Syntax OK." -ForegroundColor Green

# ── Step 4: Launch Streamlit ──────────────────────────────────────────────
Write-Host "[4/4] Launching Streamlit..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  UI will open at: http://localhost:8501" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C here to stop the server." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Safety mode: Read-Only + Safe Commands Only" -ForegroundColor DarkYellow
Write-Host "  Allowed roots:" -ForegroundColor DarkYellow
Write-Host "    D:\AGENT_ALINE_X_" -ForegroundColor DarkYellow
Write-Host "    D:\OCR_MASTER\ocr-platform-complete" -ForegroundColor DarkYellow
Write-Host ""

python -m streamlit run .\agent_ui.py --server.port 8501 --server.headless false
