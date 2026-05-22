@echo off
title APEX Trading Bot Launcher
echo ===================================================
echo             APEX TRADING BOT - LAUNCHER
echo ===================================================
echo [INFO] Starting FastAPI Backend on http://127.0.0.1:8000...
start "APEX Backend (FastAPI)" cmd /k "PYTHONPATH=. uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload"

echo [INFO] Starting Vite Frontend...
start "APEX Frontend (Vite)" cmd /k "cd client && npm run dev"

echo [SUCCESS] Both servers are launching in separate windows!
echo - Backend API Docs: http://127.0.0.1:8000/docs
echo - Live Interactive Dashboard (Vite Dev): http://localhost:5173
echo ===================================================
echo Press any key to exit this launcher window...
pause > nul
