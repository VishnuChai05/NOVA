@echo off
color 0B
echo =======================================
echo         STARTING NOVA PLATFORM
echo =======================================
echo.

echo [1/3] Starting Backend API (FastAPI)...
start "NOVA Backend API" cmd /k "cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/3] Starting Background Worker (RQ)...
start "NOVA RQ Worker" cmd /k "cd backend && ..\.venv\Scripts\python.exe -m app.workers.rq_worker"

echo [3/3] Starting Frontend (React)...
start "NOVA Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo =======================================
echo   All services launched in new windows!
echo   You can close this window now.
echo =======================================
pause
