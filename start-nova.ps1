#!/usr/bin/env pwsh
# Start NOVA backend and frontend services

$RootDir = Get-Location
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$LogsDir = Join-Path $BackendDir ".logs"

New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

Write-Host "Starting NOVA..." -ForegroundColor Cyan

# Stop previous instances
try {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "vite" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
} catch { }

# Start backend
$backendProcess = Start-Process `
    -FilePath "python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $BackendDir `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $LogsDir "backend_stdout.log") `
    -RedirectStandardError (Join-Path $LogsDir "backend_stderr.log")

if ($backendProcess) {
    Write-Host "Backend started (PID: $($backendProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "Failed to start backend" -ForegroundColor Red
}

Start-Sleep -Seconds 2

# Start frontend
$frontendProcess = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run dev" `
    -WorkingDirectory $FrontendDir `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $LogsDir "frontend_stdout.log") `
    -RedirectStandardError (Join-Path $LogsDir "frontend_stderr.log")

if ($frontendProcess) {
    Write-Host "Frontend started (PID: $($frontendProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "Failed to start frontend" -ForegroundColor Red
}

Write-Host ""
Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Yellow
Write-Host "Logs:     $LogsDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop: Get-Process python,node | Stop-Process" -ForegroundColor Gray
