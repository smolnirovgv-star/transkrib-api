@echo off
chcp 1251 >nul
echo ============================================================
echo  Transkrib — Universal Installer Build (x64 + ia32)
echo ============================================================
echo.

set "EWIN=%~dp0platforms\desktop_windows"
set "RELEASE=%EWIN%\release"
set "BUILD=%EWIN%\build"

:: ── Step 1: npm install ───────────────────────────────────────
pushd "%EWIN%"
if errorlevel 1 (
    echo ERROR: Cannot change to Electron directory.
    echo Path: %EWIN%
    pause & exit /b 1
)
echo [1/5] Installing npm dependencies...
if exist node_modules rmdir /s /q node_modules
if exist package-lock.json del package-lock.json
call npm install
if errorlevel 1 ( popd & echo ERROR: npm install failed. & pause & exit /b 1 )

:: ── Step 2: Build Electron renderer + main ───────────────────
echo.
echo [2/5] Building Electron app (renderer + main)...
call npm run build
if errorlevel 1 ( popd & echo ERROR: npm run build failed. & pause & exit /b 1 )

:: ── Step 3: electron-builder x64 + ia32 ─────────────────────
echo.
echo [3/5] Packaging NSIS installers (x64 and ia32)...
call npx electron-builder --win --x64 --ia32
if errorlevel 1 ( popd & echo ERROR: electron-builder failed. & pause & exit /b 1 )
popd

:: Verify both arch installers exist
if not exist "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe" (
    echo ERROR: x64 installer not found in release\
    pause & exit /b 1
)
if not exist "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe" (
    echo ERROR: ia32 installer not found in release\
    pause & exit /b 1
)

:: ── Step 4: Find makensis ────────────────────────────────────
echo.
echo [4/5] Locating makensis...
set MAKENSIS=

:: Try 1: electron-builder bundled (app-builder-lib vendor)
for /f "delims=" %%f in ('dir /s /b "%EWIN%\node_modules\app-builder-lib\vendor\nsis\windows\makensis.exe" 2^>nul') do (
    set "MAKENSIS=%%f" & goto :found_nsis
)

:: Try 2: electron-builder cache (downloaded NSIS)
for /d %%d in ("%LOCALAPPDATA%\electron-builder\Cache\nsis\nsis-*") do (
    if exist "%%d\Bin\makensis.exe" (
        set "MAKENSIS=%%d\Bin\makensis.exe" & goto :found_nsis
    )
)

:: Try 3: system PATH
for /f "delims=" %%f in ('where makensis.exe 2^>nul') do (
    set "MAKENSIS=%%f" & goto :found_nsis
)

:: Try 4: default NSIS install path
if exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe" & goto :found_nsis
)
if exist "C:\Program Files\NSIS\makensis.exe" (
    set "MAKENSIS=C:\Program Files\NSIS\makensis.exe" & goto :found_nsis
)

echo ERROR: makensis.exe not found.
echo.
echo Install NSIS from https://nsis.sourceforge.io/Download
echo OR the universal wrapper step requires makensis to be available.
echo.
echo The arch-specific installers are ready:
echo   %RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe
echo   %RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe
pause & exit /b 1

:found_nsis
echo Found makensis: %MAKENSIS%

:: ── Step 5: Compile universal wrapper ───────────────────────
echo.
echo [5/5] Compiling universal installer wrapper...

:: Copy sub-installers next to the .nsi script (NSIS File command needs relative paths)
copy /y "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe"  "%BUILD%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe"  >nul
copy /y "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe" "%BUILD%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe" >nul

:: Compile — CWD must be BUILD for NSIS relative File commands
pushd "%BUILD%"
if errorlevel 1 (
    echo ERROR: Cannot change to build directory.
    echo Path: %BUILD%
    pause & exit /b 1
)
"%MAKENSIS%" installer-universal.nsi
if errorlevel 1 ( popd & echo ERROR: NSIS compilation failed. & pause & exit /b 1 )
popd

:: Move compiled universal installer to release\
move /y "%BUILD%\Transkrib SmartCut AI-Setup-1.0.0.exe" "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0.exe" >nul

:: Cleanup temp copies
del /q "%BUILD%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe"  2>nul
del /q "%BUILD%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe" 2>nul

:: ── Step 6: Version the installers ───────────────────────
echo.
echo [6/5] Creating versioned copies (build number + date)...

:: Get current date in YYYY-MM-DD format via PowerShell (locale-independent, no WMI shell refresh)
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set BUILD_DATE=%%d
if not defined BUILD_DATE set BUILD_DATE=0000-00-00

:: Read and increment build number
set BUILD_COUNTER_FILE=%RELEASE%\build_counter.txt
set BUILD_NUM=0
if exist "%BUILD_COUNTER_FILE%" set /p BUILD_NUM=<"%BUILD_COUNTER_FILE%"
set /a BUILD_NUM_NEXT=%BUILD_NUM%+1

:: Zero-pad to 3 digits
set BUILD_NUM_FMT=00%BUILD_NUM_NEXT%
set BUILD_NUM_FMT=%BUILD_NUM_FMT:~-3%

:: Create versioned copies alongside originals
set VBASE=%RELEASE%\Transkrib-Setup-b%BUILD_NUM_FMT%-%BUILD_DATE%
copy /y "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0.exe"      "%VBASE%.exe"       >nul
copy /y "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe"  "%VBASE%-x64.exe"  >nul
copy /y "%RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe" "%VBASE%-ia32.exe" >nul

:: Save updated counter
echo %BUILD_NUM_NEXT%>"%BUILD_COUNTER_FILE%"

echo.
echo ============================================================
echo  BUILD COMPLETE — Build #%BUILD_NUM_FMT% (%BUILD_DATE%)
echo ============================================================
echo.
echo  Versioned installers (build #%BUILD_NUM_FMT%):
echo    %VBASE%.exe
echo    %VBASE%-x64.exe
echo    %VBASE%-ia32.exe
echo.
echo  Latest (unversioned aliases):
echo    %RELEASE%\Transkrib SmartCut AI-Setup-1.0.0.exe
echo    %RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-x64.exe
echo    %RELEASE%\Transkrib SmartCut AI-Setup-1.0.0-ia32.exe
echo.
echo  NOTE: On 32-bit Windows the app installs but AI features
echo  (Whisper/PyTorch) require 64-bit. User sees a clear dialog.
echo ============================================================
pause
