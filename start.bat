@echo off
chcp 936 >nul
setlocal

set PROJECT_DIR=%~dp0
set BACKEND_PORT=8000
set FRONTEND_PORT=5173

echo.
echo ================================================
echo     2026Nian 8Yue Tian Qi Yu Bao Ke Shi Hua -- Qi Dong
echo ================================================
echo.

netstat -ano 2>nul | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [WARNING] Port %BACKEND_PORT% in use, run stop.bat first
    echo.
)

echo [1/2] Starting FastAPI backend (port %BACKEND_PORT%)...
start "Weather-Backend" /MIN cmd /c "cd /d "%PROJECT_DIR%" && python -m uvicorn main:app --host 127.0.0.1 --port %BACKEND_PORT%"

echo [2/2] Starting Vite frontend (port %FRONTEND_PORT%)...
start "Weather-Frontend" /MIN cmd /c "cd /d "%PROJECT_DIR%" && npx vite --host 127.0.0.1 --port %FRONTEND_PORT% --strictPort"

echo.
echo Waiting for services...
timeout /t 5 >nul

netstat -ano 2>nul | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (echo   [OK] Backend ready) else (echo   [..] Backend starting...)

netstat -ano 2>nul | findstr ":%FRONTEND_PORT% " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (echo   [OK] Frontend ready) else (echo   [..] Frontend starting...)

echo.
echo ================================================
echo   Startup complete!
echo   --------------------------------------------
echo   Frontend: http://127.0.0.1:5173
echo   Backend:  http://127.0.0.1:8000
echo   API docs: http://127.0.0.1:8000/docs
echo   --------------------------------------------
echo   Double-click stop.bat to stop all services
echo ================================================
echo.
echo Press any key to close...
pause >nul
