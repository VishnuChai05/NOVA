#!/usr/bin/env pwsh
# Start NOVA backend and frontend services

$RootDir = Get-Location
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$LogsDir = Join-Path $BackendDir ".logs"
$VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python.exe" }

New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

Write-Host "Starting NOVA..." -ForegroundColor Cyan

# Stop previous instances
try {
    Get-CimInstance Win32_Process -Filter "name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "uvicorn\s+app.main:app|app.workers.rq_worker" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-CimInstance Win32_Process -Filter "name = 'node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "vite|npm\s+run\s+dev" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 500
} catch { }

# Apply database migrations before starting services.
try {
    Write-Host "Running database migrations..." -ForegroundColor Cyan
    $migrationProcess = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList "-m app.db.migrate_startup" `
        -WorkingDirectory $BackendDir `
        -PassThru `
        -Wait `
        -NoNewWindow

    if ($migrationProcess.ExitCode -eq 0) {
        Write-Host "Database migrations completed" -ForegroundColor Green
    } else {
        Write-Host "Database migrations failed with exit code $($migrationProcess.ExitCode)" -ForegroundColor Red
        exit $migrationProcess.ExitCode
    }
} catch {
    Write-Host "Database migrations failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Start backend
$backendProcess = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -RedirectStandardOutput (Join-Path $LogsDir "backend_stdout.log") `
    -RedirectStandardError (Join-Path $LogsDir "backend_stderr.log")

if ($backendProcess) {
    Write-Host "Backend started (PID: $($backendProcess.Id))" -ForegroundColor Green
    Write-Host "Backend Python: $PythonExe" -ForegroundColor DarkGray
} else {
    Write-Host "Failed to start backend" -ForegroundColor Red
}

Start-Sleep -Seconds 2

# Start worker (only when local Redis is available)
$workerProcess = $null
$redisReady = $false
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect("127.0.0.1", 6379, $null, $null)
    $redisReady = $iar.AsyncWaitHandle.WaitOne(300)
    if ($redisReady -and $client.Connected) {
        $client.EndConnect($iar)
    } else {
        $redisReady = $false
    }
    $client.Close()
} catch {
    $redisReady = $false
}

if ($redisReady) {
    $workerProcess = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList "-m app.workers.rq_worker" `
        -WorkingDirectory $BackendDir `
        -PassThru `
        -RedirectStandardOutput (Join-Path $LogsDir "worker_stdout.log") `
        -RedirectStandardError (Join-Path $LogsDir "worker_stderr.log")

    if ($workerProcess) {
        Write-Host "Worker started (PID: $($workerProcess.Id))" -ForegroundColor Green
    }
} else {
}

# Start frontend
$frontendProcess = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run dev" `
    -WorkingDirectory $FrontendDir `
    -PassThru `
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
Write-Host "Worker:   app.workers.rq_worker" -ForegroundColor Yellow
Write-Host "Logs:     $LogsDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop: Get-Process python,node | Stop-Process" -ForegroundColor Gray
