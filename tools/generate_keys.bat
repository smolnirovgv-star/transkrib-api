@echo off
chcp 1251 >nul
echo ============================================================
echo  Transkrib Key Generator — All Plans
echo ============================================================
echo.

pushd "%~dp0"
if errorlevel 1 (
    echo ERROR: Cannot change to tools directory.
    pause & exit /b 1
)

echo [1/3] Generating BASE keys (10 days, 50 keys)...
python keygen.py --plan base --count 50 --output "./Transkrib_Keys"
if errorlevel 1 ( echo ERROR: keygen failed for BASE plan. & pause & exit /b 1 )

echo.
echo [2/3] Generating STND keys (30 days, 30 keys)...
python keygen.py --plan std --count 30 --output "./Transkrib_Keys"
if errorlevel 1 ( echo ERROR: keygen failed for STND plan. & pause & exit /b 1 )

echo.
echo [3/3] Generating PREM keys (365 days, 15 keys)...
python keygen.py --plan pro --count 15 --output "./Transkrib_Keys"
if errorlevel 1 ( echo ERROR: keygen failed for PREM plan. & pause & exit /b 1 )

popd

echo.
echo ============================================================
echo  Keys generated in: %~dp0Transkrib_Keys\
echo    plan_basic\      — BASE  (10 days, 50 keys)
echo    plan_standard\   — STND  (30 days, 30 keys)
echo    plan_pro\        — PREM  (365 days, 15 keys)
echo ============================================================
pause
