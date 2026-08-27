@echo off
echo =======================================================
echo AI AssemblyTwin — Startup Script
echo =======================================================

echo.
echo [1/3] Checking dependencies...
python -c "import simpy, fastapi, websockets, torch, sklearn, pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing backend dependencies...
    cd backend
    pip install -r requirements.txt
    cd ..
)

echo.
echo [2/3] Starting FastAPI Backend...
cd backend
start "AI AssemblyTwin Backend" cmd /c "uvicorn main:app --reload --port 8000"
cd ..

echo.
echo [3/3] Starting Next.js Frontend...
cd frontend
if not exist node_modules (
    echo Installing frontend dependencies...
    npm install
)
start "AI AssemblyTwin Frontend" cmd /c "npm run dev -- -p 3000"
cd ..

echo.
echo =======================================================
echo Services started!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo =======================================================
pause
