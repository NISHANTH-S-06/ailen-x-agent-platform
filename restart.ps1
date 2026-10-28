# restart.ps1 - Restart AGENT ALINE X backend and frontend services
$ErrorActionPreference = "Stop"

$RootDir = "D:\AGENT_ALINE_X_"

Write-Host "=== Restarting AGENT ALINE X Services ===" -ForegroundColor Yellow

& "$RootDir\stop.ps1"
Start-Sleep -Seconds 2
& "$RootDir\start.ps1"
