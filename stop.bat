@echo off
chcp 936 >nul
setlocal enabledelayedexpansion

set BACKEND_PORT=8000
set FRONTEND_PORT=5173
set KILLED=0

echo.
echo ================================================
echo     2026Nian 8Yue Tian Qi Yu Bao Ke Shi Hua -- Ting Zhi
echo ================================================
echo.

echo [1/2] Stopping backend (port %BACKEND_PORT%)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    echo   PID %%a killed
    set KILLED=1
)
if !KILLED! equ 0 echo   Port %BACKEND_PORT% not in use
set KILLED=0

echo [2/2] Stopping frontend (port %FRONTEND_PORT%)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
    echo   PID %%a killed
    set KILLED=1
)
if !KILLED! equ 0 echo   Port %FRONTEND_PORT% not in use

taskkill /FI "WINDOWTITLE eq Weather-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Weather-Frontend*" /F >nul 2>&1

echo.
echo ================================================
echo   All services stopped
echo ================================================
echo.
echo Press any key to close...
pause >nul
