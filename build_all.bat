@echo off
chcp 1251 >nul
echo ============================================================
echo  Transkrib Build Script
echo ============================================================
echo.

:: ── Step 1: PyInstaller ──────────────────────────────────────
echo [1/3] Cleaning previous build...
pushd "%~dp0backend"
if errorlevel 1 (
    echo ERROR: Cannot change to backend directory.
    echo Path: %~dp0backend
    pause & exit /b 1
)
if exist dist\backend rmdir /s /q dist\backend
if exist build\backend rmdir /s /q build\backend
popd

echo [2/3] Building backend.exe (may take 5-15 min)...
pushd "%~dp0backend"
if errorlevel 1 (
    echo ERROR: Cannot change to backend directory.
    echo Path: %~dp0backend
    pause & exit /b 1
)
python -m PyInstaller backend.spec --clean --noconfirm
if errorlevel 1 (
    popd
    echo.
    echo ERROR: PyInstaller failed. Check output above.
    pause
    exit /b 1
)
popd
echo.
echo backend.exe built successfully.
echo.

:: ── Step 2: Electron + Universal Installer ────────────────────
echo [3/3] Building Electron installer (x64 + ia32 + universal)...
call "%~dp0rebuild_installer.bat"
if errorlevel 1 (
    echo.
    echo ERROR: rebuild_installer failed. Check output above.
    pause
    exit /b 1
)
