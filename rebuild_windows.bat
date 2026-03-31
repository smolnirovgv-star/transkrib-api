@echo off
echo ========================================
echo  Transkrib SmartCut AI - Windows Rebuild
echo ========================================
echo.

echo [1/4] Сборка backend.exe...
cd backend
call pyinstaller backend.spec --clean
if errorlevel 1 ( echo ОШИБКА: pyinstaller завершился с ошибкой & pause & exit /b 1 )
cd ..

echo [2/4] Сборка Windows инсталлятора...
cd platforms\desktop_windows
call npm run build
if errorlevel 1 ( echo ОШИБКА: npm run build завершился с ошибкой & pause & exit /b 1 )
cd ..\..

echo [3/4] Обновление GitHub Release...
gh release delete-asset v1.0.1 "Transkrib.SmartCut.AI-Setup-1.0.1.exe" --yes 2>/dev/null
gh release delete-asset v1.0.1 "Transkrib.SmartCut.AI-Setup-1.0.1-x64.exe" --yes 2>/dev/null
gh release delete-asset v1.0.1 "Transkrib.SmartCut.AI-Setup-1.0.1-ia32.exe" --yes 2>/dev/null

gh release upload v1.0.1 ^
  "platforms\desktop_windows\release\Transkrib SmartCut AI-Setup-1.0.1.exe" ^
  "platforms\desktop_windows\release\Transkrib SmartCut AI-Setup-1.0.1-x64.exe" ^
  "platforms\desktop_windows\release\Transkrib SmartCut AI-Setup-1.0.1-ia32.exe" ^
  --clobber

echo [4/4] Публикация релиза...
gh release edit v1.0.1 --draft=false --latest

echo.
echo ========================================
echo  ГОТОВО! Release v1.0.1 обновлён.
echo ========================================
pause
