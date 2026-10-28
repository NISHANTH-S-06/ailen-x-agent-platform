# stop.ps1 - Stop AGENT ALINE X backend and frontend services
$ErrorActionPreference = "SilentlyContinue"

$RootDir = "D:\AGENT_ALINE_X_"

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

Write-Host "=== Stopping AGENT ALINE X Services ===" -ForegroundColor Yellow

$ports = @([int]$BackendPort, [int]$FrontendPort)
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            $targetPid = $conn.OwningProcess
            Write-Host "Stopping process $targetPid listening on port $port..." -ForegroundColor Cyan
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "No active process listening on port $port." -ForegroundColor Gray
    }
}

Write-Host "Stopped all AGENT ALINE X services." -ForegroundColor Green
