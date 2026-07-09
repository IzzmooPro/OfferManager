@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Teklif Yonetim Sistemi - Otomatik Baslatici
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [HATA] Program baslatilamadi. Yukaridaki aciklamayi inceleyin.
    pause
)

exit /b %EXIT_CODE%
