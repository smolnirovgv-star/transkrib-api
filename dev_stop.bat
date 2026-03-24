@echo off
echo Transkrib SmartCut AI - Dev Stop
echo.
echo Killing Electron...
taskkill /F /IM electron.exe /T >nul 2>&1
echo Killing Vite (port 5173)...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5173 "') do taskkill /F /PID %%p >nul 2>&1
echo Killing backend (port 8000)...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /F /PID %%p >nul 2>&1
echo Closing dev windows...
taskkill /F /FI "WINDOWTITLE eq Transkrib-Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Transkrib-Electron" >nul 2>&1
echo.
echo All dev processes stopped.
