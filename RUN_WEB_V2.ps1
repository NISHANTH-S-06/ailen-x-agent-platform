# RUN_WEB_V2.ps1 - AGENT ALINE X Web launcher
$ErrorActionPreference = "Stop"

$RootDir = "D:\AGENT_ALINE_X_"
$FrontendDir = "D:\AGENT_ALINE_X_\frontend"

function Get-EnvConfig {
    $envPath = Join-Path $RootDir ".env"
    $config = @{ BACKEND_PORT = "8100"; FRONTEND_PORT = "3100" }
    if (Test-Path $envPath) {
        Get-Content $envPath | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $parts = $line.Split("=", 2)
                $config[$parts[0].Trim()] = $parts[1].Trim()
            }
        }
    }
    return $config
}

$envConfig = Get-EnvConfig
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { $envConfig["BACKEND_PORT"] }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { $envConfig["FRONTEND_PORT"] }

function Test-PortInUse($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

Write-Host "=== AGENT ALINE X Web Launcher ===" -ForegroundColor Cyan
Write-Host "Backend Port:  $BackendPort" -ForegroundColor Gray
Write-Host "Frontend Port: $FrontendPort" -ForegroundColor Gray

# Check Backend
if (Test-PortInUse $BackendPort) {
    Write-Host "Backend already running on http://127.0.0.1:$BackendPort" -ForegroundColor Yellow
} else {
    Write-Host "Starting backend bridge on http://127.0.0.1:$BackendPort ..." -ForegroundColor Green
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd `"$RootDir`"; py -3.11 -m uvicorn backend_bridge:app --host 127.0.0.1 --port $BackendPort" -WindowStyle Minimized
}

# Check Frontend
if (Test-PortInUse $FrontendPort) {
    Write-Host "Frontend already running on http://127.0.0.1:$FrontendPort" -ForegroundColor Yellow
} else {
    Write-Host "Starting frontend dev server on http://127.0.0.1:$FrontendPort ..." -ForegroundColor Green
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd `"$FrontendDir`"; npm.cmd run dev" -WindowStyle Minimized
}

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Backend health: http://127.0.0.1:$BackendPort/api/health" -ForegroundColor Cyan
Write-Host "Frontend UI:     http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
Write-Host ""
