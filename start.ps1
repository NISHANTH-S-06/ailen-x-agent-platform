# start.ps1 - Start AGENT ALINE X backend bridge and frontend
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

Write-Host "=== Starting AGENT ALINE X Services ===" -ForegroundColor Cyan
Write-Host "Backend Port:  $BackendPort" -ForegroundColor Gray
Write-Host "Frontend Port: $FrontendPort" -ForegroundColor Gray

# Clear existing processes if running
& "$RootDir\stop.ps1" | Out-Null
Start-Sleep -Seconds 1

# Start Backend via Win32_Process
Write-Host "Starting backend bridge on http://127.0.0.1:$BackendPort ..." -ForegroundColor Green
$bCmd = "py -3.11 -m uvicorn backend_bridge:app --host 127.0.0.1 --port $BackendPort"
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $bCmd
    CurrentDirectory = $RootDir
} | Out-Null

# Start Frontend via Win32_Process
Write-Host "Starting frontend dev server on http://127.0.0.1:$FrontendPort ..." -ForegroundColor Green
$fCmd = "cmd.exe /c npm run dev -- --port $FrontendPort --host 127.0.0.1"
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $fCmd
    CurrentDirectory = $FrontendDir
} | Out-Null

Start-Sleep -Seconds 4

Write-Host ""
Write-Host "Services started!" -ForegroundColor Green
Write-Host "Backend Health Endpoint: http://127.0.0.1:$BackendPort/api/health" -ForegroundColor Cyan
Write-Host "Frontend Interface:      http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
Write-Host ""
