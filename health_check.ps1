# health_check.ps1 - Health check endpoint verification for AGENT ALINE X
$ErrorActionPreference = "Stop"

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

$healthUrl = "http://127.0.0.1:$BackendPort/api/health"

Write-Host "Checking AGENT ALINE X health at $healthUrl ..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "HTTP Status: 200 OK" -ForegroundColor Green
        Write-Host "Response Body:" -ForegroundColor Cyan
        $response.Content | Write-Host -ForegroundColor White
        Write-Host "`nHealth check PASSED!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "HTTP Status: $($response.StatusCode)" -ForegroundColor Red
        Write-Host "Response Body: $($response.Content)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Health check FAILED: Unable to reach $healthUrl" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
