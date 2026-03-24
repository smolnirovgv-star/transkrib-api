@echo off
echo ============================================================
echo  Transkrib SmartCut AI - Dev Start
echo ============================================================
echo.

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "EWIN=%ROOT%platforms\desktop_windows"

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found in PATH.
    pause ^& exit /b 1
)

node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: node not found in PATH.
    pause ^& exit /b 1
)

if not exist "%BACKEND%\storage\logs" mkdir "%BACKEND%\storage\logs"

echo [1/2] Starting backend (port 8000)...
echo       Log: %BACKEND%\storage\logs\backend_dev.log
start "Transkrib-Backend" /min cmd /c "cd /d ""%BACKEND%"" ^&^& python standalone_server.py ^> storage\logs\backend_dev.log 2^>^&1"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Electron dev...
start "Transkrib-Electron" cmd /c "cd /d ""%EWIN%"" ^&^& npm run dev"

echo ============================================================
echo  Dev servers launched.
echo.
echo  Backend:  http://127.0.0.1:8000
echo  Vite:     http://localhost:5173
echo  API docs: http://127.0.0.1:8000/docs
echo  Log:      %BACKEND%\storage\logs\backend_dev.log
echo.
echo  Run dev_stop.bat to kill all dev processes.
echo ============================================================
